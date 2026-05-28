def test_stack_synthesizes_valid_template(template):
    # Verify the stack synthesizes a valid CloudFormation template
    template_json = template.to_json()
    assert isinstance(template_json, dict)
    # An empty CDK stack still produces valid CloudFormation with Parameters and Rules
    assert len(template_json) > 0


def test_stack_has_no_unexpected_resources(template):
    # An empty stack should not contain any unexpected resources
    # CDK Metadata is added by default unless explicitly suppressed
    template_json = template.to_json()
    resources = template_json.get("Resources", {})
    # Only CDKMetadata (if present) should exist in the empty stack
    for resource_id, resource in resources.items():
        assert resource["Type"] == "AWS::CDK::Metadata"
