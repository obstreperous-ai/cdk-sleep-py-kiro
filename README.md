# Event-Driven Sleep Audio Pipeline

A serverless pipeline built with AWS CDK (Python) for processing audio content intended for sleep and relaxation applications. Users upload raw audio files or text scripts to an S3 bucket, and the system automatically processes them through a multi-step workflow -- validating inputs, converting text to speech via Amazon Polly, storing processed audio, tracking metadata, and sending notifications on completion or failure.

## Architecture Overview

The pipeline follows an event-driven, loosely coupled design:

1. **Upload** -- Audio or text files land in the S3 input bucket
2. **Event Detection** -- EventBridge captures the `ObjectCreated` event and triggers a Step Functions state machine
3. **Processing** -- A Lambda function validates, processes (audio passthrough or Polly TTS), and uploads output
4. **Metadata** -- DynamoDB tracks the lifecycle of each file (PROCESSING, COMPLETED, FAILED)
5. **Notification** -- KMS-encrypted SNS topics alert subscribers of success or failure

For the full system design, diagrams, and service rationale, see **[ARCHITECTURE.md](./ARCHITECTURE.md)**.

## Key Features

- **S3 upload trigger** via EventBridge (no polling)
- **Step Functions orchestration** with retry policies and error handling
- **Lambda processing** with dual-mode behavior (audio passthrough and text-to-speech)
- **Amazon Polly TTS** for converting text scripts into natural-sounding audio
- **DynamoDB metadata tracking** with full lifecycle status updates
- **KMS-encrypted SNS notifications** for success and failure events
- **Multi-environment support** (dev, stage, prod) via CDK context
- **CDK Pipeline** for self-mutating CI/CD deployments
- **CloudWatch alarms** for state machine failures and Lambda errors
- **X-Ray tracing** for end-to-end distributed tracing

## Prerequisites

- Python 3.11 (managed via pyenv)
- Node.js 22 (for AWS CDK CLI)
- AWS CDK CLI (`npm install -g aws-cdk@2`)
- AWS account with configured credentials
- boto3 (for Lambda handler development/testing)

## Quick Start

```bash
# Set Python version
pyenv local 3.11.15

# Install dependencies
pip install -r requirements.txt -r requirements-dev.txt
pip install boto3 botocore

# Run the test suite
NODE_OPTIONS='' pytest tests/ -q

# Synthesize CloudFormation (dev environment)
NODE_OPTIONS='' npx cdk synth -c environment=dev --quiet
```

> **Note:** The `NODE_OPTIONS=''` prefix is required to avoid a proxy-bootstrap.js error in this environment.

## Deployment

Deploy to any environment using CDK context:

```bash
# Development
cdk deploy -c environment=dev

# Staging
cdk deploy -c environment=stage

# Production
cdk deploy -c environment=prod
```

Each environment has different configurations for log retention, removal policies, and alarm actions. See [ARCHITECTURE.md](./ARCHITECTURE.md#multi-environment-support) for details.

### CDK Pipeline (Self-Mutating)

For automated deployments via CodePipeline:

```bash
cdk deploy PipelineStack -c deploy_pipeline=true
```

The pipeline connects to GitHub via CodeStar Connections and automatically deploys on push.

## Testing

This project follows a **TDD-first** approach. All infrastructure and Lambda logic is covered by tests written before implementation.

```bash
# Run all tests
NODE_OPTIONS='' pytest tests/ -q

# Run with coverage
NODE_OPTIONS='' pytest tests/ --cov=cdk_base --cov=lambda -q

# Run a specific test file
NODE_OPTIONS='' pytest tests/unit/test_e2e_flow.py -q
```

The test suite uses:
- `aws_cdk.assertions` for validating synthesized CloudFormation templates
- `unittest.mock` for Lambda handler tests with mocked AWS services
- Shared fixtures in `tests/conftest.py` for template generation
- `pytest-cov` for coverage reporting

## CI/CD

A GitHub Actions workflow (`.github/workflows/ci.yml`) runs on every push and pull request:

1. Installs Python 3.11 and Node.js 22
2. Installs all dependencies
3. Runs the full test suite (`pytest tests/`)
4. Validates CDK synthesis for all three environments (dev, stage, prod)

This ensures that all environment configurations produce valid CloudFormation before merging.

## Project Structure

```
cdk-sleep-py-kiro/
  app.py                          # CDK app entry point
  cdk.json                        # CDK configuration and context
  requirements.txt                # Runtime dependencies (aws-cdk-lib, constructs)
  requirements-dev.txt            # Dev dependencies (pytest, pytest-cov)
  cdk_base/
    __init__.py
    cdk_base_stack.py             # Main stack (S3, EventBridge, Step Functions, Lambda, DynamoDB, SNS, CloudWatch)
    pipeline_stack.py             # CDK Pipeline stack (self-mutating CI/CD)
  lambda/
    sleep_audio_processor/
      handler.py                  # Lambda handler (validation, audio processing, Polly TTS)
  tests/
    __init__.py
    conftest.py                   # Shared pytest fixtures (template generation per environment)
    unit/
      __init__.py
      test_cdk_base_stack.py      # Core stack resource tests
      test_step_functions.py      # State machine definition tests
      test_dynamodb_metadata.py   # DynamoDB table configuration tests
      test_sns_notifications.py   # SNS topic and encryption tests
      test_lambda_integration.py  # Lambda permissions and configuration tests
      test_lambda_handler.py      # Lambda handler unit tests (mocked AWS)
      test_audio_processing.py    # Audio processing logic tests
      test_audio_processing_infra.py  # Audio processing infrastructure tests
      test_multi_environment.py   # Multi-environment configuration tests
      test_pipeline_construct.py  # CDK Pipeline construct tests
      test_pipeline_validation.py # Pipeline validation tests
      test_pipeline_e2e.py        # End-to-end pipeline state machine tests
      test_e2e_flow.py            # End-to-end Lambda flow tests (mocked services)
      test_error_handling_observability.py  # Error handling, retries, alarms, X-Ray tests
  .github/
    workflows/
      ci.yml                      # GitHub Actions CI workflow
  ARCHITECTURE.md                 # Full system design and architecture (source of truth)
  AGENT_GUIDELINES.md             # Guidelines for AI agents and contributors
  SUMMARY.md                      # Project summary and key decisions
```

## Supported Audio Formats

| Extension | Format | Processing Mode |
|-----------|--------|-----------------|
| `.mp3` | MPEG Audio Layer III | Audio passthrough (download, upload to output) |
| `.wav` | Waveform Audio File | Audio passthrough |
| `.ogg` | Ogg Vorbis | Audio passthrough |
| `.flac` | Free Lossless Audio Codec | Audio passthrough |
| `.txt` | Plain text | Text-to-speech via Amazon Polly (VoiceId: Joanna) |

Files with unsupported extensions are rejected with a validation error. All output is stored in MP3 format with key `processed/{basename}_{uuid}.mp3`.

## Documentation

- **[ARCHITECTURE.md](./ARCHITECTURE.md)** -- Full system design, diagrams, service rationale, and implementation status
- **[AGENT_GUIDELINES.md](./AGENT_GUIDELINES.md)** -- Development guidelines, conventions, and troubleshooting
- **[SUMMARY.md](./SUMMARY.md)** -- Project summary, key decisions, and experiment notes

## License

This project is provided as-is for educational and experimental purposes.
