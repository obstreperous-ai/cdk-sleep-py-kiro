# Experiment Design: AI-Driven IaC Development

## Overview & Goals

This repository is one entry in a broader experiment titled **"5 Languages x 3 AIs"**, which studies how AI coding agents build complex Infrastructure as Code (IaC) projects through structured meta-prompting. The experiment aims to answer:

- How effectively can AI agents produce production-quality IaC from structured prompts?
- What role does meta-prompting methodology play in guiding agent output?
- How do different AI actors and language flavors affect outcomes?
- Can a TDD-first workflow translate reliably to AI-driven cloud infrastructure development?

This specific repository represents the **Python (CDK)** language flavor, driven entirely by **Kiro by Amazon** as the AI actor. The target system is an event-driven serverless audio processing pipeline on AWS -- a non-trivial, multi-service architecture suitable for evaluating agent capabilities across planning, implementation, testing, and documentation.

### Success Criteria

- Fully synthesizable CDK stack across multiple environments (dev, stage, prod)
- Comprehensive test suite validating all infrastructure resources and behaviors
- Zero manual console changes -- everything defined as code
- Clean issue-driven development trail from bootstrap through completion
- Documentation sufficient for reproduction and evaluation

---

## Methodology

The experiment uses three interlocking methodologies:

### Test-Driven Development (TDD)

Every infrastructure component and Lambda behavior was implemented test-first:

1. Write failing tests using `aws_cdk.assertions` or `unittest.mock`
2. Implement minimal CDK resources or Lambda logic to make tests pass
3. Refactor while maintaining a passing test suite
4. Verify CloudFormation synthesis for all environments
5. Repeat for the next component

This approach caught configuration errors early (missing IAM grants, incorrect state machine routing) and enabled safe refactoring as the architecture evolved.

### Issue-Driven Development

Work was organized into 14 sequential GitHub issues, each with a focused scope and a corresponding pull request. Issues progressed from bootstrap through architecture, core infrastructure, orchestration, data layer, notifications, Lambda integration, wiring, testing, error handling, audio processing, validation, and documentation. Each issue included:

- Clear acceptance criteria
- TDD expectations (tests written before implementation)
- A pull request linking back to the issue

### Architecture-as-Code

All architecture decisions were captured in code and documentation simultaneously. The CDK stack is the single source of truth for infrastructure, while `ARCHITECTURE.md` provides human-readable diagrams and rationale. No out-of-band changes were made through the AWS console or CLI.

---

## Actors & Setup

### AI Actor

| Property | Value |
|----------|-------|
| **Name** | Kiro by Amazon |
| **Role** | Sole implementer of all code, tests, and documentation |
| **Interaction model** | Issue-driven prompts with meta-prompting patterns |
| **Autonomy level** | Full implementation within issue scope; human-guided issue sequencing |

### Language Flavor

| Property | Value |
|----------|-------|
| **Language** | Python 3.11 |
| **IaC Framework** | AWS CDK (Python bindings) |
| **Test Framework** | pytest with aws_cdk.assertions |
| **Runtime** | AWS Lambda (Python 3.11) |

### Experiment Matrix

This repository occupies one cell in the 5x3 experiment grid:

| | AI Actor 1 | AI Actor 2 | AI Actor 3 |
|---|---|---|---|
| **Language A** | ... | ... | ... |
| **Language B** | ... | ... | ... |
| **Python (CDK)** | ... | **This repo (Kiro)** | ... |
| **Language D** | ... | ... | ... |
| **Language E** | ... | ... | ... |

Each cell produces an independent implementation of the same target system, enabling comparison of outputs across AI actors and language flavors.

---

## Prompting Patterns & Meta-Prompts

The experiment relies on structured meta-prompting to guide the AI agent. Rather than freeform instructions, each issue uses patterns documented in [META-PROMPTS.md](./META-PROMPTS.md):

### Key Patterns Used

- **Bootstrap Pattern** -- Establishes project structure, tooling, and TDD conventions before any infrastructure work
- **Architecture-First Pattern** -- Produces system design documents with Mermaid diagrams before writing CDK code
- **TDD Scaffold Pattern** -- Provides test expectations in the issue body, ensuring the agent writes tests first
- **Incremental Wiring Pattern** -- Builds integrations one service at a time, validating each connection before adding the next
- **Documentation-as-Deliverable Pattern** -- Treats documentation as a first-class output, not an afterthought

### Meta-Prompt Structure

Each issue follows a consistent template:

1. **Context** -- What exists and what the issue builds upon
2. **Objectives** -- Specific deliverables with measurable criteria
3. **Constraints** -- TDD requirements, naming conventions, environment rules
4. **Acceptance criteria** -- Checklist that defines "done"
5. **References** -- Links to relevant architecture sections or prior PRs

This structured approach reduces ambiguity and increases the likelihood of correct first-pass implementation. See [META-PROMPTS.md](./META-PROMPTS.md) for the full catalog of patterns and templates.

---

## Issue History Summary

All implementation was performed through the following 14 issues, executed sequentially:

| # | Issue | PR | Description |
|---|-------|-----|-------------|
| 1 | #1: Bootstrap: Python CDK + Strict TDD + Agent Configuration | PR #2 | Project scaffolding, CDK app structure, pytest setup, agent guidelines |
| 2 | #3: Initial Architecture Design with Mermaid | PR #4 | System architecture document with service diagrams and data flow |
| 3 | #5: Core S3 Buckets + EventBridge Rule | PR #6 | Input/output S3 buckets with encryption, versioning, and EventBridge integration |
| 4 | #7: Step Functions State Machine + Polly Integration | PR #8 | State machine definition with orchestration states and Polly placeholder |
| 5 | #9: DynamoDB Metadata Table + State Machine I/O | PR #10 | Metadata table with lifecycle tracking and state machine read/write integration |
| 6 | #11: SNS Notifications + Error Handling | PR #12 | KMS-encrypted SNS topics for success/failure notifications with dead-letter handling |
| 7 | #13: Lambda Function Skeleton + State Machine Integration | PR #14 | Lambda resource definition, IAM grants, and state machine invocation wiring |
| 8 | #15: Complete Pipeline Wiring, Input Validation & End-to-End Flow | PR #16 | Full integration of all services, input validation logic, end-to-end state transitions |
| 9 | #17: Pipeline Testing, Refinement & Deployment Preparation | PR #18 | CDK Pipeline (self-mutating), CI workflow, multi-environment synthesis validation |
| 10 | #19: Advanced Error Handling, Retries & Observability | PR #20 | Retry policies, CloudWatch alarms, X-Ray tracing, structured error responses |
| 11 | #21: Full Audio Processing Implementation & Output Handling | PR #22 | Lambda audio passthrough, Polly TTS, S3 output writes, DynamoDB status updates |
| 12 | #23: End-to-End Validation, Documentation Polish & Project Completion | PR #24 | Integration tests, documentation updates, final validation across all environments |
| 13 | #25: Documentation: Review & Enrich README + Meta-Prompting Patterns | PR #26 | README overhaul, META-PROMPTS.md creation, documentation cross-linking |
| 14 | #27: Documentation: Capture Experimental Design & Meta-Prompting Process | -- | This document (EXPERIMENT.md) capturing the full experiment design |

### Development Timeline

```
Bootstrap --> Architecture --> Core Infrastructure --> Orchestration --> Data Layer
    --> Notifications --> Lambda --> Wiring --> Testing/Deployment
    --> Error Handling --> Audio Processing --> E2E Validation
    --> Documentation Enrichment --> Experiment Design (this document)
```

The progression follows a deliberate "outside-in" strategy: establish structure, design architecture, build infrastructure bottom-up, wire services together, then harden with error handling and observability. Documentation was treated as a capstone activity to ensure accuracy.

---

## Key Decisions & Trade-offs

These decisions shaped the implementation and reflect trade-offs evaluated during development:

| Decision | Rationale | Trade-off |
|----------|-----------|-----------|
| Event-driven architecture | Decouples upload from processing; enables independent scaling | Adds complexity vs. synchronous processing; requires careful error propagation |
| Step Functions for orchestration | Visual workflow, built-in retry/error handling, state management without custom code | Vendor lock-in; state machine JSON is verbose and harder to test than application code |
| DynamoDB for metadata | Sub-millisecond latency, no connection management, flexible schema, on-demand billing | No relational queries; denormalized data; eventual consistency by default |
| KMS-encrypted SNS | Notification payloads encrypted at rest; supports multiple subscriber types | Additional cost; KMS key management overhead |
| Multi-environment via CDK context | Single codebase for dev/stage/prod with environment-specific configs | Context values can be error-prone; no type-checking on context parameters |
| Lambda dual-mode processing | Single Lambda handles both audio passthrough and Polly TTS | Increases Lambda complexity; single responsibility principle tension |
| TDD-first development | Catches errors early; enables safe refactoring; documents expected behavior | Slower initial velocity; tests for CDK assertions can be brittle to refactoring |
| EventBridge over S3 notifications | Content-based filtering, replay capability, cleaner Step Functions integration | More indirection; harder to debug than direct S3 event triggers |
| CDK Pipeline (self-mutating) | Pipeline updates itself on push; eliminates manual deployment steps | Complex bootstrap; harder to debug pipeline failures |
| X-Ray tracing | End-to-end visibility across Lambda and state machine executions | Performance overhead (minimal); additional cost |

---

## Preliminary Observations

### Strengths

- **TDD translated well to IaC**: The `aws_cdk.assertions` library enabled meaningful test-first development for CloudFormation resources. Tests caught misconfiguration early and provided confidence during refactoring.
- **Issue-driven structure provided clear guardrails**: Each issue had a bounded scope, preventing scope creep and enabling focused implementation. The sequential progression built naturally on prior work.
- **Meta-prompting reduced ambiguity**: Structured prompts with explicit acceptance criteria minimized back-and-forth and reduced instances of incorrect or incomplete implementation.
- **298 tests provide comprehensive coverage**: The test suite covers infrastructure resources, Lambda behavior, error scenarios, multi-environment configurations, and state machine logic.
- **Zero manual console changes**: The entire system was built exclusively through CDK code, validating the IaC-only workflow.
- **All environments synthesize valid CloudFormation**: Dev, stage, and prod configurations produce correct templates with appropriate environment-specific settings.

### Challenges

- **State machine definition testing**: The Step Functions definition in CloudFormation is stored as `Fn::Join` arrays with placeholder references. Tests required custom parsing logic to join array elements and replace CFN references, adding test complexity.
- **NODE_OPTIONS environment quirk**: The development environment requires `NODE_OPTIONS=''` before any Node.js/CDK command due to a proxy-bootstrap.js injection. This non-obvious requirement could block new contributors or CI setups.
- **boto3 dependency management**: boto3 is available in the Lambda runtime but not in `requirements.txt` (intentionally, to keep deployment packages small). This requires separate installation for local testing.
- **Polly integration complexity**: Direct Polly invocation from Lambda was chosen over the Step Functions `CallAwsService` integration for testability, leaving the state machine Polly task as a placeholder for future workflows.

### Lessons Learned

- **Architecture documents pay dividends**: Having `ARCHITECTURE.md` established early provided a shared reference for all subsequent issues. The AI agent could reference it for consistency.
- **Incremental wiring beats big-bang integration**: Building service connections one at a time (issues #5 through #15) avoided the debugging complexity of connecting everything at once.
- **Documentation-as-deliverable works**: Treating docs as explicit issue deliverables (issues #25, #27) resulted in higher-quality documentation than post-hoc documentation efforts.
- **DynamoDB dual-write pattern adds resilience**: Having the Lambda write FAILED status directly (rather than relying solely on state machine error handling) ensures failure metadata is captured even when the orchestrator encounters unexpected issues.
- **Multi-environment validation catches subtle bugs**: Synthesizing all three environments in CI caught configuration differences that would have been missed with single-environment testing.

---

## References

- [ARCHITECTURE.md](./ARCHITECTURE.md) -- Full system design with Mermaid diagrams
- [META-PROMPTS.md](./META-PROMPTS.md) -- CDK-focused meta-prompting patterns and templates
- [AGENT_GUIDELINES.md](./AGENT_GUIDELINES.md) -- Development rules, conventions, and troubleshooting
- [SUMMARY.md](./SUMMARY.md) -- Project summary, key decisions, and experiment notes
