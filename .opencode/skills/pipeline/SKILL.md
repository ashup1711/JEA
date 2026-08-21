---
name: pipeline
description: Multi-agent pipeline orchestration using RAG and AST context for implementing software requirements
---

## Overview
Sequential multi-agent pipeline that: indexes codebase via vector DB,
uses RAG + AST for rich context, writes targeted prompts per expert,
executes experts in isolated sessions, verifies with QA (LSP + tests),
and loops on failures.

## Agents
- orchestrator (primary): Coordinates full pipeline
- explore-research (subagent): Read-only research with semantic search + AST
- prompt-engineer (subagent): Generates expert and QA prompts
- expert-backend (subagent): Python backend changes
- expert-frontend (subagent): Frontend changes
- expert-infra (subagent): Infrastructure/DevOps changes
- qa (subagent): Verification with LSP + tests

## MCP Tools
- `semantic-search_*`: Semantic search over codebase (TF-IDF based)
- `jcodemunch_*`: AST symbols, source, importers, blast radius

## Custom Tools
- `pipeline-state_createRequestId`: Generate request ID
- `pipeline-state_logEntry`: Persist prompt/state per request
- `pipeline-state_finalizeRequest`: Complete and summarize

## Flow
1. Create Request ID -> research -> Research Brief
2. Prompt Engineer -> Expert Prompts (one per domain, only if needed)
3. Execute Experts sequentially -> Implementation Summaries
4. Prompt Engineer -> QA Prompt
5. QA loop (max 3 retries): on FAIL, generate fix prompts, re-dispatch
6. Finalize with status and summary

## QA Retry Rules
- Only re-dispatch experts that produced failing code
- Include specific error messages in fix prompts
- Max 3 total QA attempts before marking FAILED
