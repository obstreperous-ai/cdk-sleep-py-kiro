from aws_cdk import assertions


def test_stack_synthesizes_valid_template(template):
    # Verify the stack synthesizes a valid CloudFormation template
    template_json = template.to_json()
    assert isinstance(template_json, dict)
    # An empty CDK stack still produces valid CloudFormation with Parameters and Rules
    assert len(template_json) > 0


def test_input_bucket_has_correct_properties(template):
    template.has_resource_properties(
        "AWS::S3::Bucket",
        {
            "VersioningConfiguration": {"Status": "Enabled"},
            "BucketEncryption": {
                "ServerSideEncryptionConfiguration": assertions.Match.any_value()
            },
            "PublicAccessBlockConfiguration": {
                "BlockPublicAcls": True,
                "BlockPublicPolicy": True,
                "IgnorePublicAcls": True,
                "RestrictPublicBuckets": True,
            },
        },
    )


def test_input_bucket_has_eventbridge_notifications_enabled(template):
    # CDK uses a custom resource to enable EventBridge notifications on S3 buckets
    template.has_resource_properties(
        "Custom::S3BucketNotifications",
        {
            "NotificationConfiguration": {
                "EventBridgeConfiguration": {}
            },
        },
    )


def test_output_bucket_has_correct_properties(template):
    template.has_resource_properties(
        "AWS::S3::Bucket",
        {
            "VersioningConfiguration": {"Status": "Enabled"},
            "BucketEncryption": {
                "ServerSideEncryptionConfiguration": assertions.Match.any_value()
            },
            "PublicAccessBlockConfiguration": {
                "BlockPublicAcls": True,
                "BlockPublicPolicy": True,
                "IgnorePublicAcls": True,
                "RestrictPublicBuckets": True,
            },
        },
    )


def test_stack_has_exactly_two_s3_buckets(template):
    template.resource_count_is("AWS::S3::Bucket", 2)


def test_eventbridge_rule_exists(template):
    template.has_resource_properties(
        "AWS::Events::Rule",
        {
            "EventPattern": {
                "source": ["aws.s3"],
                "detail-type": ["Object Created"],
                "detail": assertions.Match.any_value(),
            },
        },
    )


def test_eventbridge_rule_has_target(template):
    template.has_resource_properties(
        "AWS::Events::Rule",
        {
            "Targets": assertions.Match.any_value(),
        },
    )
