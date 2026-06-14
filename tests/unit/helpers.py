"""Shared test helper utilities for state machine definition parsing."""

import json


def parse_state_machine_definition(template):
    """Extract and parse the state machine definition from a synthesized CDK template.

    Handles both plain string definitions and Fn::Join-based definitions
    (where ARN references are replaced with 'PLACEHOLDER').

    Args:
        template: An aws_cdk.assertions.Template instance.

    Returns:
        dict: The parsed state machine definition JSON.
    """
    sm_resources = template.find_resources("AWS::StepFunctions::StateMachine")
    resource = list(sm_resources.values())[0]
    definition_str = resource["Properties"]["DefinitionString"]
    if isinstance(definition_str, dict) and "Fn::Join" in definition_str:
        parts = definition_str["Fn::Join"][1]
        joined = "".join(
            p if isinstance(p, str) else "PLACEHOLDER" for p in parts
        )
        return json.loads(joined)
    return json.loads(definition_str) if isinstance(definition_str, str) else definition_str
