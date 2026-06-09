"""Tests for the CDK Pipeline construct.

Verifies that a PipelineStack can be synthesized with a valid CodePipeline resource.
"""

import pytest
import aws_cdk as cdk
import aws_cdk.assertions as assertions

from cdk_base.pipeline_stack import PipelineStack


@pytest.fixture
def pipeline_template():
    """Synthesize a template from PipelineStack."""
    app = cdk.App()
    stack = PipelineStack(app, "TestPipelineStack")
    return assertions.Template.from_stack(stack)


class TestPipelineStackImport:
    """PipelineStack can be imported and instantiated."""

    def test_pipeline_stack_can_be_imported(self):
        """PipelineStack can be imported from cdk_base.pipeline_stack."""
        from cdk_base.pipeline_stack import PipelineStack as PS
        assert PS is not None

    def test_pipeline_stack_instantiates(self):
        """PipelineStack instantiates without errors."""
        app = cdk.App()
        stack = PipelineStack(app, "InstantiateTestStack")
        assert stack is not None


class TestPipelineSynthesis:
    """Pipeline stack synthesizes valid CloudFormation."""

    def test_codepipeline_resource_exists(self, pipeline_template):
        """The pipeline stack contains a CodePipeline resource."""
        pipeline_template.resource_count_is("AWS::CodePipeline::Pipeline", 1)

    def test_pipeline_has_source_stage(self, pipeline_template):
        """The CodePipeline has a Source stage configured."""
        pipeline_template.has_resource_properties(
            "AWS::CodePipeline::Pipeline",
            {
                "Stages": assertions.Match.array_with(
                    [
                        assertions.Match.object_like(
                            {"Name": "Source"}
                        ),
                    ]
                ),
            },
        )

    def test_pipeline_has_build_stage(self, pipeline_template):
        """The CodePipeline has a Build stage configured."""
        pipeline_template.has_resource_properties(
            "AWS::CodePipeline::Pipeline",
            {
                "Stages": assertions.Match.array_with(
                    [
                        assertions.Match.object_like(
                            {"Name": "Build"}
                        ),
                    ]
                ),
            },
        )
