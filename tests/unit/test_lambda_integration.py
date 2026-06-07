import json

from aws_cdk.assertions import Match


def test_lambda_function_exists(template):
    """Verify a Lambda function resource exists with the expected runtime."""
    template.has_resource_properties(
        "AWS::Lambda::Function",
        {"Runtime": "python3.11", "Handler": "handler.lambda_handler"},
    )


def test_lambda_function_has_python_runtime(template):
    """Verify the Lambda function uses Python 3.11 runtime."""
    template.has_resource_properties(
        "AWS::Lambda::Function",
        {"Runtime": "python3.11"},
    )


def test_lambda_function_has_handler_configured(template):
    """Verify the Lambda function has a handler entry point."""
    template.has_resource_properties(
        "AWS::Lambda::Function",
        {"Handler": "handler.lambda_handler"},
    )


def test_lambda_function_has_table_name_env_var(template):
    """Verify the Lambda function has TABLE_NAME environment variable."""
    template.has_resource_properties(
        "AWS::Lambda::Function",
        {
            "Environment": {
                "Variables": {
                    "TABLE_NAME": Match.any_value(),
                }
            }
        },
    )


def test_state_machine_definition_contains_lambda_invoke(template):
    """The state machine definition includes a LambdaInvoke task for ProcessAudio."""
    sm_resources = template.find_resources("AWS::StepFunctions::StateMachine")
    assert len(sm_resources) == 1
    resource = list(sm_resources.values())[0]
    definition_str = resource["Properties"]["DefinitionString"]
    definition_text = json.dumps(definition_str)
    assert "ProcessAudio" in definition_text


def test_lambda_invoke_positioned_between_write_and_polly(template):
    """ProcessAudio task appears after WriteInitialRecord and before PollyTask."""
    sm_resources = template.find_resources("AWS::StepFunctions::StateMachine")
    resource = list(sm_resources.values())[0]
    definition_str = resource["Properties"]["DefinitionString"]
    definition_text = json.dumps(definition_str)
    write_pos = definition_text.index("WriteInitialRecord")
    process_pos = definition_text.index("ProcessAudio")
    polly_pos = definition_text.index("PollyTask")
    assert write_pos < process_pos, (
        "WriteInitialRecord must appear before ProcessAudio"
    )
    assert process_pos < polly_pos, (
        "ProcessAudio must appear before PollyTask"
    )


def test_state_machine_role_can_invoke_lambda(template):
    """The state machine execution role has permission to invoke the Lambda."""
    template.has_resource_properties(
        "AWS::IAM::Policy",
        {
            "PolicyDocument": {
                "Statement": Match.array_with(
                    [
                        Match.object_like(
                            {
                                "Action": "lambda:InvokeFunction",
                                "Effect": "Allow",
                            }
                        )
                    ]
                )
            }
        },
    )


def test_lambda_role_has_dynamodb_access(template):
    """The Lambda execution role has DynamoDB read/write permissions."""
    template.has_resource_properties(
        "AWS::IAM::Policy",
        {
            "PolicyDocument": {
                "Statement": Match.array_with(
                    [
                        Match.object_like(
                            {
                                "Action": Match.array_with(
                                    [
                                        "dynamodb:BatchGetItem",
                                        "dynamodb:Query",
                                        "dynamodb:GetItem",
                                        "dynamodb:Scan",
                                        "dynamodb:ConditionCheckItem",
                                        "dynamodb:BatchWriteItem",
                                        "dynamodb:PutItem",
                                        "dynamodb:UpdateItem",
                                        "dynamodb:DeleteItem",
                                        "dynamodb:DescribeTable",
                                    ]
                                ),
                                "Effect": "Allow",
                            }
                        )
                    ]
                )
            }
        },
    )


def test_lambda_invoke_has_catch_for_errors(template):
    """The ProcessAudio Lambda invoke task has error handling (Catch)."""
    sm_resources = template.find_resources("AWS::StepFunctions::StateMachine")
    resource = list(sm_resources.values())[0]
    definition_str = resource["Properties"]["DefinitionString"]
    definition_text = json.dumps(definition_str)
    # Find the ProcessAudio state and verify it has a Catch clause
    # The Catch appears after ProcessAudio in the definition
    process_pos = definition_text.index("ProcessAudio")
    # Find the next state after ProcessAudio (PollyTask)
    polly_pos = definition_text.index("PollyTask")
    # Within the ProcessAudio state definition, there should be a Catch
    process_section = definition_text[process_pos:polly_pos]
    assert "Catch" in process_section, (
        "ProcessAudio task must have a Catch clause for error handling"
    )


def test_lambda_invoke_has_result_path(template):
    """The ProcessAudio Lambda invoke task uses result_path to avoid state clobbering."""
    sm_resources = template.find_resources("AWS::StepFunctions::StateMachine")
    resource = list(sm_resources.values())[0]
    definition_str = resource["Properties"]["DefinitionString"]
    definition_text = json.dumps(definition_str)
    process_pos = definition_text.index("ProcessAudio")
    polly_pos = definition_text.index("PollyTask")
    process_section = definition_text[process_pos:polly_pos]
    assert "ResultPath" in process_section, (
        "ProcessAudio task must have a ResultPath to avoid clobbering state"
    )
