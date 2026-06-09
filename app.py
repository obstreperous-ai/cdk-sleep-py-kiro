#!/usr/bin/env python3
import os

import aws_cdk as cdk

from cdk_base.cdk_base_stack import CdkBaseStack
from cdk_base.pipeline_stack import PipelineStack


app = cdk.App()

# Read environment context, default to 'dev'
environment = app.node.try_get_context("environment") or "dev"

CdkBaseStack(app, f"CdkBaseStack-{environment}",
    # If you don't specify 'env', this stack will be environment-agnostic.
    # Account/Region-dependent features and context lookups will not work,
    # but a single synthesized template can be deployed anywhere.

    # Uncomment the next line to specialize this stack for the AWS Account
    # and Region that are implied by the current CLI configuration.

    #env=cdk.Environment(account=os.getenv('CDK_DEFAULT_ACCOUNT'), region=os.getenv('CDK_DEFAULT_REGION')),

    # Uncomment the next line if you know exactly what Account and Region you
    # want to deploy the stack to. */

    #env=cdk.Environment(account='123456789012', region='us-east-1'),

    # For more information, see https://docs.aws.amazon.com/cdk/latest/guide/environments.html
    )

# Conditionally instantiate PipelineStack when context 'deploy_pipeline' is 'true'
deploy_pipeline = app.node.try_get_context("deploy_pipeline")
if deploy_pipeline == "true":
    PipelineStack(app, "PipelineStack")

app.synth()
