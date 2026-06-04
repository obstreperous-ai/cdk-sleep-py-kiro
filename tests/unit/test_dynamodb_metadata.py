import json

from aws_cdk.assertions import Match


def test_dynamodb_table_exists(template):
    """Verify exactly 1 DynamoDB table resource exists."""
    template.resource_count_is("AWS::DynamoDB::Table", 1)


def test_dynamodb_table_has_correct_key_schema(template):
    """Verify partition key is 'audioId' (S type)."""
    template.has_resource_properties(
        "AWS::DynamoDB::Table",
        {
            "KeySchema": [
                {"AttributeName": "audioId", "KeyType": "HASH"}
            ],
            "AttributeDefinitions": Match.array_with(
                [{"AttributeName": "audioId", "AttributeType": "S"}]
            ),
        },
    )


def test_dynamodb_table_has_on_demand_billing(template):
    """Verify billing mode is PAY_PER_REQUEST."""
    template.has_resource_properties(
        "AWS::DynamoDB::Table",
        {"BillingMode": "PAY_PER_REQUEST"},
    )


def test_dynamodb_table_has_encryption(template):
    """Verify server-side encryption is enabled."""
    template.has_resource_properties(
        "AWS::DynamoDB::Table",
        {"SSESpecification": {"SSEEnabled": True}},
    )


def test_dynamodb_table_has_point_in_time_recovery(template):
    """Verify point-in-time recovery is enabled."""
    template.has_resource_properties(
        "AWS::DynamoDB::Table",
        {"PointInTimeRecoverySpecification": {"PointInTimeRecoveryEnabled": True}},
    )


def test_state_machine_definition_contains_dynamodb_putitem(template):
    """The state machine definition includes a DynamoDB PutItem task."""
    sm_resources = template.find_resources("AWS::StepFunctions::StateMachine")
    assert len(sm_resources) == 1
    resource = list(sm_resources.values())[0]
    definition_str = resource["Properties"]["DefinitionString"]
    definition_text = json.dumps(definition_str)
    # DynamoDB PutItem task uses arn:aws:states:::dynamodb:putItem
    assert "dynamodb:putItem" in definition_text or "PutItem" in definition_text


def test_state_machine_definition_contains_dynamodb_updateitem(template):
    """The state machine definition includes a DynamoDB UpdateItem task."""
    sm_resources = template.find_resources("AWS::StepFunctions::StateMachine")
    assert len(sm_resources) == 1
    resource = list(sm_resources.values())[0]
    definition_str = resource["Properties"]["DefinitionString"]
    definition_text = json.dumps(definition_str)
    # DynamoDB UpdateItem task uses arn:aws:states:::dynamodb:updateItem
    assert "dynamodb:updateItem" in definition_text or "UpdateItem" in definition_text


def test_state_machine_role_has_dynamodb_permissions(template):
    """The state machine role has DynamoDB PutItem and UpdateItem permissions."""
    template.has_resource_properties(
        "AWS::IAM::Policy",
        {
            "PolicyDocument": {
                "Statement": Match.array_with(
                    [
                        Match.object_like(
                            {
                                "Action": Match.string_like_regexp("dynamodb:.*"),
                                "Effect": "Allow",
                            }
                        )
                    ]
                )
            }
        },
    )


def test_state_machine_definition_has_status_processing(template):
    """The state machine definition references PROCESSING status."""
    sm_resources = template.find_resources("AWS::StepFunctions::StateMachine")
    resource = list(sm_resources.values())[0]
    definition_text = json.dumps(resource["Properties"]["DefinitionString"])
    assert "PROCESSING" in definition_text


def test_state_machine_definition_has_status_completed(template):
    """The state machine definition references COMPLETED status."""
    sm_resources = template.find_resources("AWS::StepFunctions::StateMachine")
    resource = list(sm_resources.values())[0]
    definition_text = json.dumps(resource["Properties"]["DefinitionString"])
    assert "COMPLETED" in definition_text


def test_state_machine_definition_has_status_failed(template):
    """The state machine definition references FAILED status."""
    sm_resources = template.find_resources("AWS::StepFunctions::StateMachine")
    resource = list(sm_resources.values())[0]
    definition_text = json.dumps(resource["Properties"]["DefinitionString"])
    assert "FAILED" in definition_text
