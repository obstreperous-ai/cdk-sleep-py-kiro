"""Unit tests for the SleepAudioProcessor Lambda handler."""

import sys
import os

import pytest

# Add the Lambda source directory to the path so we can import the handler
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "..", "lambda", "sleep_audio_processor")
)

from handler import lambda_handler  # noqa: E402


@pytest.fixture
def valid_event():
    """Return a well-formed event matching state machine input."""
    return {
        "bucket": {"name": "my-input-bucket"},
        "object": {"key": "audio/test-file.mp3"},
    }


@pytest.fixture
def lambda_context():
    """Minimal mock Lambda context."""

    class Context:
        function_name = "SleepAudioProcessor"
        memory_limit_in_mb = 128
        invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:SleepAudioProcessor"
        aws_request_id = "test-request-id"

    return Context()


class TestLambdaHandlerSuccess:
    """Tests for the happy path."""

    def test_returns_processed_status(self, valid_event, lambda_context):
        """Handler returns processorStatus PROCESSED for valid input."""
        result = lambda_handler(valid_event, lambda_context)
        assert result["processorStatus"] == "PROCESSED"

    def test_returns_audio_id(self, valid_event, lambda_context):
        """Handler returns the object key as audioId."""
        result = lambda_handler(valid_event, lambda_context)
        assert result["audioId"] == "audio/test-file.mp3"

    def test_returns_bucket_name(self, valid_event, lambda_context):
        """Handler returns the bucket name."""
        result = lambda_handler(valid_event, lambda_context)
        assert result["bucket"] == "my-input-bucket"

    def test_returns_table_name(self, valid_event, lambda_context, monkeypatch):
        """Handler returns the TABLE_NAME from environment."""
        monkeypatch.setenv("TABLE_NAME", "TestMetadataTable")
        # Re-import to pick up the new env var
        import importlib
        import handler

        importlib.reload(handler)
        result = handler.lambda_handler(valid_event, lambda_context)
        assert result["tableName"] == "TestMetadataTable"

    def test_returns_success_message(self, valid_event, lambda_context):
        """Handler returns a success message."""
        result = lambda_handler(valid_event, lambda_context)
        assert result["message"] == "Audio metadata enriched successfully"

    def test_ignores_extra_fields(self, lambda_context):
        """Handler ignores extra fields in the event (e.g., dynamoResult)."""
        event = {
            "bucket": {"name": "my-bucket"},
            "object": {"key": "file.mp3"},
            "dynamoResult": {"some": "data"},
        }
        result = lambda_handler(event, lambda_context)
        assert result["processorStatus"] == "PROCESSED"


class TestLambdaHandlerValidation:
    """Tests for input validation and error paths."""

    def test_raises_on_missing_object_key(self, lambda_context):
        """Handler raises ValueError when object.key is missing."""
        event = {"bucket": {"name": "my-bucket"}, "object": {}}
        with pytest.raises(ValueError, match="Missing required fields"):
            lambda_handler(event, lambda_context)

    def test_raises_on_missing_bucket_name(self, lambda_context):
        """Handler raises ValueError when bucket.name is missing."""
        event = {"bucket": {}, "object": {"key": "file.mp3"}}
        with pytest.raises(ValueError, match="Missing required fields"):
            lambda_handler(event, lambda_context)

    def test_raises_on_empty_object_key(self, lambda_context):
        """Handler raises ValueError when object.key is empty string."""
        event = {"bucket": {"name": "my-bucket"}, "object": {"key": ""}}
        with pytest.raises(ValueError, match="Missing required fields"):
            lambda_handler(event, lambda_context)

    def test_raises_on_empty_bucket_name(self, lambda_context):
        """Handler raises ValueError when bucket.name is empty string."""
        event = {"bucket": {"name": ""}, "object": {"key": "file.mp3"}}
        with pytest.raises(ValueError, match="Missing required fields"):
            lambda_handler(event, lambda_context)

    def test_raises_on_missing_object_entirely(self, lambda_context):
        """Handler raises ValueError when object field is missing entirely."""
        event = {"bucket": {"name": "my-bucket"}}
        with pytest.raises(ValueError, match="Missing required fields"):
            lambda_handler(event, lambda_context)

    def test_raises_on_missing_bucket_entirely(self, lambda_context):
        """Handler raises ValueError when bucket field is missing entirely."""
        event = {"object": {"key": "file.mp3"}}
        with pytest.raises(ValueError, match="Missing required fields"):
            lambda_handler(event, lambda_context)

    def test_raises_on_empty_event(self, lambda_context):
        """Handler raises ValueError on empty event dict."""
        with pytest.raises(ValueError, match="Missing required fields"):
            lambda_handler({}, lambda_context)


class TestLambdaHandlerMetadataFields:
    """Tests for handler returning complete metadata fields."""

    def test_returns_valid_true_with_all_required_fields(self, valid_event, lambda_context):
        """Handler returns valid=True with all required metadata fields."""
        result = lambda_handler(valid_event, lambda_context)
        required_fields = ["audioId", "bucket", "tableName", "processorStatus", "message", "valid"]
        for field in required_fields:
            assert field in result, f"Missing required field: {field}"
        assert result["valid"] is True

    def test_nested_path_keys_return_correct_audio_id(self, lambda_context):
        """Handler with nested path keys like 'folder/subfolder/file.wav' returns correct audioId."""
        event = {
            "bucket": {"name": "my-bucket"},
            "object": {"key": "folder/subfolder/file.wav"},
        }
        result = lambda_handler(event, lambda_context)
        assert result["audioId"] == "folder/subfolder/file.wav"
        assert result["valid"] is True
