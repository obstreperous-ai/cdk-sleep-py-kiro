"""Tests for error handling, retry policies, and observability features.

TDD tests covering:
- Retry policies on WriteInitialRecord, ProcessAudio, and PollyTask
- Specific error type catches (Lambda.ServiceException, States.TaskFailed, etc.)
- X-Ray tracing on Lambda and state machine
- CloudWatch Alarms for execution failures and Lambda errors
- Structured logging in Lambda handler
"""

import json

from aws_cdk.assertions import Match


def _get_state_definition_text(template):
    """Helper to get the flattened state machine definition text."""
    sm_resources = template.find_resources("AWS::StepFunctions::StateMachine")
    resource = list(sm_resources.values())[0]
    definition_str = resource["Properties"]["DefinitionString"]
    # The definition is usually an Fn::Join intrinsic; flatten parts to text
    if isinstance(definition_str, dict) and "Fn::Join" in definition_str:
        parts = definition_str["Fn::Join"][1]
        return "".join(
            str(p) if isinstance(p, str) else json.dumps(p) for p in parts
        )
    return json.dumps(definition_str)


def _get_state_section(definition_text, state_name):
    """Extract the section for a specific state from the definition text.

    Looks for the pattern '"StateName":{"Next"...' or '"StateName":{"Type"...'
    which is the actual state definition (not a reference in Next/StartAt).
    """
    # Find the state definition: "StateName":{"
    marker = f'"{state_name}":{{"'
    idx = definition_text.index(marker)
    # Find the end - look for the next state at the same nesting level
    # A simple heuristic: find the next '","<StateName>":{"' pattern
    # We'll grab a generous chunk since states can be large
    section = definition_text[idx:idx + 2000]
    return section


# --- Retry Policy Tests ---


def test_write_initial_record_has_retry_policy(template):
    """WriteInitialRecord task should have a Retry configuration."""
    definition_text = _get_state_definition_text(template)
    section = _get_state_section(definition_text, "WriteInitialRecord")
    assert "Retry" in section, (
        "WriteInitialRecord task must have a Retry configuration"
    )


def test_write_initial_record_retry_parameters(template):
    """WriteInitialRecord retry should have interval=2s, max_attempts=3, backoff_rate=2.0."""
    definition_text = _get_state_definition_text(template)
    section = _get_state_section(definition_text, "WriteInitialRecord")

    assert '"IntervalSeconds":2' in section
    assert '"MaxAttempts":3' in section
    assert '"BackoffRate":2' in section


def test_process_audio_has_retry_policy(template):
    """ProcessAudio task should have a Retry configuration."""
    definition_text = _get_state_definition_text(template)
    section = _get_state_section(definition_text, "ProcessAudio")
    assert "Retry" in section, (
        "ProcessAudio task must have a Retry configuration"
    )


def test_process_audio_retry_parameters(template):
    """ProcessAudio retry should have interval=2s, max_attempts=3, backoff_rate=2.0."""
    definition_text = _get_state_definition_text(template)
    section = _get_state_section(definition_text, "ProcessAudio")

    assert '"IntervalSeconds":2' in section
    assert '"MaxAttempts":3' in section
    assert '"BackoffRate":2' in section


def test_polly_task_has_retry_policy(template):
    """PollyTask should have a Retry configuration."""
    definition_text = _get_state_definition_text(template)
    section = _get_state_section(definition_text, "PollyTask")
    assert "Retry" in section, (
        "PollyTask must have a Retry configuration"
    )


def test_polly_task_retry_parameters(template):
    """PollyTask retry should have interval=5s, max_attempts=3, backoff_rate=2.0."""
    definition_text = _get_state_definition_text(template)
    section = _get_state_section(definition_text, "PollyTask")

    assert '"IntervalSeconds":5' in section
    assert '"MaxAttempts":3' in section
    assert '"BackoffRate":2' in section


# --- Specific Error Type Catches ---


def test_process_audio_catches_lambda_service_exception(template):
    """ProcessAudio should catch Lambda.ServiceException specifically."""
    definition_text = _get_state_definition_text(template)
    section = _get_state_section(definition_text, "ProcessAudio")

    assert "Lambda.ServiceException" in section, (
        "ProcessAudio must catch Lambda.ServiceException"
    )


def test_process_audio_catches_lambda_aws_exception(template):
    """ProcessAudio should catch Lambda.AWSLambdaException."""
    definition_text = _get_state_definition_text(template)
    section = _get_state_section(definition_text, "ProcessAudio")

    assert "Lambda.AWSLambdaException" in section, (
        "ProcessAudio must catch Lambda.AWSLambdaException"
    )


def test_process_audio_catches_lambda_sdk_client_exception(template):
    """ProcessAudio should catch Lambda.SdkClientException."""
    definition_text = _get_state_definition_text(template)
    section = _get_state_section(definition_text, "ProcessAudio")

    assert "Lambda.SdkClientException" in section, (
        "ProcessAudio must catch Lambda.SdkClientException"
    )


def test_polly_task_catches_states_task_failed(template):
    """PollyTask should catch States.TaskFailed specifically."""
    definition_text = _get_state_definition_text(template)
    section = _get_state_section(definition_text, "PollyTask")

    assert "States.TaskFailed" in section, (
        "PollyTask must catch States.TaskFailed"
    )


def test_process_audio_catches_states_all_fallback(template):
    """ProcessAudio should have States.ALL as a fallback catch for application errors."""
    definition_text = _get_state_definition_text(template)
    section = _get_state_section(definition_text, "ProcessAudio")

    assert "States.ALL" in section, (
        "ProcessAudio must have States.ALL fallback catch for application errors"
    )


def test_polly_task_catches_states_all_fallback(template):
    """PollyTask should have States.ALL as a fallback catch for unexpected errors."""
    definition_text = _get_state_definition_text(template)
    section = _get_state_section(definition_text, "PollyTask")

    assert "States.ALL" in section, (
        "PollyTask must have States.ALL fallback catch for unexpected errors"
    )


def test_normalize_caught_error_state_exists(template):
    """NormalizeCaughtError Pass state should exist to normalize error payloads."""
    definition_text = _get_state_definition_text(template)
    assert "NormalizeCaughtError" in definition_text, (
        "NormalizeCaughtError state must exist in state machine definition"
    )


def test_normalize_validation_error_state_exists(template):
    """NormalizeValidationError Pass state should exist to normalize validation failure payloads."""
    definition_text = _get_state_definition_text(template)
    assert "NormalizeValidationError" in definition_text, (
        "NormalizeValidationError state must exist in state machine definition"
    )


def test_publish_failed_notification_uses_normalized_reason(template):
    """PublishFailedNotification should reference $.failureReason (normalized) not $.processAudioResult.Payload.validationError."""
    definition_text = _get_state_definition_text(template)
    section = _get_state_section(definition_text, "PublishFailedNotification")

    assert "$.failureReason" in section, (
        "PublishFailedNotification must use $.failureReason for the error reason"
    )
    assert "$.processAudioResult.Payload.validationError" not in section, (
        "PublishFailedNotification must not directly reference $.processAudioResult.Payload.validationError"
    )


# --- X-Ray Tracing Tests ---


def test_lambda_has_xray_tracing_active(template):
    """Lambda function should have X-Ray tracing enabled (Mode=Active)."""
    template.has_resource_properties(
        "AWS::Lambda::Function",
        {
            "TracingConfig": {
                "Mode": "Active",
            }
        },
    )


def test_state_machine_has_xray_tracing_enabled(template):
    """State machine should have X-Ray tracing enabled."""
    template.has_resource_properties(
        "AWS::StepFunctions::StateMachine",
        {
            "TracingConfiguration": {
                "Enabled": True,
            }
        },
    )


# --- CloudWatch Alarms Tests ---


def test_cloudwatch_alarms_exist(template):
    """At least 2 CloudWatch Alarms should exist (state machine failures, Lambda errors)."""
    alarms = template.find_resources("AWS::CloudWatch::Alarm")
    assert len(alarms) >= 2, (
        f"Expected at least 2 CloudWatch Alarms, found {len(alarms)}"
    )


def test_state_machine_execution_failures_alarm(template):
    """A CloudWatch Alarm should monitor state machine ExecutionsFailed metric."""
    template.has_resource_properties(
        "AWS::CloudWatch::Alarm",
        {
            "MetricName": "ExecutionsFailed",
            "Namespace": "AWS/States",
            "Threshold": 1,
            "ComparisonOperator": "GreaterThanOrEqualToThreshold",
            "EvaluationPeriods": 1,
            "Period": 300,
            "Statistic": "Sum",
        },
    )


def test_lambda_errors_alarm(template):
    """A CloudWatch Alarm should monitor Lambda Errors metric."""
    template.has_resource_properties(
        "AWS::CloudWatch::Alarm",
        {
            "MetricName": "Errors",
            "Namespace": "AWS/Lambda",
            "Threshold": 1,
            "ComparisonOperator": "GreaterThanOrEqualToThreshold",
            "EvaluationPeriods": 1,
            "Period": 300,
            "Statistic": "Sum",
        },
    )


# --- Structured Logging Tests ---


def test_lambda_handler_structured_logging():
    """Lambda handler should emit structured JSON logs with request ID."""
    import sys
    import os
    from unittest.mock import patch, MagicMock

    # Add the lambda directory to path so we can import the handler
    lambda_dir = os.path.join(
        os.path.dirname(__file__), "..", "..", "lambda", "sleep_audio_processor"
    )
    sys.path.insert(0, lambda_dir)

    import handler
    from handler import lambda_handler

    class MockContext:
        aws_request_id = "test-request-id-12345"
        function_name = "test-function"
        memory_limit_in_mb = 128
        invoked_function_arn = "arn:aws:lambda:us-east-1:123456789:function:test"

    event = {
        "bucket": {"name": "test-bucket"},
        "object": {"key": "test-audio.mp3"},
    }

    mock_s3 = MagicMock()
    mock_polly = MagicMock()
    mock_dynamodb = MagicMock()
    mock_s3.download_file.return_value = None
    mock_s3.upload_file.return_value = None
    mock_dynamodb.update_item.return_value = {}

    with patch.object(handler, "s3_client", mock_s3), \
         patch.object(handler, "polly_client", mock_polly), \
         patch.object(handler, "dynamodb_client", mock_dynamodb):
        result = lambda_handler(event, MockContext())

    assert result["audioId"] == "test-audio.mp3"
    assert result["valid"] is True
    # The handler should include requestId in the response
    assert "requestId" in result, (
        "Lambda handler must include requestId in the response for traceability"
    )
    assert result["requestId"] == "test-request-id-12345"

    # Clean up sys.path
    sys.path.remove(lambda_dir)
