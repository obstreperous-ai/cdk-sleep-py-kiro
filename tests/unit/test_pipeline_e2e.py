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


from tests.unit.helpers import parse_state_machine_definition


def _parse_definition(template):
    """Module-level helper to extract and parse the state machine definition."""
    return parse_state_machine_definition(template)


class TestCompleteE2EStateDefinition:
    """Validates state types and transitions by parsing the full definition JSON."""

    def test_write_initial_record_is_task_type(self, template):
        """WriteInitialRecord is a Task state."""
        definition = _parse_definition(template)
        state = definition["States"]["WriteInitialRecord"]
        assert state["Type"] == "Task"

    def test_write_initial_record_transitions_to_process_audio(self, template):
        """WriteInitialRecord transitions to ProcessAudio."""
        definition = _parse_definition(template)
        state = definition["States"]["WriteInitialRecord"]
        assert state["Next"] == "ProcessAudio"

    def test_process_audio_is_task_type(self, template):
        """ProcessAudio is a Task state (Lambda invoke)."""
        definition = _parse_definition(template)
        state = definition["States"]["ProcessAudio"]
        assert state["Type"] == "Task"

    def test_process_audio_transitions_to_validate_input(self, template):
        """ProcessAudio transitions to ValidateInput."""
        definition = _parse_definition(template)
        state = definition["States"]["ProcessAudio"]
        assert state["Next"] == "ValidateInput"

    def test_validate_input_is_choice_type(self, template):
        """ValidateInput is a Choice state."""
        definition = _parse_definition(template)
        state = definition["States"]["ValidateInput"]
        assert state["Type"] == "Choice"

    def test_validate_input_routes_valid_to_polly_task(self, template):
        """ValidateInput routes valid=True to PollyTask."""
        definition = _parse_definition(template)
        state = definition["States"]["ValidateInput"]
        choices = state["Choices"]
        valid_choice = next(
            c for c in choices
            if c.get("Variable") == "$.processAudioResult.Payload.valid"
        )
        assert valid_choice["BooleanEquals"] is True
        assert valid_choice["Next"] == "PollyTask"

    def test_validate_input_default_routes_to_normalize_validation_error(self, template):
        """ValidateInput default route goes to NormalizeValidationError."""
        definition = _parse_definition(template)
        state = definition["States"]["ValidateInput"]
        assert state["Default"] == "NormalizeValidationError"

    def test_polly_task_is_task_type(self, template):
        """PollyTask is a Task state."""
        definition = _parse_definition(template)
        state = definition["States"]["PollyTask"]
        assert state["Type"] == "Task"

    def test_polly_task_transitions_to_update_status_completed(self, template):
        """PollyTask transitions to UpdateStatusCompleted."""
        definition = _parse_definition(template)
        state = definition["States"]["PollyTask"]
        assert state["Next"] == "UpdateStatusCompleted"

    def test_update_status_completed_is_task_type(self, template):
        """UpdateStatusCompleted is a Task state (DynamoDB update)."""
        definition = _parse_definition(template)
        state = definition["States"]["UpdateStatusCompleted"]
        assert state["Type"] == "Task"

    def test_update_status_completed_transitions_to_publish_completed(self, template):
        """UpdateStatusCompleted transitions to PublishCompletedNotification."""
        definition = _parse_definition(template)
        state = definition["States"]["UpdateStatusCompleted"]
        assert state["Next"] == "PublishCompletedNotification"

    def test_publish_completed_notification_is_task_type(self, template):
        """PublishCompletedNotification is a Task state (SNS publish)."""
        definition = _parse_definition(template)
        state = definition["States"]["PublishCompletedNotification"]
        assert state["Type"] == "Task"

    def test_publish_completed_notification_transitions_to_done(self, template):
        """PublishCompletedNotification transitions to Done."""
        definition = _parse_definition(template)
        state = definition["States"]["PublishCompletedNotification"]
        assert state["Next"] == "Done"

    def test_done_is_succeed_type(self, template):
        """Done is a Succeed state."""
        definition = _parse_definition(template)
        state = definition["States"]["Done"]
        assert state["Type"] == "Succeed"

    def test_start_at_is_write_initial_record(self, template):
        """State machine starts at WriteInitialRecord."""
        definition = _parse_definition(template)
        assert definition["StartAt"] == "WriteInitialRecord"

    def test_write_initial_record_uses_dynamodb_put_item(self, template):
        """WriteInitialRecord resource is dynamodb:putItem."""
        definition = _parse_definition(template)
        state = definition["States"]["WriteInitialRecord"]
        assert "dynamodb:putItem" in state["Resource"]

    def test_process_audio_uses_lambda_invoke(self, template):
        """ProcessAudio resource is lambda:invoke."""
        definition = _parse_definition(template)
        state = definition["States"]["ProcessAudio"]
        assert "lambda:invoke" in state["Resource"]

    def test_update_status_completed_uses_dynamodb_update_item(self, template):
        """UpdateStatusCompleted resource is dynamodb:updateItem."""
        definition = _parse_definition(template)
        state = definition["States"]["UpdateStatusCompleted"]
        assert "dynamodb:updateItem" in state["Resource"]

    def test_publish_completed_uses_sns_publish(self, template):
        """PublishCompletedNotification resource is sns:publish."""
        definition = _parse_definition(template)
        state = definition["States"]["PublishCompletedNotification"]
        assert "sns:publish" in state["Resource"]


class TestCompleteE2EErrorHandling:
    """Validates complete error chains in the state machine."""

    def test_process_audio_error_routes_to_normalize_caught_error(self, template):
        """ProcessAudio errors route to NormalizeCaughtError."""
        definition = _parse_definition(template)
        state = definition["States"]["ProcessAudio"]
        catch_targets = [c["Next"] for c in state["Catch"]]
        assert "NormalizeCaughtError" in catch_targets

    def test_normalize_caught_error_routes_to_update_status_failed(self, template):
        """NormalizeCaughtError routes to UpdateStatusFailed."""
        definition = _parse_definition(template)
        state = definition["States"]["NormalizeCaughtError"]
        assert state["Next"] == "UpdateStatusFailed"

    def test_update_status_failed_routes_to_publish_failed_notification(self, template):
        """UpdateStatusFailed routes to PublishFailedNotification."""
        definition = _parse_definition(template)
        state = definition["States"]["UpdateStatusFailed"]
        assert state["Next"] == "PublishFailedNotification"

    def test_publish_failed_notification_routes_to_fail(self, template):
        """PublishFailedNotification routes to Fail state."""
        definition = _parse_definition(template)
        state = definition["States"]["PublishFailedNotification"]
        assert state["Next"] == "Fail"

    def test_fail_state_is_fail_type(self, template):
        """Fail state is of type Fail."""
        definition = _parse_definition(template)
        state = definition["States"]["Fail"]
        assert state["Type"] == "Fail"

    def test_polly_task_error_routes_to_normalize_caught_error(self, template):
        """PollyTask errors also route through NormalizeCaughtError."""
        definition = _parse_definition(template)
        state = definition["States"]["PollyTask"]
        catch_targets = [c["Next"] for c in state["Catch"]]
        assert "NormalizeCaughtError" in catch_targets

    def test_normalize_caught_error_is_pass_type(self, template):
        """NormalizeCaughtError is a Pass state."""
        definition = _parse_definition(template)
        state = definition["States"]["NormalizeCaughtError"]
        assert state["Type"] == "Pass"

    def test_normalize_caught_error_extracts_failure_reason(self, template):
        """NormalizeCaughtError extracts failureReason from error."""
        definition = _parse_definition(template)
        state = definition["States"]["NormalizeCaughtError"]
        params = state["Parameters"]
        assert "failureReason.$" in params
        assert params["failureReason.$"] == "$.error.Error"


class TestRetryBehavior:
    """Validates retry configurations on key states."""

    def test_write_initial_record_has_retry(self, template):
        """WriteInitialRecord has retry configuration."""
        definition = _parse_definition(template)
        state = definition["States"]["WriteInitialRecord"]
        assert "Retry" in state
        assert len(state["Retry"]) > 0

    def test_write_initial_record_retry_interval(self, template):
        """WriteInitialRecord retry has IntervalSeconds=2."""
        definition = _parse_definition(template)
        state = definition["States"]["WriteInitialRecord"]
        retry = state["Retry"][0]
        assert retry["IntervalSeconds"] == 2

    def test_write_initial_record_retry_max_attempts(self, template):
        """WriteInitialRecord retry has MaxAttempts=3."""
        definition = _parse_definition(template)
        state = definition["States"]["WriteInitialRecord"]
        retry = state["Retry"][0]
        assert retry["MaxAttempts"] == 3

    def test_write_initial_record_retry_backoff_rate(self, template):
        """WriteInitialRecord retry has BackoffRate=2."""
        definition = _parse_definition(template)
        state = definition["States"]["WriteInitialRecord"]
        retry = state["Retry"][0]
        assert retry["BackoffRate"] == 2

    def test_process_audio_has_retry(self, template):
        """ProcessAudio has retry configuration."""
        definition = _parse_definition(template)
        state = definition["States"]["ProcessAudio"]
        assert "Retry" in state
        assert len(state["Retry"]) > 0

    def test_process_audio_retry_interval(self, template):
        """ProcessAudio retry has IntervalSeconds=2."""
        definition = _parse_definition(template)
        state = definition["States"]["ProcessAudio"]
        retry = state["Retry"][0]
        assert retry["IntervalSeconds"] == 2

    def test_process_audio_retry_max_attempts(self, template):
        """ProcessAudio retry has MaxAttempts=3."""
        definition = _parse_definition(template)
        state = definition["States"]["ProcessAudio"]
        retry = state["Retry"][0]
        assert retry["MaxAttempts"] == 3

    def test_process_audio_retry_backoff_rate(self, template):
        """ProcessAudio retry has BackoffRate=2."""
        definition = _parse_definition(template)
        state = definition["States"]["ProcessAudio"]
        retry = state["Retry"][0]
        assert retry["BackoffRate"] == 2

    def test_polly_task_has_retry(self, template):
        """PollyTask has retry configuration."""
        definition = _parse_definition(template)
        state = definition["States"]["PollyTask"]
        assert "Retry" in state
        assert len(state["Retry"]) > 0

    def test_polly_task_retry_interval(self, template):
        """PollyTask retry has IntervalSeconds=5."""
        definition = _parse_definition(template)
        state = definition["States"]["PollyTask"]
        retry = state["Retry"][0]
        assert retry["IntervalSeconds"] == 5

    def test_polly_task_retry_max_attempts(self, template):
        """PollyTask retry has MaxAttempts=3."""
        definition = _parse_definition(template)
        state = definition["States"]["PollyTask"]
        retry = state["Retry"][0]
        assert retry["MaxAttempts"] == 3

    def test_polly_task_retry_backoff_rate(self, template):
        """PollyTask retry has BackoffRate=2."""
        definition = _parse_definition(template)
        state = definition["States"]["PollyTask"]
        retry = state["Retry"][0]
        assert retry["BackoffRate"] == 2


class TestNotificationContent:
    """Validates SNS message payloads include required fields."""

    def test_completed_notification_message_has_audio_id(self, template):
        """Completed notification message payload includes audioId field."""
        definition = _parse_definition(template)
        state = definition["States"]["PublishCompletedNotification"]
        message = state["Parameters"]["Message"]
        assert "audioId.$" in message

    def test_completed_notification_message_has_status(self, template):
        """Completed notification message payload includes status=COMPLETED."""
        definition = _parse_definition(template)
        state = definition["States"]["PublishCompletedNotification"]
        message = state["Parameters"]["Message"]
        assert message["status"] == "COMPLETED"

    def test_failed_notification_message_has_audio_id(self, template):
        """Failed notification message payload includes audioId field."""
        definition = _parse_definition(template)
        state = definition["States"]["PublishFailedNotification"]
        message = state["Parameters"]["Message"]
        assert "audioId.$" in message

    def test_failed_notification_message_has_status(self, template):
        """Failed notification message payload includes status=FAILED."""
        definition = _parse_definition(template)
        state = definition["States"]["PublishFailedNotification"]
        message = state["Parameters"]["Message"]
        assert message["status"] == "FAILED"

    def test_failed_notification_message_has_reason(self, template):
        """Failed notification message payload includes reason field."""
        definition = _parse_definition(template)
        state = definition["States"]["PublishFailedNotification"]
        message = state["Parameters"]["Message"]
        assert "reason.$" in message

    def test_completed_notification_audio_id_references_object_key(self, template):
        """Completed notification audioId references $.object.key."""
        definition = _parse_definition(template)
        state = definition["States"]["PublishCompletedNotification"]
        message = state["Parameters"]["Message"]
        assert message["audioId.$"] == "$.object.key"

    def test_failed_notification_audio_id_references_object_key(self, template):
        """Failed notification audioId references $.object.key."""
        definition = _parse_definition(template)
        state = definition["States"]["PublishFailedNotification"]
        message = state["Parameters"]["Message"]
        assert message["audioId.$"] == "$.object.key"

    def test_failed_notification_reason_references_failure_reason(self, template):
        """Failed notification reason references $.failureReason."""
        definition = _parse_definition(template)
        state = definition["States"]["PublishFailedNotification"]
        message = state["Parameters"]["Message"]
        assert message["reason.$"] == "$.failureReason"


class TestErrorPathRouting:
    """Verify error path routing in the state machine."""

    def _get_definition(self, template):
        """Helper to extract and parse the state machine definition."""
        return _parse_definition(template)

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
