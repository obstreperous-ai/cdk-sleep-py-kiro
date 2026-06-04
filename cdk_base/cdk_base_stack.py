from aws_cdk import (
    RemovalPolicy,
    Stack,
    aws_s3 as s3,
    aws_dynamodb as dynamodb,
    aws_events as events,
    aws_events_targets as targets,
    aws_logs as logs,
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as sfn_tasks,
)
from constructs import Construct


class CdkBaseStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Input S3 Bucket for raw audio uploads
        input_bucket = s3.Bucket(
            self,
            "SleepAudioInputBucket",
            versioned=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            event_bridge_enabled=True,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        # Output S3 Bucket for processed audio
        s3.Bucket(
            self,
            "SleepAudioOutputBucket",
            versioned=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
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
            removal_policy=RemovalPolicy.DESTROY,
        )

        # CloudWatch Log Group for state machine logging
        log_group = logs.LogGroup(
            self,
            "AudioUploadRuleLogGroup",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY,
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

        # Error handling: catch errors from WriteInitialRecord -> Fail
        # (cannot write a FAILED record if DynamoDB itself is down)
        write_initial_record.add_catch(fail_state, result_path="$.error")

        # Error handling: catch errors from PollyTask -> UpdateStatusFailed -> Fail
        polly_task.add_catch(update_status_failed, result_path="$.error")
        update_status_failed.next(fail_state)

        # Main chain: WriteInitialRecord -> PollyTask -> UpdateStatusCompleted -> Done
        definition = write_initial_record.next(
            polly_task.next(
                update_status_completed.next(succeed_state)
            )
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
            removal_policy=RemovalPolicy.DESTROY,
        )

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
