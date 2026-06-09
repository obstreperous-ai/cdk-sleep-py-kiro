from aws_cdk import (
    RemovalPolicy,
    Stack,
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
        config = ENV_CONFIG.get(environment, ENV_CONFIG["dev"])
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
        publish_failed_notification = sfn_tasks.SnsPublish(
            self,
            "PublishFailedNotification",
            topic=failed_topic,
            message=sfn.TaskInput.from_object(
                {
                    "audioId": sfn.JsonPath.string_at("$.object.key"),
                    "status": "FAILED",
                    "reason": sfn.JsonPath.string_at(
                        "$.processAudioResult.Payload.validationError"
                    ),
                }
            ),
            result_path="$.snsFailedResult",
        )

        # Choice state: validate input based on Lambda result
        validate_input = sfn.Choice(self, "ValidateInput")

        # Error handling: catch errors from WriteInitialRecord -> Fail
        # (cannot write a FAILED record if DynamoDB itself is down)
        write_initial_record.add_catch(fail_state, result_path="$.error")

        # Error handling: catch errors from ProcessAudio -> UpdateStatusFailed -> PublishFailedNotification -> Fail
        process_audio_task.add_catch(update_status_failed, result_path="$.error")

        # Error handling: catch errors from PollyTask -> UpdateStatusFailed -> PublishFailedNotification -> Fail
        polly_task.add_catch(update_status_failed, result_path="$.error")
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
        validate_input.otherwise(update_status_failed)

        # Main chain: WriteInitialRecord -> ProcessAudio -> ValidateInput -> (Choice routes)
        definition = write_initial_record.next(
            process_audio_task.next(validate_input)
        )

        # State machine with logging enabled
        state_machine = sfn.StateMachine(
            self,
            "AudioPipelineStateMachine",
            definition_body=sfn.DefinitionBody.from_chainable(definition),
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
