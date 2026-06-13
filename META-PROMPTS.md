# CDK-Focused Meta-Prompting Patterns for IaC Development with AI Agents

This document captures reusable meta-prompting patterns extracted from the Event-Driven Sleep Audio Pipeline project. These patterns are primarily CDK-focused, with notes on adaptation to other Infrastructure as Code frameworks (Terraform, Pulumi, CloudFormation).

---

## Table of Contents

- [Overview](#overview)
- [TDD-First Agent Instructions](#tdd-first-agent-instructions)
- [Issue-Driven Development Template](#issue-driven-development-template)
- [CDK-Specific Agent Rules](#cdk-specific-agent-rules)
- [Reusable Prompt Templates](#reusable-prompt-templates)
  - [Creating New CDK Resources](#creating-new-cdk-resources)
  - [Adding Lambda Handlers](#adding-lambda-handlers)
  - [Writing CDK Assertion Tests](#writing-cdk-assertion-tests)
  - [Multi-Environment Validation](#multi-environment-validation)
- [Adapting to Other Projects](#adapting-to-other-projects)
- [References](#references)

---

## Overview

Meta-prompting for IaC projects is a methodology where structured prompt templates guide AI agents through infrastructure development with consistency and reliability. Instead of ad-hoc instructions, agents receive well-defined patterns that encode:

- **Development workflow** (what order to perform tasks)
- **Quality gates** (what must pass before work is considered complete)
- **Architectural constraints** (what boundaries must not be crossed)
- **Verification steps** (how to confirm correctness)

This approach produced a complete serverless pipeline (S3, EventBridge, Step Functions, Lambda, DynamoDB, SNS, CloudWatch, X-Ray) with nearly 300 passing tests and zero manual console changes.

### Why Meta-Prompting Works for IaC

1. **Repeatability**: The same prompt template produces consistent results across different resources and features
2. **Safety**: TDD-first patterns catch configuration errors before deployment
3. **Traceability**: Issue-driven development creates a clear audit trail from requirement to implementation
4. **Scalability**: New team members (human or AI) can follow the same patterns immediately
5. **Quality**: Strict verification steps prevent incomplete or broken infrastructure from being committed

---

## TDD-First Agent Instructions

The core development cycle that every agent must follow. This template ensures no infrastructure is deployed without test coverage.

### Template

```markdown
## Development Cycle

For every infrastructure change, follow this exact sequence:

1. **Write failing tests first**
   - Define the expected resource properties using `aws_cdk.assertions`
   - Define the expected behavior using `unittest.mock` (for Lambda)
   - Run `pytest tests/ -q` and confirm the new tests FAIL
   - Tests must be specific: assert resource counts, property values, and relationships

2. **Implement minimal code**
   - Add only the CDK resources or Lambda logic needed to make tests pass
   - Do not add resources beyond what the tests require
   - Do not optimize prematurely

3. **Verify all tests pass**
   - Run `pytest tests/ -q` and confirm ALL tests pass (new and existing)
   - Fix any regressions before proceeding

4. **Verify synthesis**
   - Run `cdk synth -c environment=dev --quiet`
   - Run `cdk synth -c environment=stage --quiet`
   - Run `cdk synth -c environment=prod --quiet`
   - All three must succeed

5. **Refactor if needed**
   - Clean up implementation while keeping all tests green
   - Extract shared patterns into helper functions
   - Improve naming and organization

6. **Commit with conventional message**
   - Use `feat:` for new resources or capabilities
   - Use `fix:` for correcting behavior
   - Use `refactor:` for non-functional improvements
   - Use `docs:` for documentation changes
```

### Key Rules

- Never skip the "write failing tests first" step
- Never commit with failing tests
- Never add resources that are not covered by at least one assertion
- The test suite is the source of truth for what the infrastructure should look like

---

## Issue-Driven Development Template

Every piece of work originates from a well-scoped issue. This prevents scope creep and ensures clean git history.

### Template

```markdown
## Issue Structure

### Title
[type]: [concise description of the single concern]

### Body
**Context**: Why this change is needed and where it fits in the architecture.

**Acceptance Criteria**:
- [ ] Specific, testable criterion 1
- [ ] Specific, testable criterion 2
- [ ] All existing tests continue to pass
- [ ] CDK synth succeeds for all environments

**Scope Boundaries**:
- This issue ONLY covers [specific scope]
- It does NOT cover [adjacent concerns that should be separate issues]

**References**:
- Architecture section: [link to relevant ARCHITECTURE.md section]
- Related issues: [links to dependent or related issues]
```

### Rules

1. **Single concern**: Each issue addresses exactly one resource, one behavior, or one fix
2. **Conventional commits**: The resulting commit message matches the issue type (`feat:`, `fix:`, `docs:`, etc.)
3. **Strict ordering**: Issues are resolved in dependency order (you cannot build SNS notifications before the state machine exists)
4. **No speculative work**: Only implement what the issue describes
5. **PR per issue**: Each issue maps to exactly one pull request

### Example Issue

```markdown
Title: feat: add KMS-encrypted SNS notification topics

Context: The pipeline needs to notify subscribers when audio processing
completes or fails. ARCHITECTURE.md specifies two KMS-encrypted SNS topics
integrated with the Step Functions state machine.

Acceptance Criteria:
- [ ] SleepAudioPipelineCompleted SNS topic exists with KMS encryption
- [ ] SleepAudioPipelineFailed SNS topic exists with KMS encryption
- [ ] KMS key has rotation enabled
- [ ] State machine has sns:Publish permission to both topics
- [ ] Tests validate topic count, encryption, and key configuration
- [ ] All existing tests pass
- [ ] CDK synth succeeds for dev, stage, and prod

Scope Boundaries:
- This issue ONLY covers SNS topic creation and encryption
- It does NOT cover Step Functions integration (separate issue)
- It does NOT cover subscriber configuration (future issue)
```

---

## CDK-Specific Agent Rules

Rules that apply specifically to AWS CDK projects. These encode best practices and prevent common mistakes.

### Template

```markdown
## CDK Agent Rules

### Source of Truth
- ARCHITECTURE.md is the authoritative specification for what should exist
- Do NOT add resources not described in ARCHITECTURE.md
- If a new resource is needed, update ARCHITECTURE.md FIRST, then implement

### Multi-Environment Awareness
- All resources must work across dev, stage, and prod environments
- Use `self.node.try_get_context('environment')` for environment-specific configuration
- Test synthesis for ALL environments, not just dev
- Environment differences: log retention, removal policies, alarm actions, feature flags

### No Manual Changes
- All infrastructure is defined in CDK code
- Never create resources through the AWS console
- Never manually edit `cdk.out/` or CloudFormation templates
- Never edit generated files (snapshots, lock files)

### Security (Least Privilege)
- Each Lambda gets a dedicated execution role
- Grant only the specific permissions needed (e.g., `s3:GetObject` on one bucket, not `s3:*`)
- Use CDK L2 construct grant methods (`bucket.grant_read()`, `table.grant_read_write_data()`)
- All S3 buckets block public access
- All data at rest is encrypted (SSE-S3, SSE-KMS, or AWS-managed)
- SNS topics use KMS encryption

### Resource Naming
- Use descriptive construct IDs that indicate purpose (e.g., `SleepAudioInputBucket`, not `Bucket1`)
- Let CDK generate physical names (do not hardcode)
- Stack name follows the pattern: `CdkBaseStack-{environment}`

### Testing Patterns
- Use `Template.from_stack()` to get the synthesized CloudFormation
- Assert resource counts: `template.resource_count_is("AWS::S3::Bucket", 2)`
- Assert properties: `template.has_resource_properties("AWS::Lambda::Function", {...})`
- Parse Step Functions definitions from `Fn::Join` arrays for state machine testing
- Use environment-specific fixtures for multi-environment assertions
```

---

## Reusable Prompt Templates

### Creating New CDK Resources

Use this template when an agent needs to add a new AWS resource to the stack.

```markdown
## Task: Add [Resource Name] to the CDK Stack

### Context
[Brief description of why this resource is needed and how it fits in the pipeline]

### Architecture Reference
See ARCHITECTURE.md section: [section name]

### Steps

1. **Write tests** in `tests/unit/[test_file].py`:
   - Assert the resource exists with correct type
   - Assert key properties (encryption, billing mode, etc.)
   - Assert IAM permissions are correctly scoped
   - Assert environment-specific configuration differences

2. **Implement** in `cdk_base/cdk_base_stack.py`:
   - Add the resource using CDK L2 constructs (prefer L2 over L1)
   - Configure environment-specific settings via CDK context
   - Grant minimum required permissions to other resources
   - Follow existing naming conventions in the stack

3. **Verify**:
   - `pytest tests/ -q` (all tests pass)
   - `cdk synth -c environment=dev --quiet`
   - `cdk synth -c environment=stage --quiet`
   - `cdk synth -c environment=prod --quiet`

4. **Commit**: `feat: add [resource description]`

### Constraints
- Do not modify existing resources unless the new resource requires integration
- Do not break existing tests
- Use L2 constructs unless an L1 escape hatch is absolutely required
```

### Adding Lambda Handlers

Use this template when an agent needs to add or modify a Lambda function.

```markdown
## Task: Add/Modify Lambda Handler for [Purpose]

### Context
[What the Lambda does and where it fits in the processing pipeline]

### Steps

1. **Write Lambda handler tests** in `tests/unit/test_[handler_name].py`:
   - Mock all AWS service clients (S3, DynamoDB, Polly, etc.) using `unittest.mock.patch`
   - Test the happy path with expected input/output
   - Test error cases (missing fields, invalid input, service errors)
   - Test edge cases (empty files, max size, timeout scenarios)

2. **Write CDK integration tests** in `tests/unit/test_lambda_integration.py`:
   - Assert Lambda function exists with correct runtime, memory, timeout
   - Assert environment variables are set correctly
   - Assert IAM permissions are granted (S3 read/write, DynamoDB, etc.)
   - Assert the function is correctly wired to its trigger

3. **Implement the handler** in `lambda/[function_name]/handler.py`:
   - Import only stdlib and boto3 (available in Lambda runtime)
   - Include structured JSON logging with request ID
   - Handle errors gracefully and return structured error responses
   - Keep the handler function thin; extract logic into helper functions

4. **Implement CDK resources** in `cdk_base/cdk_base_stack.py`:
   - Define the Lambda function with appropriate memory and timeout
   - Set environment variables for downstream service names
   - Grant permissions using CDK grant methods
   - Wire to trigger (EventBridge, Step Functions, API Gateway, etc.)

5. **Verify**:
   - `pytest tests/ -q` (all tests pass)
   - `cdk synth -c environment=dev --quiet`

6. **Commit**: `feat: add [Lambda purpose] handler`

### Lambda Best Practices
- Runtime: Python 3.11
- Memory: Start at 512 MB, adjust based on profiling
- Timeout: Match the expected processing time (60s for audio, 30s for validation)
- Logging: Structured JSON with `requestId`, `status`, and relevant business fields
- Error handling: Catch exceptions, log them, update metadata, then re-raise for Step Functions
```

### Writing CDK Assertion Tests

Use this template when an agent needs to write tests for infrastructure.

```markdown
## Task: Write CDK Assertion Tests for [Resource/Feature]

### Context
[What aspect of the infrastructure these tests validate]

### Test Structure

```python
import pytest
from aws_cdk import assertions

class TestResourceName:
    """Tests for [resource description]."""

    def test_resource_exists(self, template):
        """Verify the resource is created."""
        template.resource_count_is("AWS::[Service]::[Resource]", expected_count)

    def test_resource_properties(self, template):
        """Verify key configuration properties."""
        template.has_resource_properties("AWS::[Service]::[Resource]", {
            "PropertyName": "expected_value",
        })

    def test_resource_permissions(self, template):
        """Verify IAM permissions are correctly scoped."""
        template.has_resource_properties("AWS::IAM::Policy", {
            "PolicyDocument": {
                "Statement": assertions.Match.array_with([
                    assertions.Match.object_like({
                        "Action": "service:SpecificAction",
                        "Effect": "Allow",
                    })
                ])
            }
        })

    def test_multi_environment(self, template, stage_template, prod_template):
        """Verify environment-specific configuration."""
        # Assert differences between environments
        pass
```

### Testing Patterns
- Use the `template` fixture from `conftest.py` (generates dev environment by default)
- Use `stage_template` and `prod_template` for multi-environment assertions
- Use `assertions.Match.object_like()` for partial property matching
- Use `assertions.Match.array_with()` for arrays that may contain additional elements
- For Step Functions, parse the `DefinitionString` from `Fn::Join` arrays
```

### Multi-Environment Validation

Use this template when verifying that resources behave correctly across environments.

```markdown
## Task: Validate Multi-Environment Configuration for [Feature]

### Context
The pipeline deploys to dev, stage, and prod with different configurations.
This task verifies that environment-specific settings are applied correctly.

### What Varies by Environment

| Setting | Dev | Stage | Prod |
|---------|-----|-------|------|
| Log retention | 7 days | 30 days | 90 days |
| Removal policy | DESTROY | DESTROY | RETAIN |
| Auto-delete objects | Yes | Yes | No |
| Alarm actions | None | Email | PagerDuty + Email |

### Test Template

```python
class TestMultiEnvironment:
    def test_dev_uses_destroy_policy(self, template):
        # Dev resources should have DeletionPolicy: Delete
        template.has_resource("AWS::DynamoDB::Table", {
            "DeletionPolicy": "Delete"
        })

    def test_prod_uses_retain_policy(self, prod_template):
        # Prod resources should have DeletionPolicy: Retain
        prod_template.has_resource("AWS::DynamoDB::Table", {
            "DeletionPolicy": "Retain"
        })

    def test_log_retention_differs(self, template, prod_template):
        # Dev: 7 days, Prod: 90 days
        template.has_resource_properties("AWS::Logs::LogGroup", {
            "RetentionInDays": 7
        })
        prod_template.has_resource_properties("AWS::Logs::LogGroup", {
            "RetentionInDays": 90
        })
```

### Verification Steps
1. Synthesize all environments: `cdk synth -c environment={dev,stage,prod}`
2. Run multi-environment tests: `pytest tests/unit/test_multi_environment.py -q`
3. Verify no environment produces synthesis errors
```

---

## Adapting to Other Projects

These meta-prompting patterns are not specific to this sleep audio pipeline. They can be adapted to any IaC project by replacing the project-specific details with your own.

### Steps to Adapt

1. **Create your ARCHITECTURE.md**: Document your system design, services, and data flow. This becomes the agent's source of truth.

2. **Write AGENT_GUIDELINES.md**: Define project-specific rules, conventions, and troubleshooting steps. Include:
   - Project structure explanation
   - Naming conventions
   - Testing commands
   - Common pitfalls and their solutions

3. **Adapt the TDD cycle**: The write-test-then-implement pattern works for any IaC tool:
   - **CDK**: `aws_cdk.assertions` for CloudFormation validation
   - **Terraform**: `terraform plan` output parsing, or tools like Terratest
   - **Pulumi**: Built-in unit testing with mocks
   - **CloudFormation**: cfn-lint and taskcat for validation

4. **Apply issue-driven development**: Regardless of the IaC tool:
   - One concern per issue
   - Conventional commits
   - Dependency-ordered implementation
   - Architecture document as the contract

5. **Customize verification steps**: Replace CDK-specific commands with your tool's equivalents:
   - CDK: `cdk synth`, `cdk diff`
   - Terraform: `terraform validate`, `terraform plan`
   - Pulumi: `pulumi preview`
   - CloudFormation: `aws cloudformation validate-template`

### Framework-Specific Adaptations

| Framework | Test Tool | Synth/Plan Command | Key Difference |
|-----------|-----------|-------------------|----------------|
| AWS CDK | `aws_cdk.assertions` | `cdk synth` | Tests operate on synthesized CloudFormation |
| Terraform | Terratest / `terraform plan` | `terraform plan` | Tests operate on plan output or real infrastructure |
| Pulumi | Built-in mocks | `pulumi preview` | Tests run against in-memory resource model |
| CloudFormation | cfn-lint + taskcat | `aws cloudformation validate-template` | Tests validate template syntax and deploy to test accounts |

### Key Principles That Transfer

Regardless of the IaC framework:

1. **Architecture document as contract**: Agents need a single source of truth
2. **TDD prevents drift**: Tests catch configuration errors before deployment
3. **Single-concern issues**: Keeps changes reviewable and reversible
4. **Conventional commits**: Creates readable, searchable history
5. **Multi-environment validation**: Catches environment-specific bugs early
6. **No manual changes**: Everything in code, everything versioned

---

## References

- **[ARCHITECTURE.md](./ARCHITECTURE.md)** -- The source of truth for this project's system design
- **[AGENT_GUIDELINES.md](./AGENT_GUIDELINES.md)** -- Project-specific rules and conventions for agents
- **[SUMMARY.md](./SUMMARY.md)** -- Key decisions and experiment notes
- **[README.md](./README.md)** -- Project overview, quick start, and methodology explanation
