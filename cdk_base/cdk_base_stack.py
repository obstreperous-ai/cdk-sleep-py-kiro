from aws_cdk import (
    RemovalPolicy,
    Stack,
    aws_s3 as s3,
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

        # CloudWatch Log Group for state machine logging
        log_group = logs.LogGroup(
            self,
            "AudioUploadRuleLogGroup",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY,
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

        # State machine definition: Polly Task -> Succeed
        succeed_state = sfn.Succeed(self, "Done")
        definition = polly_task.next(succeed_state)

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
