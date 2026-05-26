# ExpertView — Project Introduction

## Why this project exists

ExpertView is built primarily as a **CV/portfolio artifact** that demonstrates production-shaped multi-agent engineering on industry-standard tooling — the kind of project an AI-platform reviewer at a company like Anthropic, OpenAI, or a frontier AI lab can read end-to-end and recognize as competent rather than vibe-coded. Secondarily, it is the prepared entry for the shapeX 1-day hackathon: arrived at the event already polished, ready to either ship intact (if the brief aligns with the RCA problem) or be lifted apart into a divergent application (if the brief diverges materially). Either way the hackathon day is for adaptation, not first-time construction.

What this is *not*: a generic multi-agent framework, a production system, a reusable library. It is a single concrete application — Root Cause Analysis for industrial manufacturing incidents — whose modular boundaries exist as a *safety net* and as evidence of clean engineering judgment, not as a polished public API.

## 1. Problem Statement

When an operational incident occurs — a manufacturing process fails, a system degrades, a product goes out-of-spec, a service disruption happens — Root Cause Analysis (RCA) is expensive, slow, and structurally broken. The core problem is not lack of data: organizations have more data than ever. The problem is that the data lives across completely different domains (mechanical, process, supply chain, environmental, human factors) and no single expert or team can investigate all domains simultaneously.

Current state: investigation is sequential. One team checks the machine, then passes findings to the process team, which passes to supply chain. Each handoff introduces delay and information loss. Mean time to root cause spans days to weeks. Corrective actions are delayed. The same root causes recur because the full picture was never assembled.

The structural insight: RCA requires parallel hypothesis pursuit across heterogeneous knowledge domains, with convergence to a weighted causal explanation. This is not a workflow that can be made faster — it is a problem that requires a different shape.

## 2. Why This Genuinely Requires Multi-Agent Architecture

This is not a pipeline with an orchestrator label on top. The multi-agent requirement is structural, not stylistic:

**Different knowledge bases, irreconcilable in a single context.** A mechanical investigator needs hydraulic manuals, maintenance logs, torque specs, and FMEA documents. A supply chain investigator needs vendor QC certificates, batch traceability, and delivery manifests. A human factors investigator needs shift logs, training records, and operator SOPs. No single agent can hold all of this with effective retrieval — domain-specific RAG stores are architecturally necessary.

**Parallel hypotheses are correct by design.** You do not know ex-ante which domain contains the root cause. Sequential investigation is structurally wrong: if the root cause is in supply chain but you investigate mechanical first, you lose days before arriving. All hypotheses must run simultaneously.

**Sub-investigation spawning is dynamic and unpredictable.** A mechanical investigator may discover an anomaly that requires a sub-investigation into the specific component's supplier history. This spawns a new agent dynamically — the depth of the investigation tree is unknown at the start.

**Evidence convergence requires inter-agent communication.** The synthesis is not a simple aggregation. Investigators must share partial findings. If the environmental investigator finds a temperature spike and the mechanical investigator finds bearing failure, the synthesizer must recognize the causal link. This requires agents to read each other's outputs and adjust confidence scores.

**Pattern**: Parallel Hypotheses + Recursive Sub-Investigation + Evidence-Weighted Convergence.

## 3. What this demonstrates for hiring review

The technical shape above maps cleanly onto signals that AI-platform engineering reviewers look for:

- **LangGraph used because the shape demands it, not as a buzzword.** The `Send` API for parallel branch fan-out, conditional edges for dynamic sub-investigation spawning, and the typed shared-state object for cross-agent evidence sharing each map 1:1 onto the structural pattern above. The orchestration choice is justifiable in interview detail, not just badge-listed.
- **LangSmith tracing on every node and LLM call.** Observability is wired in from day one, not retrofitted; trace replay is the demo-day failure path as well as the build-time debugging surface.
- **Model routing across a single OpenRouter gateway.** Free open-weight models (Owl Alpha for the 5 parallel investigators, DeepSeek V4 Flash for build-phase synthesis) carry iteration cost; a paid frontier model (e.g. Anthropic Opus 4.7) is selectable via a single env var at demo time. The same factory module handles both, demonstrating production-shaped model-selection discipline rather than per-provider SDK sprawl.
- **Local embeddings (`BAAI/bge-small-en-v1.5`) by deliberate choice.** Removes hosted-embedding network dependency and quota concerns at <1k-doc corpora scale. Demonstrates the kind of "use the right tool at the right cost tier" judgment that distinguishes engineering from cargo-culting hosted services.
- **Strict module boundaries with `Protocol`-based contracts.** `KnowledgeStore`, `Investigator`, `Synthesizer` are typed protocols; `agents/llms.py` is the sole construction site for provider clients; cross-agent data flows through pydantic v2 models. The codebase reads as a maintainable system, not a notebook glued together.
- **Decision log + open-questions discipline.** Every architecturally-significant choice is recorded in `ProjectDocs/decisions.md` with reasons, alternatives, and reversibility. The artifact a reviewer can audit at-a-glance is the decision trail, not just the diff.

## 4. Hackathon angle (secondary)

The shapeX 1-day event is a real milestone the build also targets, with two outcomes designed in from the start:

- **Path A — Brief aligns with RCA**: ExpertView ships intact with minor scenario tuning (swap the rehearsed incident, adjust investigator prompts to the brief's vocabulary, rehearse twice).
- **Path B — Brief diverges materially**: the modular pieces (`rag/`, `orchestration/`, `evidence/`, `agents/base.py`, `agents/llms.py`, `prompts/`) lift into a new project; the LangGraph + state schema is the unit of reuse.

The 1-day pressure of the event is exactly why the build happens in advance: arriving with a polished system is worth more than 8 hours of vibe-coded construction under deadline, on both axes (winning the event *and* protecting the artifact's value as a portfolio piece).
