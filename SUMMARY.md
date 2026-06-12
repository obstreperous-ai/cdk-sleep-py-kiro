# Event-Driven Sleep Audio Pipeline -- Summary

## Overview

This project implements a fully serverless audio processing pipeline on AWS, designed for sleep and relaxation content. Users upload raw audio files or text scripts to an S3 bucket, and the system automatically validates, processes, and delivers finished audio -- tracking every step in DynamoDB and notifying subscribers via SNS.

The entire infrastructure is defined as code using AWS CDK (Python), deployed across multiple environments, and developed using a strict test-driven methodology.

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| **Event-driven architecture** | Decouples upload from processing; enables independent scaling and clear separation of concerns |
| **Step Functions for orchestration** | Visual workflow, built-in retry/error handling, state management without custom code |
| **DynamoDB for metadata** | Single-digit millisecond latency, no connection management, flexible schema, on-demand billing |
| **KMS-encrypted SNS** | Ensures notification payloads are encrypted at rest; supports multiple subscriber types |
| **Multi-environment via CDK context** | Single codebase deploys to dev/stage/prod with environment-specific configuration (log retention, removal policies, alarm actions) |
| **Lambda dual-mode processing** | Audio files pass through directly; text files are synthesized via Polly -- both handled by a single Lambda for simplicity |
| **TDD-first development** | Every resource and behavior was tested before implementation, ensuring correctness and enabling safe refactoring |
| **EventBridge over S3 notifications** | Content-based filtering, replay capability, and cleaner integration with Step Functions |
| **CDK Pipeline (self-mutating)** | Pipeline updates itself on push, eliminating manual deployment steps |
| **X-Ray tracing** | End-to-end visibility across Lambda invocations and state machine executions |

## What Was Built

### Infrastructure (CDK Stack)

- **S3 Input Bucket** -- Versioned, SSE-S3 encrypted, EventBridge notifications enabled, public access blocked
- **S3 Output Bucket** -- Versioned, SSE-S3 encrypted, public access blocked, stores all processed audio
- **EventBridge Rule** -- Matches `Object Created` events from the input bucket, triggers Step Functions
- **Step Functions State Machine** -- Full pipeline orchestrator with DynamoDB writes, Lambda invocation, Choice routing, Polly placeholder, SNS notifications, retry policies, and error handling
- **Lambda: SleepAudioProcessor** -- 512MB, 60s timeout, handles validation + audio passthrough + Polly TTS + DynamoDB error tracking
- **DynamoDB Metadata Table** -- On-demand billing, SSE, PITR enabled, tracks file lifecycle (PROCESSING/COMPLETED/FAILED)
- **SNS Topics (2)** -- KMS-encrypted Completed and Failed notification topics
- **KMS Key** -- Dedicated key for SNS encryption with automatic rotation
- **CloudWatch Alarms (2)** -- State machine failures and Lambda errors (5-minute evaluation period)
- **X-Ray Tracing** -- Active on Lambda and state machine

### Lambda Handler

- Input validation (bucket name, object key, file extension)
- Audio file processing (S3 download from input, upload to output with `processed/` prefix)
- Text-to-speech processing (read text from S3, call Polly `synthesize_speech`, upload generated audio)
- DynamoDB failure tracking (writes FAILED status with error message on exceptions)
- Structured JSON logging with request ID correlation

### CDK Pipeline

- Self-mutating CodePipeline defined in `pipeline_stack.py`
- GitHub source via CodeStar Connections
- Synth step (install + cdk synth)
- Application stage deploying the main stack

### CI/CD

- GitHub Actions workflow validating all three environments on every push/PR
- Runs pytest + cdk synth for dev, stage, and prod

### Test Suite (298 tests)

- CDK assertions validating synthesized CloudFormation templates
- Lambda handler unit tests with mocked AWS services
- End-to-end flow tests simulating the full pipeline
- State machine definition parsing and validation
- Multi-environment configuration verification
- Error handling, retry, and observability tests

## TDD Process

The project was developed incrementally with a strict test-first approach:

1. **Write failing tests** -- Define expected resource properties, state machine structure, or Lambda behavior using `aws_cdk.assertions` or `unittest.mock`
2. **Implement minimal code** -- Add CDK resources or Lambda logic to make the tests pass
3. **Refactor** -- Clean up implementation while keeping tests green
4. **Verify synthesis** -- Run `cdk synth` for all environments to confirm valid CloudFormation output
5. **Repeat** -- Move to the next component

This process was applied to every layer of the system: S3 buckets, EventBridge rules, Step Functions state machine (states, transitions, error handling, retries), Lambda handler (validation, processing, Polly integration), DynamoDB integration, SNS notifications, CloudWatch alarms, X-Ray tracing, and the CDK Pipeline.

Key benefits observed:
- Caught configuration errors early (e.g., missing IAM grants, incorrect state machine routing)
- Enabled safe refactoring of the state machine definition as requirements evolved
- Provided documentation of expected behavior through test assertions
- Made multi-environment validation straightforward (synthesize and assert per environment)

## Deployment

```bash
# Prerequisites
pyenv local 3.11.15
pip install -r requirements.txt -r requirements-dev.txt

# Validate
NODE_OPTIONS='' pytest tests/ -q
NODE_OPTIONS='' npx cdk synth -c environment=dev --quiet

# Deploy
cdk deploy -c environment=dev      # Development
cdk deploy -c environment=stage    # Staging
cdk deploy -c environment=prod     # Production

# Pipeline (self-mutating)
cdk deploy PipelineStack -c deploy_pipeline=true
```

## Future Work

Possible extensions documented in the architecture:

- **Audio streaming** -- CloudFront distribution for low-latency playback
- **User preferences** -- Extend DynamoDB schema for preferred audio profiles
- **Batch processing** -- SQS queues for bulk upload handling
- **Content library** -- Catalog with search via OpenSearch
- **Mobile integration** -- API Gateway + Cognito for authenticated access
- **Analytics** -- Kinesis Data Firehose for usage data and recommendations
- **Multi-region** -- DynamoDB global tables and S3 cross-region replication
- **Webhooks** -- SNS HTTP/HTTPS subscriptions for third-party integrations
- **Advanced TTS workflows** -- Use the Step Functions Polly task (currently placeholder) for batch synthesis or long-form content generation

## Experiment Notes

Observations useful for reference or final reporting:

- **NODE_OPTIONS quirk**: The development environment requires `NODE_OPTIONS=''` before any Node.js/CDK command due to a proxy-bootstrap.js injection. The CI workflow handles this by setting `NODE_OPTIONS: ""` as an env variable.
- **State machine definition parsing**: The Step Functions definition is stored as `Fn::Join` in CloudFormation with placeholder references. Tests parse this by joining array elements and replacing CFN references with `PLACEHOLDER` strings.
- **Polly task as placeholder**: The Step Functions `CallAwsService` Polly integration exists as a placeholder for future advanced workflows. Actual Polly TTS is handled directly by the Lambda for simplicity and testability.
- **DynamoDB dual-write pattern**: The Lambda writes FAILED status directly on errors, while Step Functions writes COMPLETED status via `UpdateStatusCompleted`. This ensures failure metadata is always captured even if the state machine itself encounters issues.
- **Test count**: 298 tests covering all infrastructure resources, Lambda behavior, error scenarios, and multi-environment configurations.
- **boto3 not in requirements.txt**: boto3 is available in the Lambda runtime but must be installed separately for local testing. This is intentional to keep the deployment package small.
- **Multi-environment synthesis**: All three environments (dev, stage, prod) produce valid CloudFormation with different configurations for log retention (7/30/90 days), removal policies (DESTROY/RETAIN), and alarm actions.
