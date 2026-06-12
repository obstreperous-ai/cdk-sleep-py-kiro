# Agent Guidelines

This document provides guidelines for AI agents and contributors working on the Event-Driven Sleep Audio Pipeline project.

## Source of Truth

**[ARCHITECTURE.md](./ARCHITECTURE.md)** is the authoritative reference for the system design, data flow, service choices, and infrastructure patterns. All implementation work must align with the architecture described there.

When implementing features or resolving issues:

1. Read `ARCHITECTURE.md` first to understand where the change fits in the overall system
2. Follow the documented data flow and service boundaries
3. Respect the security model (least privilege, encryption at rest, private buckets)
4. Maintain consistency between the architecture documentation and the deployed infrastructure

## Development Principles

- **TDD-first**: Write failing tests using `aws_cdk.assertions` before adding any CDK resources
- **Incremental delivery**: Each pull request should address a single concern or resource
- **No manual changes**: All infrastructure must be defined in CDK stacks
- **Multi-environment aware**: All resources must support `dev`, `stage`, and `prod` via CDK context

## Project Structure

```
cdk-sleep-py-kiro/
  app.py                          # CDK app entry point
  cdk.json                        # CDK configuration and context
  requirements.txt                # Runtime dependencies (aws-cdk-lib, constructs)
  requirements-dev.txt            # Dev dependencies (pytest, pytest-cov)
  cdk_base/
    __init__.py
    cdk_base_stack.py             # Main stack definition (all resources)
    pipeline_stack.py             # CDK Pipeline stack (self-mutating CI/CD)
  lambda/
    sleep_audio_processor/
      handler.py                  # Lambda handler (validation, processing, Polly TTS)
  tests/
    __init__.py
    conftest.py                   # Shared pytest fixtures (template per environment)
    unit/
      __init__.py
      test_cdk_base_stack.py      # Core stack resource tests
      test_step_functions.py      # State machine definition tests
      test_dynamodb_metadata.py   # DynamoDB table tests
      test_sns_notifications.py   # SNS and KMS tests
      test_lambda_integration.py  # Lambda permission and config tests
      test_lambda_handler.py      # Lambda handler unit tests
      test_audio_processing.py    # Audio processing logic tests
      test_audio_processing_infra.py  # Audio infra (S3/Polly grants) tests
      test_multi_environment.py   # Multi-environment config tests
      test_pipeline_construct.py  # CDK Pipeline construct tests
      test_pipeline_validation.py # Pipeline validation tests
      test_pipeline_e2e.py        # End-to-end state machine tests
      test_e2e_flow.py            # End-to-end Lambda flow tests
      test_error_handling_observability.py  # Error handling and observability tests
  .github/
    workflows/
      ci.yml                      # GitHub Actions CI workflow
  ARCHITECTURE.md                 # System design (source of truth)
  AGENT_GUIDELINES.md             # This file
  SUMMARY.md                      # Project summary and key decisions
```

## Implementation Workflow

1. Reference `ARCHITECTURE.md` to understand the target architecture
2. Write a failing test for the new resource or behavior
3. Implement the minimal CDK code to make the test pass
4. Verify with `pytest tests/` and `cdk synth`
5. Update `ARCHITECTURE.md` if the implementation introduces design changes

## Conventions

- Stack code lives in `cdk_base/`
- Tests live in `tests/unit/` and use fixtures from `tests/conftest.py`
- Python dependencies go in `requirements.txt` (runtime) or `requirements-dev.txt` (testing)
- CDK context values control environment-specific behavior
- Commit messages use type prefixes: `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`

## Dependencies

### requirements.txt (Runtime)

Contains the core dependencies needed for CDK synthesis and deployment:
- `aws-cdk-lib` -- the AWS CDK library
- `constructs` -- CDK constructs base library

### requirements-dev.txt (Development/Testing)

Contains testing and development tools:
- `pytest` -- test runner
- `pytest-cov` -- coverage reporting

### Additional Dependencies

- `boto3` and `botocore` -- required for Lambda handler tests (mocking AWS service calls)
- These are available at runtime in the Lambda execution environment but must be installed locally for testing

Install everything:

```bash
pip install -r requirements.txt -r requirements-dev.txt
pip install boto3 botocore
```

## Testing

### Running Tests

```bash
# Run all tests
NODE_OPTIONS='' pytest tests/ -q

# Run with verbose output
NODE_OPTIONS='' pytest tests/ -v

# Run a specific test file
NODE_OPTIONS='' pytest tests/unit/test_lambda_handler.py -q

# Run with coverage
NODE_OPTIONS='' pytest tests/ --cov=cdk_base --cov=lambda -q
```

### Key Points

- **NODE_OPTIONS must be unset** (or set to empty string) when running any CDK-related commands to avoid a proxy-bootstrap.js error
- **boto3 must be installed** for Lambda handler tests (`test_lambda_handler.py`, `test_audio_processing.py`, `test_e2e_flow.py`)
- Tests use `aws_cdk.assertions.Template` to validate synthesized CloudFormation
- Lambda handler tests use `unittest.mock.patch` to mock boto3 clients
- Fixtures in `tests/conftest.py` generate templates for each environment

### CDK Synthesis

```bash
# Synthesize for any environment
NODE_OPTIONS='' npx cdk synth -c environment=dev --quiet
NODE_OPTIONS='' npx cdk synth -c environment=stage --quiet
NODE_OPTIONS='' npx cdk synth -c environment=prod --quiet
```

## Common Issues / Troubleshooting

### NODE_OPTIONS proxy-bootstrap.js error

**Problem:** Running `npx cdk synth` or `pytest` fails with an error referencing `proxy-bootstrap.js`.

**Solution:** Prefix all Node.js/CDK commands with `NODE_OPTIONS=''`:

```bash
NODE_OPTIONS='' npx cdk synth -c environment=dev --quiet
NODE_OPTIONS='' pytest tests/ -q
```

### boto3 import errors in Lambda tests

**Problem:** Tests in `test_lambda_handler.py`, `test_audio_processing.py`, or `test_e2e_flow.py` fail with `ModuleNotFoundError: No module named 'boto3'`.

**Solution:** Install boto3 locally (it is available in the Lambda runtime but not included in `requirements.txt`):

```bash
pip install boto3 botocore
```

### Python version mismatch

**Problem:** CDK synthesis or tests fail due to Python version incompatibilities.

**Solution:** Ensure Python 3.11 is active via pyenv:

```bash
pyenv local 3.11.15
python --version  # Should show Python 3.11.15
```

### CDK CLI not found

**Problem:** `cdk` command not found or version mismatch.

**Solution:** Install the CDK CLI globally or use npx:

```bash
npm install -g aws-cdk@2
# or
npx cdk synth -c environment=dev
```

### Tests pass locally but fail in CI

**Problem:** Tests pass on your machine but fail in GitHub Actions.

**Solution:** The CI workflow sets `NODE_OPTIONS: ""` as an environment variable. Ensure you are running the same Python (3.11) and Node.js (22) versions locally.

## What Not to Do

- Do not add resources that are not described in `ARCHITECTURE.md` without updating the architecture first
- Do not use inline policies when managed policies or resource-based policies are sufficient
- Do not skip tests for infrastructure changes
- Do not hardcode environment-specific values; use CDK context
- Do not create public S3 buckets or overly permissive IAM roles
- Do not manually edit `cdk.out/` or other generated files
