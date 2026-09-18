# Model Context Protocol 2026-07-28 — distilled reference

Status: SOURCE_REFERENCE_ONLY
Acquired: 2026-09-15
Official source: https://blog.modelcontextprotocol.io/posts/2026-07-28/

Relevant capabilities observed in the current specification release:
- stateless protocol core;
- explicit request/response contracts;
- header-based routing;
- cacheable list results;
- authorization hardening;
- formal extension model;
- maintained Tier 1 SDKs.

SMART-MEGA adoption decision:
- do not embed a new MCP server inside the predictive core;
- apply the contract, authorization and provenance principles to external-tool boundaries;
- keep model-state mutation behind native SMART gates;
- fail closed when a tool result lacks target, provenance, hash or authorization context.

Reason: MCP is most valuable here as a boundary discipline for tools/connectors, not as a replacement for the internal statistical engine.
