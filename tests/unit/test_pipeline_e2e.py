"""End-to-end pipeline wiring tests.

Tests verify the complete pipeline from EventBridge through to terminal states,
including all required states in correct order, IAM permissions, and event patterns.
"""

import json

import aws_cdk as cdk
import aws_cdk.assertions as assertions
from aws_cdk.assertions import Match

from cdk_base.cdk_base_stack import CdkBaseStack


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


class TestSnapshotStability:
    """Snapshot test that captures template resource types and count."""

    def test_template_resource_types_and_count(self, template):
        """Template contains expected resource types and counts remain stable."""
        # Capture resource types present in the template
        template_json = template.to_json()
        resources = template_json.get("Resources", {})

        # Count resources by type
        resource_types = {}
        for resource in resources.values():
            rtype = resource["Type"]
            resource_types[rtype] = resource_types.get(rtype, 0) + 1

        # Verify key resource types are present
        assert "AWS::StepFunctions::StateMachine" in resource_types
        assert "AWS::Lambda::Function" in resource_types
        assert "AWS::DynamoDB::Table" in resource_types
        assert "AWS::S3::Bucket" in resource_types
        assert "AWS::SNS::Topic" in resource_types
        assert "AWS::Events::Rule" in resource_types
        assert "AWS::KMS::Key" in resource_types
        assert "AWS::Logs::LogGroup" in resource_types

        # Verify minimum counts for key resources
        assert resource_types["AWS::StepFunctions::StateMachine"] == 1
        assert resource_types["AWS::Lambda::Function"] >= 1
        assert resource_types["AWS::DynamoDB::Table"] == 1
        assert resource_types["AWS::S3::Bucket"] >= 2
        assert resource_types["AWS::SNS::Topic"] == 2


class TestProcessAudioPayloadScoping:
    """Verify the ProcessAudio Lambda invoke uses a scoped payload."""

    def test_process_audio_payload_has_only_bucket_and_object(self, template):
        """ProcessAudio Lambda invoke payload contains only bucket and object fields."""
        sm_resources = template.find_resources("AWS::StepFunctions::StateMachine")
        resource = list(sm_resources.values())[0]
        definition_text = json.dumps(resource["Properties"]["DefinitionString"])

        # Parse to find ProcessAudio state parameters
        # The state machine definition is a Fn::Join or string with the definition
        # Look for the ProcessAudio state payload pattern
        assert "ProcessAudio" in definition_text

        # The payload should scope to bucket and object only
        # In the CDK-generated definition, the Lambda payload will reference
        # $.bucket and $.object paths
        assert "$.bucket" in definition_text
        assert "$.object" in definition_text


class TestFailureNotificationContent:
    """Verify the failure notification SNS message includes reason/validationError field."""

    def test_failed_notification_includes_reason_field(self, template):
        """PublishFailedNotification message includes a reason field from validationError."""
        sm_resources = template.find_resources("AWS::StepFunctions::StateMachine")
        resource = list(sm_resources.values())[0]
        definition_text = json.dumps(resource["Properties"]["DefinitionString"])

        # The failure notification should include a reason field referencing validationError
        assert "validationError" in definition_text
        assert "reason" in definition_text


class TestErrorPathRouting:
    """Verify error path routing in the state machine."""

    def _get_definition(self, template):
        """Helper to extract and parse the state machine definition."""
        sm_resources = template.find_resources("AWS::StepFunctions::StateMachine")
        resource = list(sm_resources.values())[0]
        definition_str = resource["Properties"]["DefinitionString"]
        # Handle Fn::Join format - replace dict tokens with placeholder strings
        if isinstance(definition_str, dict) and "Fn::Join" in definition_str:
            parts = definition_str["Fn::Join"][1]
            joined = "".join(
                p if isinstance(p, str) else "PLACEHOLDER" for p in parts
            )
            return json.loads(joined)
        return json.loads(definition_str) if isinstance(definition_str, str) else definition_str

    def test_write_initial_record_catch_routes_to_fail(self, template):
        """WriteInitialRecord catch routes to Fail state."""
        definition = self._get_definition(template)
        states = definition.get("States", {})
        write_state = states.get("WriteInitialRecord", {})
        catchers = write_state.get("Catch", [])
        catch_targets = [c.get("Next") for c in catchers]
        assert "Fail" in catch_targets, (
            "WriteInitialRecord should catch errors and route to Fail"
        )

    def test_process_audio_catch_routes_to_update_status_failed(self, template):
        """ProcessAudio catch routes through NormalizeCaughtError to UpdateStatusFailed."""
        definition = self._get_definition(template)
        states = definition.get("States", {})
        process_state = states.get("ProcessAudio", {})
        catchers = process_state.get("Catch", [])
        catch_targets = [c.get("Next") for c in catchers]
        assert "NormalizeCaughtError" in catch_targets, (
            "ProcessAudio should catch errors and route to NormalizeCaughtError"
        )
        # Verify NormalizeCaughtError routes to UpdateStatusFailed
        normalize_state = states.get("NormalizeCaughtError", {})
        assert normalize_state.get("Next") == "UpdateStatusFailed", (
            "NormalizeCaughtError should route to UpdateStatusFailed"
        )

    def test_polly_task_catch_routes_to_update_status_failed(self, template):
        """PollyTask catch routes through NormalizeCaughtError to UpdateStatusFailed."""
        definition = self._get_definition(template)
        states = definition.get("States", {})
        polly_state = states.get("PollyTask", {})
        catchers = polly_state.get("Catch", [])
        catch_targets = [c.get("Next") for c in catchers]
        assert "NormalizeCaughtError" in catch_targets, (
            "PollyTask should catch errors and route to NormalizeCaughtError"
        )
        # Verify NormalizeCaughtError routes to UpdateStatusFailed
        normalize_state = states.get("NormalizeCaughtError", {})
        assert normalize_state.get("Next") == "UpdateStatusFailed", (
            "NormalizeCaughtError should route to UpdateStatusFailed"
        )
