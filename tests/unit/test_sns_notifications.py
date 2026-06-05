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
