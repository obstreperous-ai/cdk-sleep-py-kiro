from aws_cdk import assertions
from aws_cdk.assertions import Match


def test_stack_synthesizes_valid_template(template):
    # Verify the stack synthesizes a valid CloudFormation template
    template_json = template.to_json()
    assert isinstance(template_json, dict)
    # An empty CDK stack still produces valid CloudFormation with Parameters and Rules
    assert len(template_json) > 0


def test_stack_has_exactly_two_s3_buckets(template):
    template.resource_count_is("AWS::S3::Bucket", 2)


def test_both_buckets_have_correct_properties(template):
    # Find all S3 buckets matching expected properties; both must match
    buckets = template.find_resources(
        "AWS::S3::Bucket",
        {
            "Properties": {
                "VersioningConfiguration": {"Status": "Enabled"},
                "BucketEncryption": {
                    "ServerSideEncryptionConfiguration": Match.any_value()
                },
                "PublicAccessBlockConfiguration": {
                    "BlockPublicAcls": True,
                    "BlockPublicPolicy": True,
                    "IgnorePublicAcls": True,
                    "RestrictPublicBuckets": True,
                },
            },
        },
    )
    assert len(buckets) == 2


def test_input_bucket_has_eventbridge_notifications(template):
    # The Custom::S3BucketNotifications resource references the input bucket.
    # This confirms which bucket is the input bucket (it has EventBridge enabled).
    template.has_resource_properties(
        "Custom::S3BucketNotifications",
        {
            "BucketName": Match.any_value(),
            "NotificationConfiguration": {
                "EventBridgeConfiguration": {}
            },
        },
    )
    # Only one notification resource exists, confirming only the input bucket
    # has EventBridge notifications (not the output bucket)
    template.resource_count_is("Custom::S3BucketNotifications", 1)


def test_eventbridge_rule_exists(template):
    template.has_resource_properties(
        "AWS::Events::Rule",
        {
            "EventPattern": {
                "source": ["aws.s3"],
                "detail-type": ["Object Created"],
                "detail": {
                    "bucket": {
                        "name": Match.any_value()
                    }
                },
            },
        },
    )


def test_eventbridge_rule_has_target(template):
    template.has_resource_properties(
        "AWS::Events::Rule",
        {
            "Targets": Match.any_value(),
        },
    )


def test_log_group_has_one_week_retention(template):
    template.has_resource_properties(
        "AWS::Logs::LogGroup",
        {
            "RetentionInDays": 7,
        },
    )
