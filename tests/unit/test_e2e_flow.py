"""End-to-end flow tests for the complete Sleep Audio Pipeline.

Tests validate the full pipeline flow from input through output, covering:
- Happy path audio processing (download -> process -> upload -> structured response)
- Happy path text-to-speech (read text -> Polly synthesize -> upload)
- DynamoDB metadata tracking (FAILED updates on error, no updates on success)
- Error scenarios (S3 download failure, Polly failure, upload failure)
- Input validation (missing fields, unsupported extensions)
- State machine definition validation (state types, transitions, DynamoDB lifecycle)
- SNS notification scenarios (success and failure message formats)
"""

import json
import os
import sys
from io import BytesIO
from unittest.mock import MagicMock, patch, ANY

import pytest

# Add the Lambda source directory to the path
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "..", "lambda", "sleep_audio_processor")
)

import handler  # noqa: E402


# --- Fixtures ---


@pytest.fixture
def lambda_context():
    """Minimal mock Lambda context."""

    class Context:
        function_name = "SleepAudioProcessor"
        memory_limit_in_mb = 512
        invoked_function_arn = (
            "arn:aws:lambda:us-east-1:123456789012:function:SleepAudioProcessor"
        )
        aws_request_id = "e2e-test-request-id"

    return Context()


@pytest.fixture
def env_vars(monkeypatch):
    """Set required environment variables for the handler."""
    monkeypatch.setenv("OUTPUT_BUCKET", "output-bucket-e2e")
    monkeypatch.setenv("TABLE_NAME", "SleepAudioMetadataE2E")


@pytest.fixture
def mock_clients():
    """Mock all boto3 clients used by the handler."""
    mock_s3 = MagicMock()
    mock_polly = MagicMock()
    mock_dynamodb = MagicMock()

    with patch.object(handler, "s3_client", mock_s3), \
         patch.object(handler, "polly_client", mock_polly), \
         patch.object(handler, "dynamodb_client", mock_dynamodb):
        yield {
            "s3": mock_s3,
            "polly": mock_polly,
            "dynamodb": mock_dynamodb,
        }


# --- Helper to get state machine definition ---


def _get_definition(template):
    """Extract and parse the state machine definition from the synthesized template."""
    sm_resources = template.find_resources("AWS::StepFunctions::StateMachine")
    resource = list(sm_resources.values())[0]
    definition_str = resource["Properties"]["DefinitionString"]
    if isinstance(definition_str, dict) and "Fn::Join" in definition_str:
        parts = definition_str["Fn::Join"][1]
        joined = "".join(
            p if isinstance(p, str) else "PLACEHOLDER" for p in parts
        )
        return json.loads(joined)
    return json.loads(definition_str) if isinstance(definition_str, str) else definition_str


# --- Happy Path Audio Processing Tests ---


class TestHappyPathAudioProcessing:
    """Tests for successful audio file processing end-to-end flow."""

    @pytest.fixture(params=[".mp3", ".wav", ".ogg", ".flac"])
    def audio_event(self, request):
        """Parameterized events for all supported audio formats."""
        ext = request.param
        return {
            "bucket": {"name": "input-bucket-e2e"},
            "object": {"key": f"audio/test-file{ext}"},
        }

    def test_audio_file_downloads_from_input_bucket(
        self, audio_event, lambda_context, env_vars, mock_clients
    ):
        """Valid audio files are downloaded from the input S3 bucket."""
        mock_s3 = mock_clients["s3"]
        mock_s3.download_file.return_value = None
        mock_s3.upload_file.return_value = None

        handler.lambda_handler(audio_event, lambda_context)

        mock_s3.download_file.assert_called_once_with(
            "input-bucket-e2e",
            audio_event["object"]["key"],
            ANY,
        )

    def test_audio_file_uploads_to_output_bucket_with_processed_prefix(
        self, audio_event, lambda_context, env_vars, mock_clients
    ):
        """Processed audio files are uploaded to output bucket with processed/ prefix."""
        mock_s3 = mock_clients["s3"]
        mock_s3.download_file.return_value = None
        mock_s3.upload_file.return_value = None

        result = handler.lambda_handler(audio_event, lambda_context)

        mock_s3.upload_file.assert_called_once()
        call_args = mock_s3.upload_file.call_args[0]
        assert call_args[1] == "output-bucket-e2e"
        assert call_args[2].startswith("processed/")

    def test_audio_processing_returns_output_key(
        self, audio_event, lambda_context, env_vars, mock_clients
    ):
        """Lambda returns outputKey starting with processed/ prefix."""
        mock_s3 = mock_clients["s3"]
        mock_s3.download_file.return_value = None
        mock_s3.upload_file.return_value = None

        result = handler.lambda_handler(audio_event, lambda_context)

        assert "outputKey" in result
        assert result["outputKey"].startswith("processed/")

    def test_audio_processing_returns_output_bucket(
        self, audio_event, lambda_context, env_vars, mock_clients
    ):
        """Lambda returns outputBucket matching the configured output bucket."""
        mock_s3 = mock_clients["s3"]
        mock_s3.download_file.return_value = None
        mock_s3.upload_file.return_value = None

        result = handler.lambda_handler(audio_event, lambda_context)

        assert result["outputBucket"] == "output-bucket-e2e"

    def test_audio_processing_returns_file_size(
        self, audio_event, lambda_context, env_vars, mock_clients
    ):
        """Lambda returns fileSize as an integer."""
        mock_s3 = mock_clients["s3"]
        mock_s3.download_file.return_value = None
        mock_s3.upload_file.return_value = None

        result = handler.lambda_handler(audio_event, lambda_context)

        assert "fileSize" in result
        assert isinstance(result["fileSize"], int)

    def test_audio_processing_returns_valid_true(
        self, audio_event, lambda_context, env_vars, mock_clients
    ):
        """Lambda returns valid=True for supported audio formats."""
        mock_s3 = mock_clients["s3"]
        mock_s3.download_file.return_value = None
        mock_s3.upload_file.return_value = None

        result = handler.lambda_handler(audio_event, lambda_context)

        assert result["valid"] is True

    def test_audio_processing_returns_completed_status(
        self, audio_event, lambda_context, env_vars, mock_clients
    ):
        """Lambda returns status=COMPLETED on successful processing."""
        mock_s3 = mock_clients["s3"]
        mock_s3.download_file.return_value = None
        mock_s3.upload_file.return_value = None

        result = handler.lambda_handler(audio_event, lambda_context)

        assert result["status"] == "COMPLETED"

    def test_audio_processing_returns_correct_file_size_with_real_download(
        self, lambda_context, env_vars, mock_clients
    ):
        """Lambda returns correct fileSize when temp file has actual content."""
        mock_s3 = mock_clients["s3"]
        fake_content = b"x" * 2048

        def fake_download(bucket, key, path):
            with open(path, "wb") as f:
                f.write(fake_content)

        mock_s3.download_file.side_effect = fake_download
        mock_s3.upload_file.return_value = None

        event = {
            "bucket": {"name": "input-bucket-e2e"},
            "object": {"key": "audio/song.mp3"},
        }

        result = handler.lambda_handler(event, lambda_context)

        assert result["fileSize"] == 2048


# --- Happy Path Text-to-Speech Tests ---


class TestHappyPathTextToSpeech:
    """Tests for successful text-to-speech processing via Polly."""

    def test_reads_text_content_from_s3(
        self, lambda_context, env_vars, mock_clients
    ):
        """Lambda reads text content from S3 for .txt files."""
        mock_s3 = mock_clients["s3"]
        mock_polly = mock_clients["polly"]

        mock_s3.get_object.return_value = {
            "Body": BytesIO(b"A peaceful bedtime story")
        }
        mock_polly.synthesize_speech.return_value = {
            "AudioStream": BytesIO(b"audio-data"),
            "ContentType": "audio/mpeg",
        }
        mock_s3.upload_fileobj.return_value = None

        event = {
            "bucket": {"name": "input-bucket-e2e"},
            "object": {"key": "stories/bedtime.txt"},
        }

        handler.lambda_handler(event, lambda_context)

        mock_s3.get_object.assert_called_once_with(
            Bucket="input-bucket-e2e",
            Key="stories/bedtime.txt",
        )

    def test_calls_polly_synthesize_speech(
        self, lambda_context, env_vars, mock_clients
    ):
        """Lambda calls Polly synthesize_speech with correct parameters."""
        mock_s3 = mock_clients["s3"]
        mock_polly = mock_clients["polly"]

        text_content = "Listen to the rain falling softly"
        mock_s3.get_object.return_value = {
            "Body": BytesIO(text_content.encode("utf-8"))
        }
        mock_polly.synthesize_speech.return_value = {
            "AudioStream": BytesIO(b"synthesized-audio"),
            "ContentType": "audio/mpeg",
        }
        mock_s3.upload_fileobj.return_value = None

        event = {
            "bucket": {"name": "input-bucket-e2e"},
            "object": {"key": "prompts/rain.txt"},
        }

        handler.lambda_handler(event, lambda_context)

        mock_polly.synthesize_speech.assert_called_once()
        kwargs = mock_polly.synthesize_speech.call_args[1]
        assert kwargs["OutputFormat"] == "mp3"
        assert kwargs["VoiceId"] == "Joanna"
        assert kwargs["Text"] == text_content

    def test_uploads_polly_audio_to_output_bucket(
        self, lambda_context, env_vars, mock_clients
    ):
        """Lambda uploads Polly-generated audio to the output S3 bucket."""
        mock_s3 = mock_clients["s3"]
        mock_polly = mock_clients["polly"]

        mock_s3.get_object.return_value = {
            "Body": BytesIO(b"Some text")
        }
        mock_polly.synthesize_speech.return_value = {
            "AudioStream": BytesIO(b"polly-audio-output"),
            "ContentType": "audio/mpeg",
        }
        mock_s3.upload_fileobj.return_value = None

        event = {
            "bucket": {"name": "input-bucket-e2e"},
            "object": {"key": "prompts/sleep.txt"},
        }

        handler.lambda_handler(event, lambda_context)

        mock_s3.upload_fileobj.assert_called_once()
        call_args = mock_s3.upload_fileobj.call_args[0]
        assert call_args[1] == "output-bucket-e2e"

    def test_text_to_speech_returns_correct_file_size(
        self, lambda_context, env_vars, mock_clients
    ):
        """Lambda returns correct fileSize for Polly-generated audio."""
        mock_s3 = mock_clients["s3"]
        mock_polly = mock_clients["polly"]

        audio_data = b"synthesized-audio-data-for-size-check"
        mock_s3.get_object.return_value = {
            "Body": BytesIO(b"Text content")
        }
        mock_polly.synthesize_speech.return_value = {
            "AudioStream": BytesIO(audio_data),
            "ContentType": "audio/mpeg",
        }
        mock_s3.upload_fileobj.return_value = None

        event = {
            "bucket": {"name": "input-bucket-e2e"},
            "object": {"key": "prompts/story.txt"},
        }

        result = handler.lambda_handler(event, lambda_context)

        assert result["fileSize"] == len(audio_data)

    def test_text_to_speech_returns_valid_true(
        self, lambda_context, env_vars, mock_clients
    ):
        """Lambda returns valid=True for .txt files processed via Polly."""
        mock_s3 = mock_clients["s3"]
        mock_polly = mock_clients["polly"]

        mock_s3.get_object.return_value = {
            "Body": BytesIO(b"Short text")
        }
        mock_polly.synthesize_speech.return_value = {
            "AudioStream": BytesIO(b"audio"),
            "ContentType": "audio/mpeg",
        }
        mock_s3.upload_fileobj.return_value = None

        event = {
            "bucket": {"name": "input-bucket-e2e"},
            "object": {"key": "prompts/calm.txt"},
        }

        result = handler.lambda_handler(event, lambda_context)

        assert result["valid"] is True

    def test_text_to_speech_returns_completed_status(
        self, lambda_context, env_vars, mock_clients
    ):
        """Lambda returns status=COMPLETED for successful text-to-speech."""
        mock_s3 = mock_clients["s3"]
        mock_polly = mock_clients["polly"]

        mock_s3.get_object.return_value = {
            "Body": BytesIO(b"Relaxing story")
        }
        mock_polly.synthesize_speech.return_value = {
            "AudioStream": BytesIO(b"audio-bytes"),
            "ContentType": "audio/mpeg",
        }
        mock_s3.upload_fileobj.return_value = None

        event = {
            "bucket": {"name": "input-bucket-e2e"},
            "object": {"key": "prompts/relax.txt"},
        }

        result = handler.lambda_handler(event, lambda_context)

        assert result["status"] == "COMPLETED"


# --- DynamoDB Metadata Tracking Tests ---


class TestDynamoDBMetadataTracking:
    """Tests for DynamoDB metadata tracking behavior in the Lambda handler."""

    def test_no_dynamodb_update_on_success(
        self, lambda_context, env_vars, mock_clients
    ):
        """Lambda does NOT update DynamoDB on success (Step Functions handles that)."""
        mock_s3 = mock_clients["s3"]
        mock_dynamodb = mock_clients["dynamodb"]
        mock_s3.download_file.return_value = None
        mock_s3.upload_file.return_value = None

        event = {
            "bucket": {"name": "input-bucket-e2e"},
            "object": {"key": "audio/track.mp3"},
        }

        handler.lambda_handler(event, lambda_context)

        mock_dynamodb.update_item.assert_not_called()

    def test_dynamodb_updated_with_failed_status_on_error(
        self, lambda_context, env_vars, mock_clients
    ):
        """Lambda calls _update_dynamodb_failed with FAILED status when processing fails."""
        from botocore.exceptions import ClientError

        mock_s3 = mock_clients["s3"]
        mock_dynamodb = mock_clients["dynamodb"]
        mock_s3.download_file.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "Not found"}},
            "GetObject",
        )
        mock_dynamodb.update_item.return_value = {}

        event = {
            "bucket": {"name": "input-bucket-e2e"},
            "object": {"key": "audio/missing.mp3"},
        }

        with pytest.raises(ClientError):
            handler.lambda_handler(event, lambda_context)

        mock_dynamodb.update_item.assert_called_once()
        call_kwargs = mock_dynamodb.update_item.call_args[1]
        assert call_kwargs["TableName"] == "SleepAudioMetadataE2E"
        expr_values = call_kwargs["ExpressionAttributeValues"]
        assert any(
            v.get("S") == "FAILED"
            for v in expr_values.values()
            if isinstance(v, dict) and "S" in v
        )

    def test_dynamodb_update_uses_correct_table_name(
        self, lambda_context, env_vars, mock_clients
    ):
        """Lambda uses TABLE_NAME env var for DynamoDB updates on failure."""
        from botocore.exceptions import ClientError

        mock_s3 = mock_clients["s3"]
        mock_dynamodb = mock_clients["dynamodb"]
        mock_s3.download_file.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "Not found"}},
            "GetObject",
        )
        mock_dynamodb.update_item.return_value = {}

        event = {
            "bucket": {"name": "input-bucket-e2e"},
            "object": {"key": "audio/error.mp3"},
        }

        with pytest.raises(ClientError):
            handler.lambda_handler(event, lambda_context)

        call_kwargs = mock_dynamodb.update_item.call_args[1]
        assert call_kwargs["TableName"] == "SleepAudioMetadataE2E"

    def test_dynamodb_update_uses_audio_id_as_key(
        self, lambda_context, env_vars, mock_clients
    ):
        """Lambda uses the audioId (object key) as the DynamoDB partition key."""
        from botocore.exceptions import ClientError

        mock_s3 = mock_clients["s3"]
        mock_dynamodb = mock_clients["dynamodb"]
        mock_s3.download_file.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Denied"}},
            "GetObject",
        )
        mock_dynamodb.update_item.return_value = {}

        event = {
            "bucket": {"name": "input-bucket-e2e"},
            "object": {"key": "audio/specific-track.mp3"},
        }

        with pytest.raises(ClientError):
            handler.lambda_handler(event, lambda_context)

        call_kwargs = mock_dynamodb.update_item.call_args[1]
        assert call_kwargs["Key"] == {"audioId": {"S": "audio/specific-track.mp3"}}


# --- Error Scenarios Tests ---


class TestErrorScenarios:
    """Tests for error scenarios triggering DynamoDB FAILED update then re-raising."""

    def test_s3_download_failure_triggers_dynamodb_failed_then_reraises(
        self, lambda_context, env_vars, mock_clients
    ):
        """S3 download failure triggers DynamoDB FAILED update then re-raises exception."""
        from botocore.exceptions import ClientError

        mock_s3 = mock_clients["s3"]
        mock_dynamodb = mock_clients["dynamodb"]
        mock_s3.download_file.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "Key not found"}},
            "GetObject",
        )
        mock_dynamodb.update_item.return_value = {}

        event = {
            "bucket": {"name": "input-bucket-e2e"},
            "object": {"key": "audio/not-exists.mp3"},
        }

        with pytest.raises(ClientError):
            handler.lambda_handler(event, lambda_context)

        # Verify DynamoDB was updated with FAILED status
        mock_dynamodb.update_item.assert_called_once()
        call_kwargs = mock_dynamodb.update_item.call_args[1]
        expr_values = call_kwargs["ExpressionAttributeValues"]
        status_values = [
            v["S"] for v in expr_values.values()
            if isinstance(v, dict) and "S" in v
        ]
        assert "FAILED" in status_values

    def test_polly_failure_triggers_dynamodb_failed_then_reraises(
        self, lambda_context, env_vars, mock_clients
    ):
        """Polly failure triggers DynamoDB FAILED update then re-raises exception."""
        from botocore.exceptions import ClientError

        mock_s3 = mock_clients["s3"]
        mock_polly = mock_clients["polly"]
        mock_dynamodb = mock_clients["dynamodb"]

        mock_s3.get_object.return_value = {
            "Body": BytesIO(b"Text for synthesis")
        }
        mock_polly.synthesize_speech.side_effect = ClientError(
            {"Error": {"Code": "ServiceUnavailableException", "Message": "Polly down"}},
            "SynthesizeSpeech",
        )
        mock_dynamodb.update_item.return_value = {}

        event = {
            "bucket": {"name": "input-bucket-e2e"},
            "object": {"key": "prompts/story.txt"},
        }

        with pytest.raises(ClientError):
            handler.lambda_handler(event, lambda_context)

        mock_dynamodb.update_item.assert_called_once()
        call_kwargs = mock_dynamodb.update_item.call_args[1]
        expr_values = call_kwargs["ExpressionAttributeValues"]
        status_values = [
            v["S"] for v in expr_values.values()
            if isinstance(v, dict) and "S" in v
        ]
        assert "FAILED" in status_values

    def test_upload_failure_triggers_dynamodb_failed_then_reraises(
        self, lambda_context, env_vars, mock_clients
    ):
        """Upload failure triggers DynamoDB FAILED update then re-raises exception."""
        from botocore.exceptions import ClientError

        mock_s3 = mock_clients["s3"]
        mock_dynamodb = mock_clients["dynamodb"]
        mock_s3.download_file.return_value = None
        mock_s3.upload_file.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Upload denied"}},
            "PutObject",
        )
        mock_dynamodb.update_item.return_value = {}

        event = {
            "bucket": {"name": "input-bucket-e2e"},
            "object": {"key": "audio/upload-fail.mp3"},
        }

        with pytest.raises(ClientError):
            handler.lambda_handler(event, lambda_context)

        mock_dynamodb.update_item.assert_called_once()
        call_kwargs = mock_dynamodb.update_item.call_args[1]
        expr_values = call_kwargs["ExpressionAttributeValues"]
        status_values = [
            v["S"] for v in expr_values.values()
            if isinstance(v, dict) and "S" in v
        ]
        assert "FAILED" in status_values

    def test_error_message_stored_in_dynamodb(
        self, lambda_context, env_vars, mock_clients
    ):
        """Error message from the exception is stored in DynamoDB."""
        from botocore.exceptions import ClientError

        mock_s3 = mock_clients["s3"]
        mock_dynamodb = mock_clients["dynamodb"]
        mock_s3.download_file.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "The key does not exist"}},
            "GetObject",
        )
        mock_dynamodb.update_item.return_value = {}

        event = {
            "bucket": {"name": "input-bucket-e2e"},
            "object": {"key": "audio/bad-key.mp3"},
        }

        with pytest.raises(ClientError):
            handler.lambda_handler(event, lambda_context)

        call_kwargs = mock_dynamodb.update_item.call_args[1]
        expr_values = call_kwargs["ExpressionAttributeValues"]
        error_msgs = [
            v["S"] for v in expr_values.values()
            if isinstance(v, dict) and "S" in v and "NoSuchKey" in v.get("S", "")
        ]
        assert len(error_msgs) > 0


# --- Input Validation Tests ---


class TestInputValidation:
    """Tests for input validation and rejection of invalid inputs."""

    def test_missing_bucket_name_raises_value_error(
        self, lambda_context, env_vars, mock_clients
    ):
        """Missing bucket.name raises ValueError."""
        event = {
            "bucket": {"name": ""},
            "object": {"key": "audio/file.mp3"},
        }

        with pytest.raises(ValueError, match="Missing required fields"):
            handler.lambda_handler(event, lambda_context)

    def test_missing_object_key_raises_value_error(
        self, lambda_context, env_vars, mock_clients
    ):
        """Missing object.key raises ValueError."""
        event = {
            "bucket": {"name": "input-bucket"},
            "object": {"key": ""},
        }

        with pytest.raises(ValueError, match="Missing required fields"):
            handler.lambda_handler(event, lambda_context)

    def test_unsupported_extension_returns_valid_false(
        self, lambda_context, env_vars, mock_clients
    ):
        """Unsupported file extension returns valid=False with validationError."""
        event = {
            "bucket": {"name": "input-bucket-e2e"},
            "object": {"key": "files/document.pdf"},
        }

        result = handler.lambda_handler(event, lambda_context)

        assert result["valid"] is False
        assert "validationError" in result
        assert ".pdf" in result["validationError"]

    def test_no_extension_returns_valid_false(
        self, lambda_context, env_vars, mock_clients
    ):
        """File with no extension returns valid=False."""
        event = {
            "bucket": {"name": "input-bucket-e2e"},
            "object": {"key": "files/noextension"},
        }

        result = handler.lambda_handler(event, lambda_context)

        assert result["valid"] is False
        assert "validationError" in result

    def test_unsupported_extension_returns_validation_error_message(
        self, lambda_context, env_vars, mock_clients
    ):
        """Unsupported extension includes descriptive validationError message."""
        event = {
            "bucket": {"name": "input-bucket-e2e"},
            "object": {"key": "files/image.png"},
        }

        result = handler.lambda_handler(event, lambda_context)

        assert result["valid"] is False
        assert "Unsupported audio format" in result["validationError"]

    def test_missing_bucket_dict_raises_value_error(
        self, lambda_context, env_vars, mock_clients
    ):
        """Event missing bucket entirely raises ValueError."""
        event = {
            "object": {"key": "audio/file.mp3"},
        }

        with pytest.raises(ValueError, match="Missing required fields"):
            handler.lambda_handler(event, lambda_context)

    def test_missing_object_dict_raises_value_error(
        self, lambda_context, env_vars, mock_clients
    ):
        """Event missing object entirely raises ValueError."""
        event = {
            "bucket": {"name": "input-bucket"},
        }

        with pytest.raises(ValueError, match="Missing required fields"):
            handler.lambda_handler(event, lambda_context)


# --- State Machine DynamoDB Metadata Lifecycle Tests ---


class TestDynamoDBMetadataLifecycle:
    """Tests validating DynamoDB state transitions in the state machine definition.

    Validates:
    - WriteInitialRecord writes audioId, status=PROCESSING, inputBucket, inputKey, createdAt
    - UpdateStatusCompleted writes status=COMPLETED, updatedAt, outputKey, outputBucket, fileSize
    - UpdateStatusFailed writes status=FAILED, updatedAt
    """

    def test_write_initial_record_writes_audio_id(self, template):
        """WriteInitialRecord writes audioId from $.object.key."""
        definition = _get_definition(template)
        state = definition["States"]["WriteInitialRecord"]
        item = state["Parameters"]["Item"]
        assert "audioId" in item
        assert item["audioId"] == {"S.$": "$.object.key"}

    def test_write_initial_record_writes_processing_status(self, template):
        """WriteInitialRecord writes status=PROCESSING."""
        definition = _get_definition(template)
        state = definition["States"]["WriteInitialRecord"]
        item = state["Parameters"]["Item"]
        assert "status" in item
        assert item["status"] == {"S": "PROCESSING"}

    def test_write_initial_record_writes_input_bucket(self, template):
        """WriteInitialRecord writes inputBucket from $.bucket.name."""
        definition = _get_definition(template)
        state = definition["States"]["WriteInitialRecord"]
        item = state["Parameters"]["Item"]
        assert "inputBucket" in item
        assert item["inputBucket"] == {"S.$": "$.bucket.name"}

    def test_write_initial_record_writes_input_key(self, template):
        """WriteInitialRecord writes inputKey from $.object.key."""
        definition = _get_definition(template)
        state = definition["States"]["WriteInitialRecord"]
        item = state["Parameters"]["Item"]
        assert "inputKey" in item
        assert item["inputKey"] == {"S.$": "$.object.key"}

    def test_write_initial_record_writes_created_at(self, template):
        """WriteInitialRecord writes createdAt from $$.State.EnteredTime."""
        definition = _get_definition(template)
        state = definition["States"]["WriteInitialRecord"]
        item = state["Parameters"]["Item"]
        assert "createdAt" in item
        assert item["createdAt"] == {"S.$": "$$.State.EnteredTime"}

    def test_update_status_completed_writes_completed(self, template):
        """UpdateStatusCompleted writes status=COMPLETED."""
        definition = _get_definition(template)
        state = definition["States"]["UpdateStatusCompleted"]
        expr_values = state["Parameters"]["ExpressionAttributeValues"]
        assert ":status" in expr_values
        assert expr_values[":status"] == {"S": "COMPLETED"}

    def test_update_status_completed_writes_updated_at(self, template):
        """UpdateStatusCompleted writes updatedAt from $$.State.EnteredTime."""
        definition = _get_definition(template)
        state = definition["States"]["UpdateStatusCompleted"]
        expr_values = state["Parameters"]["ExpressionAttributeValues"]
        assert ":updatedAt" in expr_values
        assert expr_values[":updatedAt"] == {"S.$": "$$.State.EnteredTime"}

    def test_update_status_completed_writes_output_key(self, template):
        """UpdateStatusCompleted writes outputKey from processAudioResult."""
        definition = _get_definition(template)
        state = definition["States"]["UpdateStatusCompleted"]
        expr_values = state["Parameters"]["ExpressionAttributeValues"]
        assert ":outputKey" in expr_values
        assert expr_values[":outputKey"] == {
            "S.$": "$.processAudioResult.Payload.outputKey"
        }

    def test_update_status_completed_writes_output_bucket(self, template):
        """UpdateStatusCompleted writes outputBucket from processAudioResult."""
        definition = _get_definition(template)
        state = definition["States"]["UpdateStatusCompleted"]
        expr_values = state["Parameters"]["ExpressionAttributeValues"]
        assert ":outputBucket" in expr_values
        assert expr_values[":outputBucket"] == {
            "S.$": "$.processAudioResult.Payload.outputBucket"
        }

    def test_update_status_completed_writes_file_size(self, template):
        """UpdateStatusCompleted writes fileSize from processAudioResult."""
        definition = _get_definition(template)
        state = definition["States"]["UpdateStatusCompleted"]
        expr_values = state["Parameters"]["ExpressionAttributeValues"]
        assert ":fileSize" in expr_values
        assert expr_values[":fileSize"] == {
            "N.$": "States.Format('{}', $.processAudioResult.Payload.fileSize)"
        }

    def test_update_status_failed_writes_failed(self, template):
        """UpdateStatusFailed writes status=FAILED."""
        definition = _get_definition(template)
        state = definition["States"]["UpdateStatusFailed"]
        expr_values = state["Parameters"]["ExpressionAttributeValues"]
        assert ":status" in expr_values
        assert expr_values[":status"] == {"S": "FAILED"}

    def test_update_status_failed_writes_updated_at(self, template):
        """UpdateStatusFailed writes updatedAt from $$.State.EnteredTime."""
        definition = _get_definition(template)
        state = definition["States"]["UpdateStatusFailed"]
        expr_values = state["Parameters"]["ExpressionAttributeValues"]
        assert ":updatedAt" in expr_values
        assert expr_values[":updatedAt"] == {"S.$": "$$.State.EnteredTime"}


# --- SNS Notification Scenarios Tests ---


class TestSNSNotificationScenarios:
    """Tests validating SNS notification message formats in the state machine."""

    def test_success_notification_contains_audio_id(self, template):
        """Success notification message includes audioId."""
        definition = _get_definition(template)
        state = definition["States"]["PublishCompletedNotification"]
        message = state["Parameters"]["Message"]
        assert "audioId.$" in message

    def test_success_notification_contains_completed_status(self, template):
        """Success notification message includes status=COMPLETED."""
        definition = _get_definition(template)
        state = definition["States"]["PublishCompletedNotification"]
        message = state["Parameters"]["Message"]
        assert message["status"] == "COMPLETED"

    def test_failure_notification_contains_audio_id(self, template):
        """Failure notification message includes audioId."""
        definition = _get_definition(template)
        state = definition["States"]["PublishFailedNotification"]
        message = state["Parameters"]["Message"]
        assert "audioId.$" in message

    def test_failure_notification_contains_failed_status(self, template):
        """Failure notification message includes status=FAILED."""
        definition = _get_definition(template)
        state = definition["States"]["PublishFailedNotification"]
        message = state["Parameters"]["Message"]
        assert message["status"] == "FAILED"

    def test_failure_notification_contains_reason_field(self, template):
        """Failure notification message includes reason field."""
        definition = _get_definition(template)
        state = definition["States"]["PublishFailedNotification"]
        message = state["Parameters"]["Message"]
        assert "reason.$" in message

    def test_completed_notification_has_catch_block(self, template):
        """PublishCompletedNotification has Catch block to prevent masking pipeline outcomes."""
        definition = _get_definition(template)
        state = definition["States"]["PublishCompletedNotification"]
        assert "Catch" in state
        catchers = state["Catch"]
        assert len(catchers) > 0
        # Should catch States.ALL and route to Done (not fail the pipeline)
        catch_errors = [c["ErrorEquals"] for c in catchers]
        assert ["States.ALL"] in catch_errors

    def test_failed_notification_has_catch_block(self, template):
        """PublishFailedNotification has Catch block to prevent masking pipeline outcomes."""
        definition = _get_definition(template)
        state = definition["States"]["PublishFailedNotification"]
        assert "Catch" in state
        catchers = state["Catch"]
        assert len(catchers) > 0
        catch_errors = [c["ErrorEquals"] for c in catchers]
        assert ["States.ALL"] in catch_errors
