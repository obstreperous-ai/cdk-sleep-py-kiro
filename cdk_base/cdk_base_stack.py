from aws_cdk import (
    RemovalPolicy,
    Stack,
    aws_s3 as s3,
    aws_events as events,
    aws_events_targets as targets,
    aws_logs as logs,
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
        )

        # Output S3 Bucket for processed audio
        s3.Bucket(
            self,
            "SleepAudioOutputBucket",
            versioned=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
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

        # Placeholder target - CloudWatch Log Group
        log_group = logs.LogGroup(
            self,
            "AudioUploadRuleLogGroup",
            removal_policy=RemovalPolicy.DESTROY,
        )
        rule.add_target(targets.CloudWatchLogGroup(log_group))
