import json

from aws_cdk.assertions import Match


def test_sns_topics_exist(template):
    """Verify exactly 2 SNS topics exist."""
    template.resource_count_is("AWS::SNS::Topic", 2)


def test_sns_topics_have_kms_encryption(template):
    """Verify both SNS topics have KMS encryption configured."""
    topics = template.find_resources("AWS::SNS::Topic")
    assert len(topics) == 2, f"Expected 2 SNS topics, found {len(topics)}"
    for logical_id, topic in topics.items():
        props = topic.get("Properties", {})
        assert "KmsMasterKeyId" in props, (
            f"SNS topic {logical_id} does not have KmsMasterKeyId property"
        )


def test_state_machine_definition_contains_sns_publish(template):
    """Verify state machine definition contains sns:Publish action."""
    sm_resources = template.find_resources("AWS::StepFunctions::StateMachine")
    assert len(sm_resources) == 1
    resource = list(sm_resources.values())[0]
    definition_text = json.dumps(resource["Properties"]["DefinitionString"])
    assert "sns:publish" in definition_text


def test_state_machine_has_publish_completed_notification(template):
    """Verify PublishCompletedNotification appears in state machine definition."""
    sm_resources = template.find_resources("AWS::StepFunctions::StateMachine")
    resource = list(sm_resources.values())[0]
    definition_text = json.dumps(resource["Properties"]["DefinitionString"])
    assert "PublishCompletedNotification" in definition_text


def test_state_machine_has_publish_failed_notification(template):
    """Verify PublishFailedNotification appears in state machine definition."""
    sm_resources = template.find_resources("AWS::StepFunctions::StateMachine")
    resource = list(sm_resources.values())[0]
    definition_text = json.dumps(resource["Properties"]["DefinitionString"])
    assert "PublishFailedNotification" in definition_text


def test_state_machine_role_has_sns_publish_permission(template):
    """Verify IAM policy grants sns:Publish permission to the state machine role."""
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


def test_state_machine_notification_ordering(template):
    """Verify UpdateStatusCompleted before PublishCompletedNotification, and UpdateStatusFailed before PublishFailedNotification."""
    sm_resources = template.find_resources("AWS::StepFunctions::StateMachine")
    resource = list(sm_resources.values())[0]
    definition_text = json.dumps(resource["Properties"]["DefinitionString"])

    update_completed_pos = definition_text.index("UpdateStatusCompleted")
    publish_completed_pos = definition_text.index("PublishCompletedNotification")
    assert update_completed_pos < publish_completed_pos, (
        "UpdateStatusCompleted must appear before PublishCompletedNotification"
    )

    update_failed_pos = definition_text.index("UpdateStatusFailed")
    publish_failed_pos = definition_text.index("PublishFailedNotification")
    assert update_failed_pos < publish_failed_pos, (
        "UpdateStatusFailed must appear before PublishFailedNotification"
    )


def test_state_machine_still_has_catch_blocks(template):
    """Verify the state machine definition still has Catch blocks for error handling."""
    sm_resources = template.find_resources("AWS::StepFunctions::StateMachine")
    resource = list(sm_resources.values())[0]
    definition_text = json.dumps(resource["Properties"]["DefinitionString"])
    assert "Catch" in definition_text


def test_state_machine_role_has_kms_permissions(template):
    """Verify the state machine role has KMS permissions for the SNS encryption key."""
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


def test_publish_completed_notification_has_catch(template):
    """Verify PublishCompletedNotification has a Catch block for error handling."""
    sm_resources = template.find_resources("AWS::StepFunctions::StateMachine")
    resource = list(sm_resources.values())[0]
    definition_str = resource["Properties"]["DefinitionString"]
    if isinstance(definition_str, dict) and "Fn::Join" in definition_str:
        parts = definition_str["Fn::Join"][1]
        resolved = "".join(str(p) if isinstance(p, str) else json.dumps(p) for p in parts)
    else:
        resolved = json.dumps(definition_str)

    # Find the state definition for PublishCompletedNotification (the actual state, not references)
    # The state definition pattern: "PublishCompletedNotification":{"Next":... or "End":...
    state_marker = '"PublishCompletedNotification":{"'
    assert state_marker in resolved, (
        "Could not find PublishCompletedNotification state definition"
    )
    state_start = resolved.index(state_marker)
    section_after = resolved[state_start:state_start + 800]
    assert "Catch" in section_after, (
        "PublishCompletedNotification should have a Catch block for error handling"
    )


def test_publish_failed_notification_has_catch(template):
    """Verify PublishFailedNotification has a Catch block for error handling."""
    sm_resources = template.find_resources("AWS::StepFunctions::StateMachine")
    resource = list(sm_resources.values())[0]
    definition_str = resource["Properties"]["DefinitionString"]
    if isinstance(definition_str, dict) and "Fn::Join" in definition_str:
        parts = definition_str["Fn::Join"][1]
        resolved = "".join(str(p) if isinstance(p, str) else json.dumps(p) for p in parts)
    else:
        resolved = json.dumps(definition_str)

    # Find the state definition for PublishFailedNotification (the actual state, not references)
    state_marker = '"PublishFailedNotification":{"'
    assert state_marker in resolved, (
        "Could not find PublishFailedNotification state definition"
    )
    state_start = resolved.index(state_marker)
    section_after = resolved[state_start:state_start + 800]
    assert "Catch" in section_after, (
        "PublishFailedNotification should have a Catch block for error handling"
    )


def test_sns_result_paths_are_distinct(template):
    """Verify the two SNS publish tasks use distinct result paths to avoid collision."""
    import re

    sm_resources = template.find_resources("AWS::StepFunctions::StateMachine")
    resource = list(sm_resources.values())[0]
    definition_str = resource["Properties"]["DefinitionString"]
    if isinstance(definition_str, dict) and "Fn::Join" in definition_str:
        parts = definition_str["Fn::Join"][1]
        resolved = "".join(str(p) if isinstance(p, str) else json.dumps(p) for p in parts)
    else:
        resolved = json.dumps(definition_str)

    # Find the actual state definitions (not "Next" references)
    completed_marker = '"PublishCompletedNotification":{"'
    failed_marker = '"PublishFailedNotification":{"'
    assert completed_marker in resolved
    assert failed_marker in resolved

    completed_start = resolved.index(completed_marker)
    failed_start = resolved.index(failed_marker)

    # Extract sections starting from the state definitions
    completed_section = resolved[completed_start:completed_start + 800]
    failed_section = resolved[failed_start:failed_start + 800]

    # Look for the primary ResultPath (after "Type":"Task"), not the Catch block's ResultPath
    # Pattern: "Type":"Task","ResultPath":"$.xxx" - the primary ResultPath for the state
    completed_match = re.search(
        r'"Type":"Task","ResultPath":"\$\.([\w]+)"', completed_section
    )
    failed_match = re.search(
        r'"Type":"Task","ResultPath":"\$\.([\w]+)"', failed_section
    )

    assert completed_match is not None, (
        "Could not find primary ResultPath for PublishCompletedNotification"
    )
    assert failed_match is not None, (
        "Could not find primary ResultPath for PublishFailedNotification"
    )
    assert completed_match.group(1) != failed_match.group(1), (
        f"Both SNS publish tasks use the same ResultPath '$.{completed_match.group(1)}' - "
        "they should have distinct paths to avoid data collision"
    )
