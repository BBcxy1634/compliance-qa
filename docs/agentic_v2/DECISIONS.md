# Agentic Compliance Copilot v2 Decisions

## ADR-001: Upgrade the Existing Project

Decision:

Upgrade the current v1 repository instead of creating a separate similar RAG
project.

Reason:

The existing project already has real data, retrieval, evaluation, citation,
refusal, and release work. A second lookalike project would dilute the narrative.

## ADR-002: Controlled Graph, Not Free-Form Multi-Agent

Decision:

Use LangGraph as an explicit state machine with bounded transitions.

Reason:

The target role is application engineering. Reliability, retries, route
decisions, and failure recovery are more important than demonstrating multiple
agents talking to each other.

## ADR-003: Preserve B1 Fast and B3 Roles

Decision:

B1 Fast remains the default. B3 remains a quality mode for multi-hop or
high-risk requests.

Reason:

V1 measurements show B1 Fast has the best practical quality-latency balance.
V2 must not silently regress the released behavior.

## ADR-004: Add Infrastructure Incrementally

Decision:

Keep Chroma for initial V2 phases. Do not migrate to Qdrant or add PostgreSQL
and Redis until a phase has a concrete requirement.

Reason:

The current corpus has 271 semantic chunks. A database migration alone does not
prove LLM application engineering and would add avoidable risk.

## ADR-005: FastAPI and SSE

Decision:

Use FastAPI for the application interface and SSE for streaming.

Reason:

These are common, understandable choices for LLM application internships and
allow clear testing of request handling, error behavior, and incremental token
delivery.

## ADR-006: Tools Start as Typed Python Functions

Decision:

Implement tools behind a small typed interface first. Add MCP adapters only for
selected tools when the graph is stable.

Reason:

MCP is useful as a protocol demonstration, but making every tool an MCP server
too early increases setup and debugging cost.

## ADR-007: Measure Application Behavior

Decision:

Keep the original answer metrics and add routing, tool, evidence, latency, and
cost metrics.

Reason:

Answer-only evaluation cannot show whether a controlled agent selected the
right path, used the right tool, or failed safely.

## ADR-008: No Production Overengineering

Decision:

Do not add Kubernetes, microservices, SSO, or long-term memory in this version.

Reason:

The project should remain runnable and explainable by one person. Reliability in
the actual path is more valuable than infrastructure breadth.

## ADR-009: No Secrets in Context or Traces

Decision:

Never place API keys, `.env` content, or private user data in project state,
prompts, logs, evaluation data, or trace payloads.

Reason:

V2 adds more model and tool integrations, increasing accidental exposure risk.

