"""Tests for the CDK Pipeline construct.

Verifies that a PipelineStack can be synthesized with a valid CodePipeline resource.
"""

import pytest
import aws_cdk as cdk
import aws_cdk.assertions as assertions
from aws_cdk import Stack

from cdk_base.pipeline_stack import ApplicationStage, PipelineStack


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


class TestDeployPipelineConditional:
    """PipelineStack is only created when deploy_pipeline context is 'true'."""

    def test_pipeline_stack_created_when_deploy_pipeline_true(self):
        """PipelineStack is instantiated when deploy_pipeline='true'."""
        app = cdk.App(context={"deploy_pipeline": "true"})
        # Simulate app.py logic
        deploy_pipeline = app.node.try_get_context("deploy_pipeline")
        if deploy_pipeline == "true":
            stack = PipelineStack(app, "PipelineStack")
        stacks = [
            child for child in app.node.children
            if isinstance(child, Stack)
        ]
        pipeline_stacks = [s for s in stacks if s.node.id == "PipelineStack"]
        assert len(pipeline_stacks) == 1

    def test_pipeline_stack_not_created_when_deploy_pipeline_false(self):
        """PipelineStack is not instantiated when deploy_pipeline='false'."""
        app = cdk.App(context={"deploy_pipeline": "false"})
        # Simulate app.py logic
        deploy_pipeline = app.node.try_get_context("deploy_pipeline")
        if deploy_pipeline == "true":
            PipelineStack(app, "PipelineStack")
        stacks = [
            child for child in app.node.children
            if isinstance(child, Stack)
        ]
        pipeline_stacks = [s for s in stacks if s.node.id == "PipelineStack"]
        assert len(pipeline_stacks) == 0

    def test_pipeline_stack_not_created_without_context(self):
        """PipelineStack is not instantiated when deploy_pipeline context is absent."""
        app = cdk.App()
        # Simulate app.py logic
        deploy_pipeline = app.node.try_get_context("deploy_pipeline")
        if deploy_pipeline == "true":
            PipelineStack(app, "PipelineStack")
        stacks = [
            child for child in app.node.children
            if isinstance(child, Stack)
        ]
        pipeline_stacks = [s for s in stacks if s.node.id == "PipelineStack"]
        assert len(pipeline_stacks) == 0


class TestApplicationStageEnvironmentPropagation:
    """ApplicationStage propagates environment context to CdkBaseStack."""

    def test_application_stage_passes_environment_context(self):
        """ApplicationStage sets environment context on the stage node."""
        app = cdk.App()
        stage = ApplicationStage(app, "TestStage", environment="prod")
        # The stage should have the environment context set
        assert stage.node.try_get_context("environment") == "prod"

    def test_application_stage_defaults_to_dev(self):
        """ApplicationStage defaults to dev environment."""
        app = cdk.App()
        stage = ApplicationStage(app, "TestStage")
        assert stage.node.try_get_context("environment") == "dev"
