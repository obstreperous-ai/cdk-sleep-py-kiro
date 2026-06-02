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
  app.py                  # CDK app entry point
  cdk.json                # CDK configuration and context
  cdk_base/               # Stack definitions
  tests/                  # Pytest tests with aws_cdk.assertions
  ARCHITECTURE.md         # System design (source of truth)
  AGENT_GUIDELINES.md     # This file
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

## What Not to Do

- Do not add resources that are not described in `ARCHITECTURE.md` without updating the architecture first
- Do not use inline policies when managed policies or resource-based policies are sufficient
- Do not skip tests for infrastructure changes
- Do not hardcode environment-specific values; use CDK context
- Do not create public S3 buckets or overly permissive IAM roles
