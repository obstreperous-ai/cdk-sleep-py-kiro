"""CDK Pipeline stack for deploying the Sleep Audio Pipeline.

Defines a self-mutating CodePipeline that deploys the CdkBaseStack
through application stages.
"""

from aws_cdk import Stack, Stage
from aws_cdk import pipelines
from constructs import Construct

from cdk_base.cdk_base_stack import CdkBaseStack


class ApplicationStage(Stage):
    """Application stage containing the CdkBaseStack."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        CdkBaseStack(self, "CdkBaseStack")


class PipelineStack(Stack):
    """CDK Pipeline stack with source, synth, and deployment stages."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Source: GitHub repository via CodeStar connection
        source = pipelines.CodePipelineSource.connection(
            "owner/cdk-sleep-py-kiro",
            "main",
            connection_arn="arn:aws:codestar-connections:us-east-1:123456789012:connection/placeholder",
        )

        # Synth step: install dependencies and synthesize
        synth = pipelines.ShellStep(
            "Synth",
            input=source,
            commands=[
                "pip install -r requirements.txt",
                "npx cdk synth",
            ],
        )

        # Create the pipeline
        pipeline = pipelines.CodePipeline(
            self,
            "Pipeline",
            synth=synth,
        )

        # Add application stage
        pipeline.add_stage(ApplicationStage(self, "Deploy"))
