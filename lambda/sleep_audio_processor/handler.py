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
    logger.info("Received event: %s", json.dumps(event))

    try:
        audio_id = event.get("object", {}).get("key", "")
        bucket_name = event.get("bucket", {}).get("name", "")

        if not audio_id or not bucket_name:
            raise ValueError("Missing required fields: object.key or bucket.name")

        # Validate file extension
        ext = os.path.splitext(audio_id)[1].lower()
        is_valid = ext in ALLOWED_EXTENSIONS

        result = {
            "audioId": audio_id,
            "bucket": bucket_name,
            "tableName": TABLE_NAME,
            "processorStatus": "PROCESSED",
            "message": "Audio metadata enriched successfully",
            "valid": is_valid,
        }

        if not is_valid:
            result["validationError"] = f"Unsupported audio format: {ext if ext else '(none)'}"

        logger.info("Processing result: %s", json.dumps(result))
        return result

    except Exception as e:
        logger.error("Error processing audio: %s", str(e))
        raise
