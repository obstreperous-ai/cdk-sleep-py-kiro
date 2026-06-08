"""End-to-end pipeline wiring tests.

Tests verify the complete pipeline from EventBridge through to terminal states,
including all required states in correct order, IAM permissions, and event patterns.
"""

import json

from aws_cdk.assertions import Match


class TestCompletePipelineWiring:
    """Tests for the complete pipeline state ordering."""

    def test_state_machine_has_all_required_states(self, template):
        """The state machine contains all required states."""
        sm_resources = template.find_resources("AWS::StepFunctions::StateMachine")
        resource = list(sm_resources.values())[0]
        definition_text = json.dumps(resource["Properties"]["DefinitionString"])

        required_states = [
            "WriteInitialRecord",
            "ProcessAudio",
            "ValidateInput",
            "PollyTask",
            "UpdateStatusCompleted",
            "PublishCompletedNotification",
            "Done",
        ]
        for state in required_states:
            assert state in definition_text, (
                f"State machine must contain state: {state}"
            )

    def test_happy_path_state_ordering(self, template):
        """States appear in correct order: WriteInitialRecord -> ProcessAudio -> ValidateInput -> PollyTask -> UpdateStatusCompleted -> PublishCompletedNotification -> Done."""
        sm_resources = template.find_resources("AWS::StepFunctions::StateMachine")
        resource = list(sm_resources.values())[0]
        definition_text = json.dumps(resource["Properties"]["DefinitionString"])

        positions = {
            "WriteInitialRecord": definition_text.index("WriteInitialRecord"),
            "ProcessAudio": definition_text.index("ProcessAudio"),
            "ValidateInput": definition_text.index("ValidateInput"),
            "PollyTask": definition_text.index("PollyTask"),
            "UpdateStatusCompleted": definition_text.index("UpdateStatusCompleted"),
            "PublishCompletedNotification": definition_text.index(
                "PublishCompletedNotification"
            ),
            "Done": definition_text.index("Done"),
        }

        ordered = [
            "WriteInitialRecord",
            "ProcessAudio",
            "ValidateInput",
            "PollyTask",
            "UpdateStatusCompleted",
            "PublishCompletedNotification",
            "Done",
        ]
        for i in range(len(ordered) - 1):
            assert positions[ordered[i]] < positions[ordered[i + 1]], (
                f"{ordered[i]} must appear before {ordered[i + 1]}"
            )

    def test_failure_path_states_exist(self, template):
        """State machine has failure path states: UpdateStatusFailed -> PublishFailedNotification -> Fail."""
        sm_resources = template.find_resources("AWS::StepFunctions::StateMachine")
        resource = list(sm_resources.values())[0]
        definition_text = json.dumps(resource["Properties"]["DefinitionString"])

        failure_states = [
            "UpdateStatusFailed",
            "PublishFailedNotification",
            "Fail",
        ]
        for state in failure_states:
            assert state in definition_text, (
                f"State machine must contain failure state: {state}"
            )


class TestIAMPermissions:
    """Tests for IAM permissions covering all required services."""

    def test_dynamodb_permissions_exist(self, template):
        """IAM policies include DynamoDB permissions."""
        template.has_resource_properties(
            "AWS::IAM::Policy",
            {
                "PolicyDocument": {
                    "Statement": Match.array_with(
                        [
                            Match.object_like(
                                {
                                    "Action": Match.array_with(
                                        ["dynamodb:PutItem"]
                                    ),
                                    "Effect": "Allow",
                                }
                            )
                        ]
                    )
                }
            },
        )

    def test_lambda_invoke_permissions_exist(self, template):
        """IAM policies include Lambda invoke permissions."""
        template.has_resource_properties(
            "AWS::IAM::Policy",
            {
                "PolicyDocument": {
                    "Statement": Match.array_with(
                        [
                            Match.object_like(
                                {
                                    "Action": "lambda:InvokeFunction",
                                    "Effect": "Allow",
                                }
                            )
                        ]
                    )
                }
            },
        )

    def test_polly_permissions_exist(self, template):
        """IAM policies include Polly permissions."""
        template.has_resource_properties(
            "AWS::IAM::Policy",
            {
                "PolicyDocument": {
                    "Statement": Match.array_with(
                        [
                            Match.object_like(
                                {
                                    "Action": "polly:startSpeechSynthesisTask",
                                    "Effect": "Allow",
                                }
                            )
                        ]
                    )
                }
            },
        )

    def test_sns_publish_permissions_exist(self, template):
        """IAM policies include SNS publish permissions."""
        template.has_resource_properties(
            "AWS::IAM::Policy",
            {
                "PolicyDocument": {
                    "Statement": Match.array_with(
                        [
                            Match.object_like(
                                {
                                    "Action": "sns:Publish",
                                    "Effect": "Allow",
                                }
                            )
                        ]
                    )
                }
            },
        )

    def test_kms_permissions_exist(self, template):
        """IAM policies include KMS permissions for encrypted SNS topics."""
        template.has_resource_properties(
            "AWS::IAM::Policy",
            {
                "PolicyDocument": {
                    "Statement": Match.array_with(
                        [
                            Match.object_like(
                                {
                                    "Action": Match.array_with(
                                        ["kms:GenerateDataKey*"]
                                    ),
                                    "Effect": "Allow",
                                }
                            )
                        ]
                    )
                }
            },
        )


class TestEventBridgeWiring:
    """Tests for EventBridge rule and target configuration."""

    def test_eventbridge_rule_matches_s3_object_created(self, template):
        """EventBridge rule matches S3 Object Created events."""
        template.has_resource_properties(
            "AWS::Events::Rule",
            {
                "EventPattern": Match.object_like(
                    {
                        "source": ["aws.s3"],
                        "detail-type": ["Object Created"],
                    }
                ),
            },
        )

    def test_eventbridge_target_passes_detail_as_input(self, template):
        """EventBridge target passes $.detail as input to the state machine."""
        template.has_resource_properties(
            "AWS::Events::Rule",
            {
                "Targets": Match.array_with(
                    [
                        Match.object_like(
                            {
                                "InputPath": "$.detail",
                            }
                        )
                    ]
                ),
            },
        )

    def test_eventbridge_rule_has_bucket_filter(self, template):
        """EventBridge rule filters for the specific input bucket."""
        template.has_resource_properties(
            "AWS::Events::Rule",
            {
                "EventPattern": Match.object_like(
                    {
                        "detail": Match.object_like(
                            {
                                "bucket": Match.object_like(
                                    {
                                        "name": Match.any_value(),
                                    }
                                )
                            }
                        ),
                    }
                ),
            },
        )
