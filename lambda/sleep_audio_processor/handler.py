"""Sleep Audio Processor Lambda handler.

Receives input from the Step Functions state machine (S3 event details),
downloads audio from input bucket (or synthesizes from text via Polly),
uploads processed audio to output bucket, and updates DynamoDB with results.
"""

import json
import logging
import os
import uuid
from datetime import datetime, timezone

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

ALLOWED_EXTENSIONS = [".mp3", ".wav", ".ogg", ".flac"]
TEXT_EXTENSIONS = [".txt"]

# Initialize boto3 clients (created at module load for Lambda container reuse)
s3_client = boto3.client("s3")
polly_client = boto3.client("polly")
dynamodb_client = boto3.client("dynamodb")


def lambda_handler(event, context):
    """Process audio file from the state machine.

    For audio files (.mp3, .wav, .ogg, .flac): downloads from input bucket,
    uploads to output bucket.
    For text files (.txt): reads text from S3, calls Polly to synthesize speech,
    uploads generated audio to output bucket.

    Args:
        event: Input from Step Functions containing S3 event details.
        context: Lambda context object.

    Returns:
        dict: Enriched metadata including output location and processing status.
    """
    request_id = getattr(context, "aws_request_id", "unknown")

    # Read environment variables at invocation time
    table_name = os.environ.get("TABLE_NAME", "")
    output_bucket = os.environ.get("OUTPUT_BUCKET", "")

    logger.info(json.dumps({
        "requestId": request_id,
        "status": "RECEIVED",
        "event": event,
    }))

    try:
        audio_id = event.get("object", {}).get("key", "")
        bucket_name = event.get("bucket", {}).get("name", "")

        if not audio_id or not bucket_name:
            raise ValueError("Missing required fields: object.key or bucket.name")

        # Validate file extension
        ext = os.path.splitext(audio_id)[1].lower()
        is_audio = ext in ALLOWED_EXTENSIONS
        is_text = ext in TEXT_EXTENSIONS
        is_valid = is_audio or is_text

        # If the file is not a supported type, return validation error
        if not is_valid:
            result = {
                "requestId": request_id,
                "audioId": audio_id,
                "bucket": bucket_name,
                "tableName": table_name,
                "processorStatus": "PROCESSED",
                "message": "Audio metadata enriched successfully",
                "valid": False,
                "validationError": f"Unsupported audio format: {ext if ext else '(none)'}",
            }
            logger.info(json.dumps({
                "requestId": request_id,
                "status": "COMPLETED",
                "audioId": audio_id,
                "valid": False,
            }))
            return result

        # Generate output key
        base_name = os.path.splitext(os.path.basename(audio_id))[0]
        unique_id = str(uuid.uuid4())
        output_key = f"processed/{base_name}_{unique_id}.mp3"

        file_size = 0

        if is_audio:
            # Download audio from input bucket and upload to output bucket
            tmp_path = f"/tmp/{base_name}_{unique_id}{ext}"
            file_size = _process_audio_file(
                bucket_name, audio_id, output_bucket, output_key, tmp_path
            )
        elif is_text:
            # Read text from S3, synthesize with Polly, upload to output bucket
            file_size = _process_text_file(
                bucket_name, audio_id, output_bucket, output_key
            )

        result = {
            "requestId": request_id,
            "audioId": audio_id,
            "bucket": bucket_name,
            "tableName": table_name,
            "outputBucket": output_bucket,
            "outputKey": output_key,
            "fileSize": file_size,
            "status": "COMPLETED",
            "processorStatus": "PROCESSED",
            "message": "Audio metadata enriched successfully",
            "valid": True,
        }

        logger.info(json.dumps({
            "requestId": request_id,
            "status": "COMPLETED",
            "audioId": audio_id,
            "outputKey": output_key,
            "fileSize": file_size,
            "valid": True,
        }))

        return result

    except Exception as e:
        logger.error(json.dumps({
            "requestId": request_id,
            "status": "ERROR",
            "error": str(e),
        }))

        # Try to update DynamoDB with FAILED status
        try:
            audio_id = event.get("object", {}).get("key", "")
            if audio_id and table_name:
                _update_dynamodb_failed(table_name, audio_id, str(e))
        except Exception as db_err:
            logger.error(json.dumps({
                "requestId": request_id,
                "status": "DYNAMODB_UPDATE_FAILED",
                "error": str(db_err),
            }))

        raise


def _process_audio_file(input_bucket, input_key, output_bucket, output_key, tmp_path):
    """Download audio from input bucket and upload to output bucket.

    Returns:
        int: File size in bytes of the uploaded file.
    """
    # Download from input bucket
    s3_client.download_file(input_bucket, input_key, tmp_path)

    try:
        # Get file size
        file_size = os.path.getsize(tmp_path) if os.path.exists(tmp_path) else 0

        # Upload to output bucket
        s3_client.upload_file(tmp_path, output_bucket, output_key)
    finally:
        # Cleanup temp file even if upload fails
        try:
            os.remove(tmp_path)
        except OSError:
            pass

    return file_size


def _process_text_file(input_bucket, input_key, output_bucket, output_key):
    """Read text from S3, synthesize with Polly, upload audio to output bucket.

    Returns:
        int: File size in bytes of the uploaded audio.
    """
    from io import BytesIO

    # Read text content from S3
    response = s3_client.get_object(Bucket=input_bucket, Key=input_key)
    text_content = response["Body"].read().decode("utf-8")

    # Validate text length against Polly's 3000-character limit
    if len(text_content) > 3000:
        raise ValueError("Text content exceeds Polly 3000-character limit")

    # Synthesize speech with Polly
    polly_response = polly_client.synthesize_speech(
        OutputFormat="mp3",
        Text=text_content,
        VoiceId="Joanna",
    )

    # Buffer the audio stream so we can measure size before uploading
    audio_stream = polly_response["AudioStream"]
    audio_buffer = BytesIO(audio_stream.read())
    file_size = len(audio_buffer.getvalue())

    # Upload the buffered audio to output bucket
    s3_client.upload_fileobj(
        audio_buffer,
        output_bucket,
        output_key,
    )

    return file_size


def _update_dynamodb_failed(table_name, audio_id, error_message):
    """Update DynamoDB record with FAILED status and error message."""
    now = datetime.now(timezone.utc).isoformat()
    dynamodb_client.update_item(
        TableName=table_name,
        Key={"audioId": {"S": audio_id}},
        UpdateExpression="SET #s = :status, errorMessage = :errorMessage, updatedAt = :updatedAt",
        ExpressionAttributeNames={
            "#s": "status",
        },
        ExpressionAttributeValues={
            ":status": {"S": "FAILED"},
            ":errorMessage": {"S": error_message},
            ":updatedAt": {"S": now},
        },
    )
