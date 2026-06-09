import pytest
import aws_cdk as cdk
import aws_cdk.assertions as assertions
from cdk_base.cdk_base_stack import CdkBaseStack


@pytest.fixture
def app():
    return cdk.App()


@pytest.fixture
def template(app):
    stack = CdkBaseStack(app, "TestStack")
    return assertions.Template.from_stack(stack)


@pytest.fixture
def env_app():
    """Factory fixture that creates an App with specific environment context."""
    def _create_app(environment):
        return cdk.App(context={"environment": environment})
    return _create_app


@pytest.fixture
def env_template():
    """Factory fixture that creates a template for a specific environment."""
    def _create_template(environment):
        app = cdk.App(context={"environment": environment})
        stack = CdkBaseStack(app, f"{environment.capitalize()}Stack")
        return assertions.Template.from_stack(stack)
    return _create_template


@pytest.fixture
def pipeline_template():
    """Synthesize a template from PipelineStack."""
    from cdk_base.pipeline_stack import PipelineStack
    app = cdk.App()
    stack = PipelineStack(app, "TestPipelineStack")
    return assertions.Template.from_stack(stack)
