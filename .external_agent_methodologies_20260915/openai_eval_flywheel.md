# OpenAI evaluation flywheel — distilled reference

Status: SOURCE_REFERENCE_ONLY
Acquired: 2026-09-15
Official sources:
- https://github.com/openai/openai-cookbook
- https://github.com/openai/evals

Relevant capabilities observed in official material:
- eval-driven iteration instead of intuition-driven changes;
- smoke tests for tool/function-call compatibility;
- task-specific evals for system correctness;
- trace-level analysis for agentic systems;
- continuous measure -> diagnose -> improve -> re-evaluate loop.

SMART-MEGA adoption decision:
- formalize supervisory agents that detect stale proofs, capability gaps and unmeasured acquisitions;
- keep every architecture change subordinate to regression and current-code certification;
- require explicit evidence before promoting any new framework, skill or agent into runtime authority;
- preserve negative findings so rejected acquisitions are not repeatedly reintroduced without new evidence.

Reason: this directly strengthens SMART-MEGA's existing falsification/non-regression doctrine without introducing an external runtime dependency.
