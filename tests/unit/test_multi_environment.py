"""Tests for multi-environment support via CDK context.

Verifies that environment-specific behavior is controlled by the 'environment'
context value passed to the CDK App.
"""

import pytest
import aws_cdk as cdk
import aws_cdk.assertions as assertions

from cdk_base.cdk_base_stack import CdkBaseStack


@pytest.fixture
def dev_template():
    """Synthesize a template with environment=dev context."""
    app = cdk.App(context={"environment": "dev"})
    stack = CdkBaseStack(app, "DevStack")
    return assertions.Template.from_stack(stack)


@pytest.fixture
def stage_template():
    """Synthesize a template with environment=stage context."""
    app = cdk.App(context={"environment": "stage"})
    stack = CdkBaseStack(app, "StageStack")
    return assertions.Template.from_stack(stack)


@pytest.fixture
def prod_template():
    """Synthesize a template with environment=prod context."""
    app = cdk.App(context={"environment": "prod"})
    stack = CdkBaseStack(app, "ProdStack")
    return assertions.Template.from_stack(stack)


class TestLogRetentionByEnvironment:
    """Log retention differs by environment."""

    def test_dev_log_retention_7_days(self, dev_template):
        """Dev environment has 7-day log retention."""
        dev_template.has_resource_properties(
            "AWS::Logs::LogGroup",
            {"RetentionInDays": 7},
        )

    def test_stage_log_retention_30_days(self, stage_template):
        """Stage environment has 30-day log retention."""
        stage_template.has_resource_properties(
            "AWS::Logs::LogGroup",
            {"RetentionInDays": 30},
        )

    def test_prod_log_retention_90_days(self, prod_template):
        """Prod environment has 90-day log retention."""
        prod_template.has_resource_properties(
            "AWS::Logs::LogGroup",
            {"RetentionInDays": 90},
        )


class TestRemovalPolicyByEnvironment:
    """Removal policy is RETAIN for prod and DESTROY for dev/stage."""

    def test_dev_dynamodb_deletion_policy_delete(self, dev_template):
        """Dev environment DynamoDB table has Delete removal policy."""
        dev_template.has_resource(
            "AWS::DynamoDB::Table",
            {"DeletionPolicy": "Delete"},
        )

    def test_stage_dynamodb_deletion_policy_delete(self, stage_template):
        """Stage environment DynamoDB table has Delete removal policy."""
        stage_template.has_resource(
            "AWS::DynamoDB::Table",
            {"DeletionPolicy": "Delete"},
        )

    def test_prod_dynamodb_deletion_policy_retain(self, prod_template):
        """Prod environment DynamoDB table has Retain removal policy."""
        prod_template.has_resource(
            "AWS::DynamoDB::Table",
            {"DeletionPolicy": "Retain"},
        )

    def test_prod_s3_input_bucket_deletion_policy_retain(self, prod_template):
        """Prod environment S3 input bucket has Retain removal policy."""
        # Find S3 buckets - at least one should have Retain
        buckets = prod_template.find_resources("AWS::S3::Bucket")
        retain_count = sum(
            1 for b in buckets.values() if b.get("DeletionPolicy") == "Retain"
        )
        assert retain_count >= 1, "Prod should have at least one S3 bucket with Retain policy"

    def test_dev_s3_bucket_deletion_policy_delete(self, dev_template):
        """Dev environment S3 buckets have Delete removal policy."""
        buckets = dev_template.find_resources("AWS::S3::Bucket")
        for name, bucket in buckets.items():
            assert bucket.get("DeletionPolicy") == "Delete", (
                f"Dev S3 bucket {name} should have Delete deletion policy"
            )


class TestStackInstantiationWithContext:
    """Stack can be instantiated with different environment context values."""

    def test_stack_instantiates_with_dev_context(self):
        """Stack instantiates cleanly with dev context."""
        app = cdk.App(context={"environment": "dev"})
        stack = CdkBaseStack(app, "DevTestStack")
        template = assertions.Template.from_stack(stack)
        template.resource_count_is("AWS::StepFunctions::StateMachine", 1)

    def test_stack_instantiates_with_stage_context(self):
        """Stack instantiates cleanly with stage context."""
        app = cdk.App(context={"environment": "stage"})
        stack = CdkBaseStack(app, "StageTestStack")
        template = assertions.Template.from_stack(stack)
        template.resource_count_is("AWS::StepFunctions::StateMachine", 1)

    def test_stack_instantiates_with_prod_context(self):
        """Stack instantiates cleanly with prod context."""
        app = cdk.App(context={"environment": "prod"})
        stack = CdkBaseStack(app, "ProdTestStack")
        template = assertions.Template.from_stack(stack)
        template.resource_count_is("AWS::StepFunctions::StateMachine", 1)

    def test_stack_defaults_to_dev_without_context(self):
        """Stack defaults to dev behavior when no environment context is set."""
        app = cdk.App()
        stack = CdkBaseStack(app, "DefaultStack")
        template = assertions.Template.from_stack(stack)
        # Should use dev defaults (7-day log retention)
        template.has_resource_properties(
            "AWS::Logs::LogGroup",
            {"RetentionInDays": 7},
        )


class TestDynamoDBBillingMode:
    """DynamoDB billing mode is PAY_PER_REQUEST for all environments."""

    def test_dev_dynamodb_on_demand(self, dev_template):
        """Dev environment uses on-demand billing."""
        dev_template.has_resource_properties(
            "AWS::DynamoDB::Table",
            {"BillingMode": "PAY_PER_REQUEST"},
        )

    def test_stage_dynamodb_on_demand(self, stage_template):
        """Stage environment uses on-demand billing."""
        stage_template.has_resource_properties(
            "AWS::DynamoDB::Table",
            {"BillingMode": "PAY_PER_REQUEST"},
        )

    def test_prod_dynamodb_on_demand(self, prod_template):
        """Prod environment uses on-demand billing."""
        prod_template.has_resource_properties(
            "AWS::DynamoDB::Table",
            {"BillingMode": "PAY_PER_REQUEST"},
        )


class TestInvalidEnvironmentValidation:
    """Unrecognized environment values raise a ValueError."""

    def test_invalid_environment_raises_value_error(self):
        """An unrecognized environment value raises ValueError."""
        app = cdk.App(context={"environment": "typo"})
        with pytest.raises(ValueError, match="Unrecognized environment 'typo'"):
            CdkBaseStack(app, "InvalidStack")

    def test_staging_typo_raises_value_error(self):
        """Common typo 'staging' instead of 'stage' raises ValueError."""
        app = cdk.App(context={"environment": "staging"})
        with pytest.raises(ValueError, match="Unrecognized environment 'staging'"):
            CdkBaseStack(app, "StagingTypoStack")

    def test_error_message_lists_valid_environments(self):
        """The error message lists the valid environment values."""
        app = cdk.App(context={"environment": "invalid"})
        with pytest.raises(ValueError, match="dev, prod, stage"):
            CdkBaseStack(app, "InvalidListStack")
