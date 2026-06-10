"""Unit tests for full audio processing Lambda logic.

Tests cover:
- S3 download from input bucket for audio files
- Polly synthesize_speech for text input files (.txt)
- S3 upload of processed file to output bucket
- DynamoDB update with output location, file size, status=COMPLETED
- Structured response with outputKey, outputBucket, fileSize, status
- Error handling: S3 download failure, Polly failure, upload failure
"""

import sys
import os
import json
from unittest.mock import patch, MagicMock, ANY
from io import BytesIO

import pytest

# Add the Lambda source directory to the path
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "..", "lambda", "sleep_audio_processor")
)

import handler  # noqa: E402


@pytest.fixture
def lambda_context():
    """Minimal mock Lambda context."""

    class Context:
        function_name = "SleepAudioProcessor"
        memory_limit_in_mb = 512
        invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:SleepAudioProcessor"
        aws_request_id = "test-request-id-audio"

    return Context()


@pytest.fixture
def audio_event():
    """Event for an audio file (.mp3) input."""
    return {
        "bucket": {"name": "my-input-bucket"},
        "object": {"key": "audio/test-file.mp3"},
    }


@pytest.fixture
def text_event():
    """Event for a text file (.txt) input."""
    return {
        "bucket": {"name": "my-input-bucket"},
        "object": {"key": "prompts/sleep-story.txt"},
    }


@pytest.fixture
def wav_event():
    """Event for a .wav audio file input."""
    return {
        "bucket": {"name": "my-input-bucket"},
        "object": {"key": "audio/relaxation.wav"},
    }


@pytest.fixture
def env_vars(monkeypatch):
    """Set required environment variables for the handler."""
    monkeypatch.setenv("OUTPUT_BUCKET", "my-output-bucket")
    monkeypatch.setenv("TABLE_NAME", "SleepAudioMetadata")


@pytest.fixture
def mock_boto3_clients():
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


class TestAudioFileDownload:
    """Tests for Lambda downloading audio files from S3 input bucket."""

    def test_downloads_audio_from_input_bucket(
        self, audio_event, lambda_context, env_vars, mock_boto3_clients
    ):
        """Lambda should download audio file from the input S3 bucket."""
        mock_s3 = mock_boto3_clients["s3"]
        mock_s3.download_file.return_value = None
        mock_s3.upload_file.return_value = None

        handler.lambda_handler(audio_event, lambda_context)

        mock_s3.download_file.assert_called_once_with(
            "my-input-bucket",
            "audio/test-file.mp3",
            ANY,
        )

    def test_downloads_wav_from_input_bucket(
        self, wav_event, lambda_context, env_vars, mock_boto3_clients
    ):
        """Lambda should download .wav audio file from the input S3 bucket."""
        mock_s3 = mock_boto3_clients["s3"]
        mock_s3.download_file.return_value = None
        mock_s3.upload_file.return_value = None

        handler.lambda_handler(wav_event, lambda_context)

        mock_s3.download_file.assert_called_once_with(
            "my-input-bucket",
            "audio/relaxation.wav",
            ANY,
        )


class TestPollyTextToSpeech:
    """Tests for Lambda calling Polly synthesize_speech for text files."""

    def test_calls_polly_for_txt_file(
        self, text_event, lambda_context, env_vars, mock_boto3_clients
    ):
        """Lambda should call Polly synthesize_speech when input is a .txt file."""
        mock_s3 = mock_boto3_clients["s3"]
        mock_polly = mock_boto3_clients["polly"]

        # Mock S3 get_object for reading text content
        mock_s3.get_object.return_value = {
            "Body": BytesIO(b"Once upon a time in a peaceful forest...")
        }

        # Mock Polly synthesize_speech response
        mock_polly.synthesize_speech.return_value = {
            "AudioStream": BytesIO(b"fake-audio-data-bytes"),
            "ContentType": "audio/mpeg",
        }

        # Mock S3 upload
        mock_s3.upload_fileobj.return_value = None

        handler.lambda_handler(text_event, lambda_context)

        mock_polly.synthesize_speech.assert_called_once()
        call_kwargs = mock_polly.synthesize_speech.call_args[1]
        assert call_kwargs["OutputFormat"] == "mp3"
        assert call_kwargs["VoiceId"] == "Joanna"
        assert "Once upon a time" in call_kwargs["Text"]

    def test_reads_text_content_from_s3(
        self, text_event, lambda_context, env_vars, mock_boto3_clients
    ):
        """Lambda should read text content from S3 for .txt files."""
        mock_s3 = mock_boto3_clients["s3"]
        mock_polly = mock_boto3_clients["polly"]

        mock_s3.get_object.return_value = {
            "Body": BytesIO(b"Sleep story content")
        }
        mock_polly.synthesize_speech.return_value = {
            "AudioStream": BytesIO(b"fake-audio-data"),
            "ContentType": "audio/mpeg",
        }
        mock_s3.upload_fileobj.return_value = None

        handler.lambda_handler(text_event, lambda_context)

        mock_s3.get_object.assert_called_once_with(
            Bucket="my-input-bucket",
            Key="prompts/sleep-story.txt",
        )


class TestOutputUpload:
    """Tests for Lambda uploading processed file to output S3 bucket."""

    def test_uploads_audio_to_output_bucket(
        self, audio_event, lambda_context, env_vars, mock_boto3_clients
    ):
        """Lambda should upload processed audio file to the output S3 bucket."""
        mock_s3 = mock_boto3_clients["s3"]
        mock_s3.download_file.return_value = None
        mock_s3.upload_file.return_value = None

        result = handler.lambda_handler(audio_event, lambda_context)

        mock_s3.upload_file.assert_called_once()
        call_args = mock_s3.upload_file.call_args
        # Verify upload is to the output bucket
        assert call_args[0][1] == "my-output-bucket"
        # Verify the key starts with processed/
        assert call_args[0][2].startswith("processed/")

    def test_output_key_contains_audio_id(
        self, audio_event, lambda_context, env_vars, mock_boto3_clients
    ):
        """Output key should contain the original audio ID (without extension)."""
        mock_s3 = mock_boto3_clients["s3"]
        mock_s3.download_file.return_value = None
        mock_s3.upload_file.return_value = None

        result = handler.lambda_handler(audio_event, lambda_context)

        output_key = result["outputKey"]
        # Should contain 'test-file' (the filename without extension)
        assert "test-file" in output_key
        assert output_key.startswith("processed/")
        assert output_key.endswith(".mp3")

    def test_uploads_polly_output_to_output_bucket(
        self, text_event, lambda_context, env_vars, mock_boto3_clients
    ):
        """Lambda should upload Polly-generated audio to the output S3 bucket."""
        mock_s3 = mock_boto3_clients["s3"]
        mock_polly = mock_boto3_clients["polly"]

        mock_s3.get_object.return_value = {
            "Body": BytesIO(b"Text content for speech")
        }
        mock_polly.synthesize_speech.return_value = {
            "AudioStream": BytesIO(b"synthesized-audio-bytes"),
            "ContentType": "audio/mpeg",
        }
        mock_s3.upload_fileobj.return_value = None

        result = handler.lambda_handler(text_event, lambda_context)

        mock_s3.upload_fileobj.assert_called_once()
        call_args = mock_s3.upload_fileobj.call_args[0]
        # Verify upload is to the output bucket
        assert call_args[1] == "my-output-bucket"


class TestDynamoDBUpdate:
    """Tests for Lambda NOT writing COMPLETED to DynamoDB (Step Functions handles that).

    The Lambda only writes FAILED status on error paths.
    """

    def test_does_not_update_dynamodb_on_success(
        self, audio_event, lambda_context, env_vars, mock_boto3_clients
    ):
        """Lambda should NOT update DynamoDB on success (Step Functions handles COMPLETED)."""
        mock_s3 = mock_boto3_clients["s3"]
        mock_dynamodb = mock_boto3_clients["dynamodb"]
        mock_s3.download_file.return_value = None
        mock_s3.upload_file.return_value = None
        mock_dynamodb.update_item.return_value = {}

        handler.lambda_handler(audio_event, lambda_context)

        # Lambda should not call DynamoDB on success path
        mock_dynamodb.update_item.assert_not_called()


class TestStructuredResponse:
    """Tests for Lambda returning structured response for Step Functions."""

    def test_returns_output_key(
        self, audio_event, lambda_context, env_vars, mock_boto3_clients
    ):
        """Lambda should return outputKey in response."""
        mock_s3 = mock_boto3_clients["s3"]
        mock_s3.download_file.return_value = None
        mock_s3.upload_file.return_value = None

        result = handler.lambda_handler(audio_event, lambda_context)

        assert "outputKey" in result
        assert result["outputKey"].startswith("processed/")

    def test_returns_output_bucket(
        self, audio_event, lambda_context, env_vars, mock_boto3_clients
    ):
        """Lambda should return outputBucket in response."""
        mock_s3 = mock_boto3_clients["s3"]
        mock_s3.download_file.return_value = None
        mock_s3.upload_file.return_value = None

        result = handler.lambda_handler(audio_event, lambda_context)

        assert "outputBucket" in result
        assert result["outputBucket"] == "my-output-bucket"

    def test_returns_file_size(
        self, audio_event, lambda_context, env_vars, mock_boto3_clients
    ):
        """Lambda should return fileSize in response (0 for mocked audio since no real file)."""
        mock_s3 = mock_boto3_clients["s3"]
        mock_s3.download_file.return_value = None
        mock_s3.upload_file.return_value = None

        result = handler.lambda_handler(audio_event, lambda_context)

        assert "fileSize" in result
        assert isinstance(result["fileSize"], int)

    def test_returns_file_size_for_text_file(
        self, text_event, lambda_context, env_vars, mock_boto3_clients
    ):
        """Lambda should return correct fileSize for text-to-speech (Polly) output."""
        mock_s3 = mock_boto3_clients["s3"]
        mock_polly = mock_boto3_clients["polly"]

        audio_data = b"fake-audio-data-bytes-1234567890"
        mock_s3.get_object.return_value = {
            "Body": BytesIO(b"Some text content")
        }
        mock_polly.synthesize_speech.return_value = {
            "AudioStream": BytesIO(audio_data),
            "ContentType": "audio/mpeg",
        }
        mock_s3.upload_fileobj.return_value = None

        result = handler.lambda_handler(text_event, lambda_context)

        assert "fileSize" in result
        assert result["fileSize"] == len(audio_data)

    def test_returns_file_size_for_audio_file_with_real_temp(
        self, audio_event, lambda_context, env_vars, mock_boto3_clients
    ):
        """Lambda should return correct fileSize when temp file exists (simulated download)."""
        import tempfile

        mock_s3 = mock_boto3_clients["s3"]
        fake_audio_content = b"x" * 1024  # 1KB of fake audio data

        def fake_download(bucket, key, path):
            """Simulate download_file by creating a real temp file."""
            with open(path, "wb") as f:
                f.write(fake_audio_content)

        mock_s3.download_file.side_effect = fake_download
        mock_s3.upload_file.return_value = None

        result = handler.lambda_handler(audio_event, lambda_context)

        assert result["fileSize"] == 1024

    def test_returns_completed_status(
        self, audio_event, lambda_context, env_vars, mock_boto3_clients
    ):
        """Lambda should return status=COMPLETED in response."""
        mock_s3 = mock_boto3_clients["s3"]
        mock_s3.download_file.return_value = None
        mock_s3.upload_file.return_value = None

        result = handler.lambda_handler(audio_event, lambda_context)

        assert result["status"] == "COMPLETED"

    def test_returns_processor_status(
        self, audio_event, lambda_context, env_vars, mock_boto3_clients
    ):
        """Lambda should return processorStatus=PROCESSED in response."""
        mock_s3 = mock_boto3_clients["s3"]
        mock_s3.download_file.return_value = None
        mock_s3.upload_file.return_value = None

        result = handler.lambda_handler(audio_event, lambda_context)

        assert result["processorStatus"] == "PROCESSED"

    def test_returns_valid_true(
        self, audio_event, lambda_context, env_vars, mock_boto3_clients
    ):
        """Lambda should return valid=True for valid audio files."""
        mock_s3 = mock_boto3_clients["s3"]
        mock_s3.download_file.return_value = None
        mock_s3.upload_file.return_value = None

        result = handler.lambda_handler(audio_event, lambda_context)

        assert result["valid"] is True

    def test_returns_request_id(
        self, audio_event, lambda_context, env_vars, mock_boto3_clients
    ):
        """Lambda should return requestId in response."""
        mock_s3 = mock_boto3_clients["s3"]
        mock_s3.download_file.return_value = None
        mock_s3.upload_file.return_value = None

        result = handler.lambda_handler(audio_event, lambda_context)

        assert result["requestId"] == "test-request-id-audio"

    def test_returns_audio_id(
        self, audio_event, lambda_context, env_vars, mock_boto3_clients
    ):
        """Lambda should return audioId in response."""
        mock_s3 = mock_boto3_clients["s3"]
        mock_s3.download_file.return_value = None
        mock_s3.upload_file.return_value = None

        result = handler.lambda_handler(audio_event, lambda_context)

        assert result["audioId"] == "audio/test-file.mp3"


class TestErrorHandling:
    """Tests for error handling: S3 download failure, Polly failure, upload failure."""

    def test_s3_download_failure_raises(
        self, audio_event, lambda_context, env_vars, mock_boto3_clients
    ):
        """Lambda should raise when S3 download fails (for Step Functions retry)."""
        from botocore.exceptions import ClientError

        mock_s3 = mock_boto3_clients["s3"]
        mock_dynamodb = mock_boto3_clients["dynamodb"]
        mock_s3.download_file.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "Key not found"}},
            "GetObject",
        )
        mock_dynamodb.update_item.return_value = {}

        with pytest.raises(ClientError):
            handler.lambda_handler(audio_event, lambda_context)

    def test_polly_failure_raises(
        self, text_event, lambda_context, env_vars, mock_boto3_clients
    ):
        """Lambda should raise when Polly synthesize_speech fails."""
        from botocore.exceptions import ClientError

        mock_s3 = mock_boto3_clients["s3"]
        mock_polly = mock_boto3_clients["polly"]
        mock_dynamodb = mock_boto3_clients["dynamodb"]

        mock_s3.get_object.return_value = {
            "Body": BytesIO(b"Some text content")
        }
        mock_polly.synthesize_speech.side_effect = ClientError(
            {"Error": {"Code": "ServiceUnavailableException", "Message": "Polly unavailable"}},
            "SynthesizeSpeech",
        )
        mock_dynamodb.update_item.return_value = {}

        with pytest.raises(ClientError):
            handler.lambda_handler(text_event, lambda_context)

    def test_upload_failure_raises(
        self, audio_event, lambda_context, env_vars, mock_boto3_clients
    ):
        """Lambda should raise when S3 upload fails."""
        from botocore.exceptions import ClientError

        mock_s3 = mock_boto3_clients["s3"]
        mock_dynamodb = mock_boto3_clients["dynamodb"]
        mock_s3.download_file.return_value = None
        mock_s3.upload_file.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Access denied"}},
            "PutObject",
        )
        mock_dynamodb.update_item.return_value = {}

        with pytest.raises(ClientError):
            handler.lambda_handler(audio_event, lambda_context)

    def test_s3_download_failure_updates_dynamodb_failed(
        self, audio_event, lambda_context, env_vars, mock_boto3_clients
    ):
        """Lambda should try to update DynamoDB status=FAILED when S3 download fails."""
        from botocore.exceptions import ClientError

        mock_s3 = mock_boto3_clients["s3"]
        mock_dynamodb = mock_boto3_clients["dynamodb"]
        mock_s3.download_file.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "Key not found"}},
            "GetObject",
        )
        mock_dynamodb.update_item.return_value = {}

        with pytest.raises(ClientError):
            handler.lambda_handler(audio_event, lambda_context)

        # Verify DynamoDB was updated with FAILED status
        mock_dynamodb.update_item.assert_called_once()
        call_kwargs = mock_dynamodb.update_item.call_args[1]
        expr_values = call_kwargs["ExpressionAttributeValues"]
        assert any(
            v.get("S") == "FAILED"
            for v in expr_values.values()
            if isinstance(v, dict) and "S" in v
        )

    def test_invalid_extension_returns_validation_error(
        self, lambda_context, env_vars, mock_boto3_clients
    ):
        """Lambda should return validationError for unsupported file extensions."""
        event = {
            "bucket": {"name": "my-input-bucket"},
            "object": {"key": "files/document.pdf"},
        }

        result = handler.lambda_handler(event, lambda_context)

        assert result["valid"] is False
        assert "validationError" in result
        assert result["processorStatus"] == "PROCESSED"
