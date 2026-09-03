# Developer AI Contract

Status: foundational

## Goal
Sol/ChatGPT, Codex, or another developer agent should be able to work on Fireworks without becoming a unique hidden dependency.

## Required behavior
Before implementation, the agent must inspect the repository-owned instructions and relevant documentation.

The agent must:
- preserve Artifactdog's authorship;
- surface consequential ambiguity;
- follow accepted decision records;
- keep modules/interfaces documented;
- add tests for new behavior and regressions where practical;
- avoid coupling the project to the agent/model itself;
- record durable decisions in the repository rather than relying only on conversation memory.

## Codex
Codex can automatically consume repository instruction files such as `AGENTS.md` according to its supported instruction mechanism.

## Other developer AIs / ChatGPT surfaces
If instructions are not automatically injected, the developer workflow must explicitly load `AGENTS.md` and referenced project documents before meaningful Fireworks changes.

This difference in harness behavior must not change project semantics.
