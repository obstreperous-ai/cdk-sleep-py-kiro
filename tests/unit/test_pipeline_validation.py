"""TDD tests for input validation in the pipeline.

Tests cover:
- ValidateInput Choice state existence and positioning in the state machine
- Lambda handler file extension validation
- Error paths for invalid files
"""

import json
import os
import sys
from unittest.mock import patch, MagicMock
from io import BytesIO

import pytest

from aws_cdk.assertions import Match

# Add the Lambda source directory to the path so we can import the handler
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "..", "lambda", "sleep_audio_processor")
)

import handler  # noqa: E402
from handler import lambda_handler  # noqa: E402


@pytest.fixture
def lambda_context():
    """Minimal mock Lambda context."""

    class Context:
        function_name = "SleepAudioProcessor"
        memory_limit_in_mb = 128
        invoked_function_arn = (
            "arn:aws:lambda:us-east-1:123456789012:function:SleepAudioProcessor"
        )
        aws_request_id = "test-request-id"

    return Context()


@pytest.fixture(autouse=True)
def mock_clients():
    """Mock boto3 clients to avoid real AWS calls for valid file processing."""
    mock_s3 = MagicMock()
    mock_polly = MagicMock()
    mock_dynamodb = MagicMock()
    mock_s3.download_file.return_value = None
    mock_s3.upload_file.return_value = None
    mock_s3.get_object.return_value = {"Body": BytesIO(b"text content")}
    mock_polly.synthesize_speech.return_value = {
        "AudioStream": BytesIO(b"audio-data"),
        "ContentType": "audio/mpeg",
    }
    mock_s3.upload_fileobj.return_value = None
    mock_dynamodb.update_item.return_value = {}

    with patch.object(handler, "s3_client", mock_s3), \
         patch.object(handler, "polly_client", mock_polly), \
         patch.object(handler, "dynamodb_client", mock_dynamodb):
        yield


class TestValidateInputChoiceState:
    """Tests for the ValidateInput Choice state in the state machine."""

    def test_state_machine_has_validate_input_state(self, template):
        """The state machine definition contains a ValidateInput state."""
        sm_resources = template.find_resources("AWS::StepFunctions::StateMachine")
        assert len(sm_resources) == 1
        resource = list(sm_resources.values())[0]
        definition_text = json.dumps(resource["Properties"]["DefinitionString"])
        assert "ValidateInput" in definition_text

    def test_validate_input_is_choice_state(self, template):
        """The ValidateInput state is a Choice type."""
        sm_resources = template.find_resources("AWS::StepFunctions::StateMachine")
        resource = list(sm_resources.values())[0]
        definition_str = resource["Properties"]["DefinitionString"]
        if isinstance(definition_str, dict) and "Fn::Join" in definition_str:
            parts = definition_str["Fn::Join"][1]
            resolved = "".join(
                str(p) if isinstance(p, str) else json.dumps(p) for p in parts
            )
        else:
            resolved = json.dumps(definition_str)

        # Find ValidateInput state definition
        state_marker = '"ValidateInput":{'
        assert state_marker in resolved, (
            "Could not find ValidateInput state definition"
        )
        state_start = resolved.index(state_marker)
        section_after = resolved[state_start : state_start + 500]
        assert '"Type":"Choice"' in section_after, (
            "ValidateInput must be a Choice state type"
        )

    def test_validate_input_after_process_audio_before_polly(self, template):
        """ValidateInput appears after ProcessAudio and before PollyTask."""
        sm_resources = template.find_resources("AWS::StepFunctions::StateMachine")
        resource = list(sm_resources.values())[0]
        definition_text = json.dumps(resource["Properties"]["DefinitionString"])
        process_pos = definition_text.index("ProcessAudio")
        validate_pos = definition_text.index("ValidateInput")
        polly_pos = definition_text.index("PollyTask")
        assert process_pos < validate_pos, (
            "ProcessAudio must appear before ValidateInput"
        )
        assert validate_pos < polly_pos, (
            "ValidateInput must appear before PollyTask"
        )

    def test_validate_input_checks_valid_field(self, template):
        """ValidateInput checks $.processAudioResult.Payload.valid."""
        sm_resources = template.find_resources("AWS::StepFunctions::StateMachine")
        resource = list(sm_resources.values())[0]
        definition_str = resource["Properties"]["DefinitionString"]
        if isinstance(definition_str, dict) and "Fn::Join" in definition_str:
            parts = definition_str["Fn::Join"][1]
            resolved = "".join(
                str(p) if isinstance(p, str) else json.dumps(p) for p in parts
            )
        else:
            resolved = json.dumps(definition_str)

        # The Choice state should reference the valid field from Lambda output
        assert "$.processAudioResult.Payload.valid" in resolved, (
            "ValidateInput must check $.processAudioResult.Payload.valid"
        )

    def test_validate_input_routes_invalid_to_update_status_failed(self, template):
        """ValidateInput routes invalid files to UpdateStatusFailed."""
        sm_resources = template.find_resources("AWS::StepFunctions::StateMachine")
        resource = list(sm_resources.values())[0]
        definition_str = resource["Properties"]["DefinitionString"]
        if isinstance(definition_str, dict) and "Fn::Join" in definition_str:
            parts = definition_str["Fn::Join"][1]
            resolved = "".join(
                str(p) if isinstance(p, str) else json.dumps(p) for p in parts
            )
        else:
            resolved = json.dumps(definition_str)

        # Find ValidateInput state and check it has a Default going to UpdateStatusFailed
        state_marker = '"ValidateInput":{'
        state_start = resolved.index(state_marker)
        section_after = resolved[state_start : state_start + 600]
        assert "UpdateStatusFailed" in section_after, (
            "ValidateInput must route invalid inputs to UpdateStatusFailed"
        )

    def test_validate_input_routes_valid_to_polly(self, template):
        """ValidateInput routes valid files to PollyTask."""
        sm_resources = template.find_resources("AWS::StepFunctions::StateMachine")
        resource = list(sm_resources.values())[0]
        definition_str = resource["Properties"]["DefinitionString"]
        if isinstance(definition_str, dict) and "Fn::Join" in definition_str:
            parts = definition_str["Fn::Join"][1]
            resolved = "".join(
                str(p) if isinstance(p, str) else json.dumps(p) for p in parts
            )
        else:
            resolved = json.dumps(definition_str)

        # Find ValidateInput state and check it routes to PollyTask
        state_marker = '"ValidateInput":{'
        state_start = resolved.index(state_marker)
        section_after = resolved[state_start : state_start + 600]
        assert "PollyTask" in section_after, (
            "ValidateInput must route valid inputs to PollyTask"
        )


class TestLambdaFileExtensionValidation:
    """Tests for file extension validation in the Lambda handler."""

    def test_valid_mp3_extension(self, lambda_context):
        """Handler returns valid=True for .mp3 files."""
        event = {"bucket": {"name": "my-bucket"}, "object": {"key": "audio/song.mp3"}}
        result = lambda_handler(event, lambda_context)
        assert result["valid"] is True

    def test_valid_wav_extension(self, lambda_context):
        """Handler returns valid=True for .wav files."""
        event = {"bucket": {"name": "my-bucket"}, "object": {"key": "audio/song.wav"}}
        result = lambda_handler(event, lambda_context)
        assert result["valid"] is True

    def test_valid_ogg_extension(self, lambda_context):
        """Handler returns valid=True for .ogg files."""
        event = {"bucket": {"name": "my-bucket"}, "object": {"key": "audio/song.ogg"}}
        result = lambda_handler(event, lambda_context)
        assert result["valid"] is True

    def test_valid_flac_extension(self, lambda_context):
        """Handler returns valid=True for .flac files."""
        event = {"bucket": {"name": "my-bucket"}, "object": {"key": "audio/song.flac"}}
        result = lambda_handler(event, lambda_context)
        assert result["valid"] is True

    def test_valid_txt_extension(self, lambda_context):
        """Handler returns valid=True for .txt files (processed via Polly)."""
        event = {"bucket": {"name": "my-bucket"}, "object": {"key": "audio/notes.txt"}}
        result = lambda_handler(event, lambda_context)
        assert result["valid"] is True

    def test_invalid_pdf_extension(self, lambda_context):
        """Handler returns valid=False for .pdf files."""
        event = {"bucket": {"name": "my-bucket"}, "object": {"key": "docs/report.pdf"}}
        result = lambda_handler(event, lambda_context)
        assert result["valid"] is False

    def test_invalid_extension_returns_validation_error(self, lambda_context):
        """Handler returns validationError message for unsupported extensions."""
        event = {"bucket": {"name": "my-bucket"}, "object": {"key": "file.pdf"}}
        result = lambda_handler(event, lambda_context)
        assert "validationError" in result
        assert ".pdf" in result["validationError"]

    def test_valid_extension_no_validation_error(self, lambda_context):
        """Handler does not return validationError for valid extensions."""
        event = {"bucket": {"name": "my-bucket"}, "object": {"key": "audio/song.mp3"}}
        result = lambda_handler(event, lambda_context)
        assert "validationError" not in result

    def test_case_insensitive_extension(self, lambda_context):
        """Handler accepts extensions regardless of case."""
        event = {"bucket": {"name": "my-bucket"}, "object": {"key": "audio/song.MP3"}}
        result = lambda_handler(event, lambda_context)
        assert result["valid"] is True

    def test_missing_fields_still_raises_value_error(self, lambda_context):
        """Handler still raises ValueError for missing required fields."""
        event = {"bucket": {"name": ""}, "object": {"key": "file.mp3"}}
        with pytest.raises(ValueError, match="Missing required fields"):
            lambda_handler(event, lambda_context)

    def test_no_extension_returns_invalid(self, lambda_context):
        """Handler returns valid=False for files with no extension."""
        event = {"bucket": {"name": "my-bucket"}, "object": {"key": "audio/noextension"}}
        result = lambda_handler(event, lambda_context)
        assert result["valid"] is False
        assert "(none)" in result["validationError"]
