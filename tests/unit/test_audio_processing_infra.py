"""CDK infrastructure tests for audio processing feature.

Verifies:
- Lambda has OUTPUT_BUCKET environment variable
- Lambda has increased memory (512MB) and timeout (60s)
- S3 read grant on input bucket for Lambda
- S3 write grant on output bucket for Lambda
- Polly permission for Lambda role
- UpdateStatusCompleted includes output metadata fields
"""

import json

from aws_cdk.assertions import Match


def test_lambda_has_output_bucket_env_var(template):
    """Lambda function should have OUTPUT_BUCKET environment variable."""
    template.has_resource_properties(
        "AWS::Lambda::Function",
        {
            "Environment": {
                "Variables": Match.object_like({
                    "OUTPUT_BUCKET": Match.any_value(),
                }),
            },
        },
    )


def test_lambda_has_table_name_env_var(template):
    """Lambda function should still have TABLE_NAME environment variable."""
    template.has_resource_properties(
        "AWS::Lambda::Function",
        {
            "Environment": {
                "Variables": Match.object_like({
                    "TABLE_NAME": Match.any_value(),
                }),
            },
        },
    )


def test_lambda_has_512mb_memory(template):
    """Lambda function should have 512MB memory."""
    template.has_resource_properties(
        "AWS::Lambda::Function",
        {
            "MemorySize": 512,
        },
    )


def test_lambda_has_60s_timeout(template):
    """Lambda function should have 60 second timeout."""
    template.has_resource_properties(
        "AWS::Lambda::Function",
        {
            "Timeout": 60,
        },
    )


def test_lambda_role_has_polly_permission(template):
    """Lambda role should have polly:SynthesizeSpeech permission."""
    # Find IAM policies that grant polly:SynthesizeSpeech
    policies = template.find_resources(
        "AWS::IAM::Policy",
    )
    found_polly = False
    for policy_id, policy in policies.items():
        statements = (
            policy.get("Properties", {})
            .get("PolicyDocument", {})
            .get("Statement", [])
        )
        for stmt in statements:
            actions = stmt.get("Action", [])
            if isinstance(actions, str):
                actions = [actions]
            if "polly:SynthesizeSpeech" in actions:
                found_polly = True
                break
    assert found_polly, "Lambda role must have polly:SynthesizeSpeech permission"


def test_lambda_role_has_s3_read_on_input_bucket(template):
    """Lambda role should have S3 read permissions on the input bucket."""
    policies = template.find_resources("AWS::IAM::Policy")
    found_s3_read = False
    for policy_id, policy in policies.items():
        statements = (
            policy.get("Properties", {})
            .get("PolicyDocument", {})
            .get("Statement", [])
        )
        for stmt in statements:
            actions = stmt.get("Action", [])
            if isinstance(actions, str):
                actions = [actions]
            # grant_read gives s3:GetObject*, s3:GetBucket*, s3:List*
            if "s3:GetObject*" in actions or "s3:GetBucket*" in actions:
                found_s3_read = True
                break
    assert found_s3_read, "Lambda role must have S3 read permissions on input bucket"


def test_lambda_role_has_s3_write_on_output_bucket(template):
    """Lambda role should have S3 write permissions on the output bucket."""
    policies = template.find_resources("AWS::IAM::Policy")
    found_s3_write = False
    for policy_id, policy in policies.items():
        statements = (
            policy.get("Properties", {})
            .get("PolicyDocument", {})
            .get("Statement", [])
        )
        for stmt in statements:
            actions = stmt.get("Action", [])
            if isinstance(actions, str):
                actions = [actions]
            # grant_write gives s3:PutObject*, s3:Abort*, s3:DeleteObject*
            if "s3:PutObject*" in actions or "s3:PutObject" in actions:
                found_s3_write = True
                break
    assert found_s3_write, "Lambda role must have S3 write permissions on output bucket"


def _get_state_definition_text(template):
    """Helper to get the flattened state machine definition text."""
    sm_resources = template.find_resources("AWS::StepFunctions::StateMachine")
    resource = list(sm_resources.values())[0]
    definition_str = resource["Properties"]["DefinitionString"]
    if isinstance(definition_str, dict) and "Fn::Join" in definition_str:
        parts = definition_str["Fn::Join"][1]
        return "".join(
            str(p) if isinstance(p, str) else json.dumps(p) for p in parts
        )
    return json.dumps(definition_str)


def test_update_status_completed_includes_output_key(template):
    """UpdateStatusCompleted DynamoDB update should include outputKey from Lambda result."""
    definition_text = _get_state_definition_text(template)
    assert "$.processAudioResult.Payload.outputKey" in definition_text, (
        "UpdateStatusCompleted must include outputKey from Lambda result"
    )


def test_update_status_completed_includes_output_bucket(template):
    """UpdateStatusCompleted DynamoDB update should include outputBucket from Lambda result."""
    definition_text = _get_state_definition_text(template)
    assert "$.processAudioResult.Payload.outputBucket" in definition_text, (
        "UpdateStatusCompleted must include outputBucket from Lambda result"
    )


def test_update_status_completed_includes_file_size(template):
    """UpdateStatusCompleted DynamoDB update should include fileSize from Lambda result."""
    definition_text = _get_state_definition_text(template)
    assert "$.processAudioResult.Payload.fileSize" in definition_text, (
        "UpdateStatusCompleted must include fileSize from Lambda result"
    )
