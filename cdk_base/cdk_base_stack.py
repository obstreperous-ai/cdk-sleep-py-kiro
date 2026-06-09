from aws_cdk import (
    Duration,
    RemovalPolicy,
    Stack,
    aws_cloudwatch as cloudwatch,
    aws_s3 as s3,
    aws_dynamodb as dynamodb,
    aws_events as events,
    aws_events_targets as targets,
    aws_kms as kms,
    aws_lambda as _lambda,
    aws_logs as logs,
    aws_sns as sns,
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as sfn_tasks,
)
from constructs import Construct


# Environment-specific configuration
ENV_CONFIG = {
    "dev": {
        "log_retention": logs.RetentionDays.ONE_WEEK,
        "removal_policy": RemovalPolicy.DESTROY,
    },
    "stage": {
        "log_retention": logs.RetentionDays.ONE_MONTH,
        "removal_policy": RemovalPolicy.DESTROY,
    },
    "prod": {
        "log_retention": logs.RetentionDays.THREE_MONTHS,
        "removal_policy": RemovalPolicy.RETAIN,
    },
}


class CdkBaseStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Read environment context, default to 'dev'
        environment = self.node.try_get_context("environment") or "dev"

        # Validate environment value
        if environment not in ENV_CONFIG:
            raise ValueError(
                f"Unrecognized environment '{environment}'. "
                f"Must be one of: {', '.join(sorted(ENV_CONFIG.keys()))}"
            )

        config = ENV_CONFIG[environment]
        removal_policy = config["removal_policy"]
        log_retention = config["log_retention"]

        # For prod, do not auto-delete objects (RETAIN policy)
        auto_delete = removal_policy == RemovalPolicy.DESTROY

        # Input S3 Bucket for raw audio uploads
        input_bucket = s3.Bucket(
            self,
            "SleepAudioInputBucket",
            versioned=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            event_bridge_enabled=True,
            removal_policy=removal_policy,
            auto_delete_objects=auto_delete,
        )

        # Output S3 Bucket for processed audio
        s3.Bucket(
            self,
            "SleepAudioOutputBucket",
            versioned=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=removal_policy,
            auto_delete_objects=auto_delete,
        )

        # DynamoDB Metadata Table for audio pipeline tracking
        metadata_table = dynamodb.Table(
            self,
            "SleepAudioMetadataTable",
            partition_key=dynamodb.Attribute(
                name="audioId",
                type=dynamodb.AttributeType.STRING,
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            encryption=dynamodb.TableEncryption.AWS_MANAGED,
            point_in_time_recovery=True,
            removal_policy=removal_policy,
        )

        # Lambda function for audio processing
        # Note: Using CDK defaults for memory (128 MB) and timeout (3 s) while
        # this remains a placeholder. Update these when real audio processing
        # logic is added.
        process_audio_fn = _lambda.Function(
            self,
            "SleepAudioProcessor",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="handler.lambda_handler",
            code=_lambda.Code.from_asset("lambda/sleep_audio_processor"),
            tracing=_lambda.Tracing.ACTIVE,
            environment={
                "TABLE_NAME": metadata_table.table_name,
            },
        )

        # Grant Lambda read/write access to the metadata table.
        # Intentional scaffolding: the handler does not use DynamoDB yet, but
        # will need it once enrichment logic writes processing results back to
        # the metadata table. Granting now avoids a redeploy when that code lands.
        metadata_table.grant_read_write_data(process_audio_fn)

        # CloudWatch Log Group for state machine logging
        log_group = logs.LogGroup(
            self,
            "AudioUploadRuleLogGroup",
            retention=log_retention,
            removal_policy=removal_policy,
        )

        # KMS key for SNS topic encryption
        sns_kms_key = kms.Key(
            self,
            "SnsTopicEncryptionKey",
            enable_key_rotation=True,
            removal_policy=removal_policy,
        )

        # SNS Topic for pipeline completion notifications
        completed_topic = sns.Topic(
            self,
            "SleepAudioPipelineCompleted",
            master_key=sns_kms_key,
        )

        # SNS Topic for pipeline failure notifications
        failed_topic = sns.Topic(
            self,
            "SleepAudioPipelineFailed",
            master_key=sns_kms_key,
        )

        # Step Functions: Write initial metadata record (PROCESSING)
        # Note: audioId uses the raw S3 object key (may contain path separators
        # or URL-encoded characters). Downstream consumers should be aware of this format.
        write_initial_record = sfn_tasks.DynamoPutItem(
            self,
            "WriteInitialRecord",
            table=metadata_table,
            item={
                "audioId": sfn_tasks.DynamoAttributeValue.from_string(
                    sfn.JsonPath.string_at("$.object.key")
                ),
                "status": sfn_tasks.DynamoAttributeValue.from_string("PROCESSING"),
                "inputBucket": sfn_tasks.DynamoAttributeValue.from_string(
                    sfn.JsonPath.string_at("$.bucket.name")
                ),
                "inputKey": sfn_tasks.DynamoAttributeValue.from_string(
                    sfn.JsonPath.string_at("$.object.key")
                ),
                "createdAt": sfn_tasks.DynamoAttributeValue.from_string(
                    sfn.JsonPath.string_at("$$.State.EnteredTime")
                ),
            },
            result_path="$.dynamoResult",
        )

        # Retry policy for WriteInitialRecord (transient DynamoDB errors)
        write_initial_record.add_retry(
            errors=["States.TaskFailed"],
            interval=Duration.seconds(2),
            max_attempts=3,
            backoff_rate=2.0,
        )

        # Step Functions: Polly task state
        polly_task = sfn_tasks.CallAwsService(
            self,
            "PollyTask",
            service="polly",
            action="startSpeechSynthesisTask",
            parameters={
                "OutputFormat": "mp3",
                "Text": "placeholder",
                "VoiceId": "Joanna",
                "OutputS3BucketName": "placeholder-bucket",
            },
            iam_resources=["*"],
            result_path="$.pollyResult",
        )

        # Retry policy for PollyTask (transient Polly errors)
        polly_task.add_retry(
            errors=["States.TaskFailed"],
            interval=Duration.seconds(5),
            max_attempts=3,
            backoff_rate=2.0,
        )

        # Step Functions: Lambda invoke task for audio processing
        # Scope payload to only the fields the handler needs, preventing
        # upstream state changes from silently breaking input validation.
        process_audio_task = sfn_tasks.LambdaInvoke(
            self,
            "ProcessAudio",
            lambda_function=process_audio_fn,
            payload=sfn.TaskInput.from_object(
                {
                    "bucket": sfn.JsonPath.object_at("$.bucket"),
                    "object": sfn.JsonPath.object_at("$.object"),
                }
            ),
            result_path="$.processAudioResult",
            retry_on_service_exceptions=False,
        )

        # Retry policy for ProcessAudio (transient Lambda errors)
        process_audio_task.add_retry(
            errors=[
                "Lambda.ServiceException",
                "Lambda.AWSLambdaException",
                "Lambda.SdkClientException",
            ],
            interval=Duration.seconds(2),
            max_attempts=3,
            backoff_rate=2.0,
        )

        # Step Functions: Update status to COMPLETED on success
        update_status_completed = sfn_tasks.DynamoUpdateItem(
            self,
            "UpdateStatusCompleted",
            table=metadata_table,
            key={
                "audioId": sfn_tasks.DynamoAttributeValue.from_string(
                    sfn.JsonPath.string_at("$.object.key")
                ),
            },
            update_expression="SET #s = :status, #u = :updatedAt",
            expression_attribute_names={
                "#s": "status",
                "#u": "updatedAt",
            },
            expression_attribute_values={
                ":status": sfn_tasks.DynamoAttributeValue.from_string("COMPLETED"),
                ":updatedAt": sfn_tasks.DynamoAttributeValue.from_string(
                    sfn.JsonPath.string_at("$$.State.EnteredTime")
                ),
            },
            result_path="$.updateResult",
        )

        # Step Functions: Update status to FAILED on error
        update_status_failed = sfn_tasks.DynamoUpdateItem(
            self,
            "UpdateStatusFailed",
            table=metadata_table,
            key={
                "audioId": sfn_tasks.DynamoAttributeValue.from_string(
                    sfn.JsonPath.string_at("$.object.key")
                ),
            },
            update_expression="SET #s = :status, #u = :updatedAt",
            expression_attribute_names={
                "#s": "status",
                "#u": "updatedAt",
            },
            expression_attribute_values={
                ":status": sfn_tasks.DynamoAttributeValue.from_string("FAILED"),
                ":updatedAt": sfn_tasks.DynamoAttributeValue.from_string(
                    sfn.JsonPath.string_at("$$.State.EnteredTime")
                ),
            },
            result_path="$.updateResult",
        )

        # Terminal states
        succeed_state = sfn.Succeed(self, "Done")
        fail_state = sfn.Fail(
            self, "Fail", cause="Pipeline execution failed"
        )

        # SNS Publish task: notify on successful completion
        publish_completed_notification = sfn_tasks.SnsPublish(
            self,
            "PublishCompletedNotification",
            topic=completed_topic,
            message=sfn.TaskInput.from_object(
                {
                    "audioId": sfn.JsonPath.string_at("$.object.key"),
                    "status": "COMPLETED",
                }
            ),
            result_path="$.snsCompletedResult",
        )

        # SNS Publish task: notify on pipeline failure
        # Uses $.failureReason which is normalized by NormalizeFailureInfo pass state
        publish_failed_notification = sfn_tasks.SnsPublish(
            self,
            "PublishFailedNotification",
            topic=failed_topic,
            message=sfn.TaskInput.from_object(
                {
                    "audioId": sfn.JsonPath.string_at("$.object.key"),
                    "status": "FAILED",
                    "reason": sfn.JsonPath.string_at("$.failureReason"),
                }
            ),
            result_path="$.snsFailedResult",
        )

        # Pass state to normalize failure info for the error-caught path
        # When errors are caught, $.error.Error contains the error type
        normalize_caught_error = sfn.Pass(
            self,
            "NormalizeCaughtError",
            parameters={
                "object.$": "$.object",
                "bucket.$": "$.bucket",
                "error.$": "$.error",
                "failureReason.$": "$.error.Error",
            },
        )

        # Pass state to normalize failure info for the validation-failure path
        # When validation fails, $.processAudioResult.Payload.validationError has the reason
        normalize_validation_error = sfn.Pass(
            self,
            "NormalizeValidationError",
            parameters={
                "object.$": "$.object",
                "bucket.$": "$.bucket",
                "processAudioResult.$": "$.processAudioResult",
                "failureReason.$": "$.processAudioResult.Payload.validationError",
            },
        )

        # Choice state: validate input based on Lambda result
        validate_input = sfn.Choice(self, "ValidateInput")

        # Error handling: catch errors from WriteInitialRecord -> Fail
        # (cannot write a FAILED record if DynamoDB itself is down)
        write_initial_record.add_catch(fail_state, result_path="$.error")

        # Error handling: catch errors from ProcessAudio -> NormalizeCaughtError -> UpdateStatusFailed -> PublishFailedNotification -> Fail
        # First catch: specific Lambda infrastructure errors
        process_audio_task.add_catch(
            normalize_caught_error,
            errors=[
                "Lambda.ServiceException",
                "Lambda.AWSLambdaException",
                "Lambda.SdkClientException",
                "States.TaskFailed",
            ],
            result_path="$.error",
        )
        # Fallback catch: application-level exceptions (ValueError, etc.)
        process_audio_task.add_catch(
            normalize_caught_error,
            errors=["States.ALL"],
            result_path="$.error",
        )

        # Error handling: catch errors from PollyTask -> NormalizeCaughtError -> UpdateStatusFailed -> PublishFailedNotification -> Fail
        polly_task.add_catch(
            normalize_caught_error,
            errors=["States.TaskFailed"],
            result_path="$.error",
        )
        # Fallback catch: Polly service-specific errors (throttling, limit exceeded, etc.)
        polly_task.add_catch(
            normalize_caught_error,
            errors=["States.ALL"],
            result_path="$.error",
        )

        # Chain: NormalizeCaughtError -> UpdateStatusFailed -> PublishFailedNotification -> Fail
        normalize_caught_error.next(update_status_failed)
        # Chain: NormalizeValidationError -> UpdateStatusFailed (same downstream)
        normalize_validation_error.next(update_status_failed)
        update_status_failed.next(publish_failed_notification)
        publish_failed_notification.add_catch(fail_state, result_path="$.notificationError")
        publish_failed_notification.next(fail_state)

        # Error handling: catch notification errors on success path
        publish_completed_notification.add_catch(
            succeed_state, result_path="$.notificationError"
        )

        # ValidateInput Choice: route based on Lambda validation result
        validate_input.when(
            sfn.Condition.boolean_equals(
                "$.processAudioResult.Payload.valid", True
            ),
            polly_task.next(
                update_status_completed.next(
                    publish_completed_notification.next(succeed_state)
                )
            ),
        )
        validate_input.otherwise(normalize_validation_error)

        # Main chain: WriteInitialRecord -> ProcessAudio -> ValidateInput -> (Choice routes)
        definition = write_initial_record.next(
            process_audio_task.next(validate_input)
        )

        # State machine with logging and X-Ray tracing enabled
        state_machine = sfn.StateMachine(
            self,
            "AudioPipelineStateMachine",
            definition_body=sfn.DefinitionBody.from_chainable(definition),
            tracing_enabled=True,
            logs=sfn.LogOptions(
                destination=log_group,
                level=sfn.LogLevel.ALL,
            ),
            removal_policy=removal_policy,
        )

        # Grant KMS permissions to the state machine role for encrypted SNS topics
        sns_kms_key.grant_encrypt_decrypt(state_machine.role)

        # EventBridge Rule matching Object Created events from the input bucket
        rule = events.Rule(
            self,
            "AudioUploadRule",
            event_pattern=events.EventPattern(
                source=["aws.s3"],
                detail_type=["Object Created"],
                detail={
                    "bucket": {
                        "name": [input_bucket.bucket_name]
                    }
                },
            ),
        )

        # Target the state machine with event detail as input
        rule.add_target(
            targets.SfnStateMachine(
                state_machine,
                input=events.RuleTargetInput.from_event_path("$.detail"),
            )
        )

        # CloudWatch Alarm: State machine execution failures
        state_machine.metric_failed(
            period=Duration.minutes(5),
            statistic="Sum",
        ).create_alarm(
            self,
            "StateMachineExecutionFailuresAlarm",
            alarm_description="Alarm when state machine executions fail",
            threshold=1,
            evaluation_periods=1,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
        )

        # CloudWatch Alarm: Lambda function errors
        process_audio_fn.metric_errors(
            period=Duration.minutes(5),
            statistic="Sum",
        ).create_alarm(
            self,
            "LambdaErrorsAlarm",
            alarm_description="Alarm when Lambda function encounters errors",
            threshold=1,
            evaluation_periods=1,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
        )
