"""Sleep Audio Processor Lambda handler.

Receives input from the Step Functions state machine (S3 event details),
logs the input, and returns enriched metadata for downstream processing.
"""

import json
import logging
import os

logger = logging.getLogger()
logger.setLevel(logging.INFO)

TABLE_NAME = os.environ.get("TABLE_NAME", "")

ALLOWED_EXTENSIONS = [".mp3", ".wav", ".ogg", ".flac"]


def lambda_handler(event, context):
    """Process audio file metadata from the state machine.

    Args:
        event: Input from Step Functions containing S3 event details.
        context: Lambda context object.

    Returns:
        dict: Enriched metadata including validation result.
    """
    request_id = getattr(context, "aws_request_id", "unknown")

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
        is_valid = ext in ALLOWED_EXTENSIONS

        result = {
            "requestId": request_id,
            "audioId": audio_id,
            "bucket": bucket_name,
            "tableName": TABLE_NAME,
            "processorStatus": "PROCESSED",
            "message": "Audio metadata enriched successfully",
            "valid": is_valid,
        }

        if not is_valid:
            result["validationError"] = f"Unsupported audio format: {ext if ext else '(none)'}"

        logger.info(json.dumps({
            "requestId": request_id,
            "status": "COMPLETED",
            "audioId": audio_id,
            "valid": is_valid,
        }))

        return result

    except Exception as e:
        logger.error(json.dumps({
            "requestId": request_id,
            "status": "ERROR",
            "error": str(e),
        }))
        raise
