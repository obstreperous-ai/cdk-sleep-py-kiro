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
