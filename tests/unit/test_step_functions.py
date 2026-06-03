import json

from aws_cdk.assertions import Match


def test_state_machine_resource_exists(template):
    """A Step Functions state machine resource is synthesized."""
    template.resource_count_is("AWS::StepFunctions::StateMachine", 1)


def test_state_machine_definition_contains_polly_task(template):
    """The state machine definition references the Polly service via aws-sdk integration."""
    sm_resources = template.find_resources("AWS::StepFunctions::StateMachine")
    assert len(sm_resources) == 1
    resource = list(sm_resources.values())[0]
    definition_str = resource["Properties"]["DefinitionString"]
    # The definition may be an Fn::Join intrinsic; flatten it to check contents
    definition_text = json.dumps(definition_str)
    assert "aws-sdk:polly:startSpeechSynthesisTask" in definition_text
    assert "PollyTask" in definition_text


def test_state_machine_has_logging_configured(template):
    """The state machine has a LoggingConfiguration with a log group destination."""
    template.has_resource_properties(
        "AWS::StepFunctions::StateMachine",
        {
            "LoggingConfiguration": {
                "Destinations": Match.array_with(
                    [
                        {
                            "CloudWatchLogsLogGroup": {
                                "LogGroupArn": Match.any_value(),
                            }
                        }
                    ]
                ),
                "Level": "ALL",
            }
        },
    )


def test_eventbridge_rule_targets_state_machine(template):
    """The EventBridge rule targets the Step Functions state machine."""
    template.has_resource_properties(
        "AWS::Events::Rule",
        {
            "Targets": Match.array_with(
                [
                    Match.object_like(
                        {
                            "Arn": Match.object_like(
                                {"Ref": Match.string_like_regexp(".*StateMachine.*")}
                            ),
                            "RoleArn": Match.any_value(),
                        }
                    )
                ]
            ),
        },
    )


def test_state_machine_role_has_polly_permissions(template):
    """The state machine execution role has least-privilege Polly permissions."""
    template.has_resource_properties(
        "AWS::IAM::Policy",
        {
            "PolicyDocument": {
                "Statement": Match.array_with(
                    [
                        Match.object_like(
                            {
                                "Action": "polly:startSpeechSynthesisTask",
                                "Effect": "Allow",
                            }
                        )
                    ]
                )
            }
        },
    )


def test_eventbridge_target_has_input_transformation(template):
    """The EventBridge target passes event detail as input to the state machine."""
    template.has_resource_properties(
        "AWS::Events::Rule",
        {
            "Targets": Match.array_with(
                [
                    Match.object_like(
                        {
                            "Arn": Match.any_value(),
                            "Input": Match.absent(),
                            "InputPath": "$.detail",
                        }
                    )
                ]
            ),
        },
    )


def test_eventbridge_rule_does_not_target_log_group(template):
    """The EventBridge rule must NOT target a CloudWatch Log Group (old placeholder removed)."""
    rules = template.find_resources("AWS::Events::Rule")
    assert len(rules) >= 1
    for rule in rules.values():
        targets = rule["Properties"].get("Targets", [])
        for target in targets:
            arn = target.get("Arn", {})
            # A log group target ARN would reference a Logs LogGroup resource via Fn::GetAtt
            if isinstance(arn, dict) and "Fn::GetAtt" in arn:
                ref_parts = arn["Fn::GetAtt"]
                # Ensure the target does not reference a LogGroup resource
                assert "LogGroup" not in ref_parts[0], (
                    f"EventBridge rule should not target a CloudWatch Log Group, "
                    f"but found target referencing {ref_parts[0]}"
                )
