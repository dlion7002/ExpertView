# ExpertView — Decision Log

> ADR-lite. One entry per locked decision. **Format**: `## YYYY-MM-DD — Title` then **Decision**, **Why**, **Alternatives considered**, **Reversibility**. Append-only — never edit prior entries, supersede them with a new entry instead.

---

## 2026-05-20 — Build before the hackathon, not during

**Decision**: ExpertView is constructed across multiple sessions *before* the shapeX hackathon event. The event day is reserved for adaptation and demo polish, not first-time construction.

**Why**: The user's goal is to win solo. Arriving with a polished, demoable, modular system gives two advantages: (a) if the brief aligns, ExpertView slots in with minor scenario tuning; (b) if the brief diverges, the modular pieces can be lifted into a new project. Building under 1-day pressure would force vibe-coded compromises and erase both advantages.

**Alternatives considered**: Build during the hackathon — rejected for the reasons above.

**Reversibility**: Hard to reverse — the schedule is set by the event date. Cheap to pre-build.

---

## 2026-05-20 — Industrial manufacturing as the base RCA domain

**Decision**: The pre-hackathon build targets industrial manufacturing RCA, with five investigator domains: mechanical, process, supply chain, environmental, human factors. Mock corpora and the rehearsed demo scenario will be drawn from this space.

**Why**: This is the domain framed in [project_introduction.md](project_introduction.md). The user confirmed it via clarifying Q&A. It is concrete enough to produce realistic mock corpora, broad enough to demonstrate true cross-domain investigation, and demo-legible to judges from any technical background.

**Alternatives considered**: Broader operational incidents (rejected — too diffuse for crisp demo storytelling); a single narrow scenario (rejected — would not demonstrate the multi-domain shape).

**Reversibility**: Easy. Domain investigators are pluggable; mock corpora live in `data/domains/` and can be swapped wholesale.

---

## 2026-05-20 — Clean modular code, not a generic framework

**Decision**: We are *not* building a reusable multi-agent orchestration framework. We are building an RCA system whose modules happen to be lift-able. Module boundaries are preserved as a *safety net* (Path B at the hackathon), not as a public API to be polished.

**Why**: Generic framework abstractions add time cost up front and tend to be wrong (premature abstraction). The user explicitly chose "Just clean modular code — well-separated modules so I can lift pieces" over building a framework. This is also consistent with the global "no premature abstraction" rule in [CLAUDE.md](../CLAUDE.md).

**Alternatives considered**: Generic multi-agent orchestration framework (rejected — too much work, likely wrong abstraction); domain-pluggable RCA framework with config-driven swap (rejected — same risk, smaller payoff than clean modules).

**Reversibility**: Easy. If we ever want to extract a framework, the modules are already separable; we just add a public package on top.

---

## 2026-05-20 — Python + uv as the only backend stack

**Decision**: Python 3.11+ managed by uv (lockfile + virtualenv). No other languages in the backend.

**Why**: User confirmed Python + uv via clarifying Q&A. The Anthropic SDK has first-class Python support, async fan-out is straightforward, and the ML / vector / embedding ecosystem is most mature in Python.

**Alternatives considered**: TypeScript / Node (rejected — async story is fine but the embedding ecosystem is weaker); polyglot stack (rejected — adds operational complexity for no demo gain).

**Reversibility**: Hard, but no reason to reverse.

---

## 2026-05-25 — Reverse "no LangChain/LangGraph" exclusion; adopt LangGraph + LangSmith

**Decision**: Adopt LangGraph as the agent orchestration substrate and LangSmith as the tracing/observability layer. The EvidenceBus described in earlier drafts of [architecture.md](architecture.md) is replaced by the LangGraph shared-state object. This entry **supersedes** the "LangChain, CrewAI, LangGraph — for transparency and demo storytelling we want raw SDK calls" exclusion line that originally lived in [architecture.md §7](architecture.md).

**Why**: ExpertView is now framed as a CV/portfolio asset for ReshapeX and other AI-company applications in addition to a hackathon entry. Industry-standard agent frameworks are load-bearing for hiring-signal legibility, not optional sugar. Beyond the resume axis, LangGraph is a genuine shape-fit: the `Send` API for parallel branch fan-out, conditional edges for dynamic sub-investigation spawning, and the typed shared-state object for cross-agent evidence sharing each map 1:1 onto the structural pattern in [project_introduction.md](project_introduction.md). LangSmith provides free trace capture that solves both observability during the build and the venue-night replay fallback at zero infra cost.

**Alternatives considered**:
- Keep raw Anthropic SDK with hand-rolled `asyncio.gather` fan-out and a custom EvidenceBus (rejected — leaves CV signal on the table, and we'd be re-implementing LangGraph's parallel-branch and state-merge primitives badly).
- LangSmith tracing only, no LangGraph (rejected — gives the keyword on the resume without the architecture story; an interviewer who probes will see no graph behind the tag).
- CrewAI / AutoGen (rejected — opinionated agent-role abstractions that don't match the "investigator + synthesizer" shape; weaker industry signal than LangGraph in 2026).

**Reversibility**: Medium. Module boundaries are preserved (the [vision.md §6](vision.md) Path B lift story still holds — the LangGraph + state schema lifts as a unit, which is arguably *stronger* industry signal than lifting hand-rolled async modules). Removing LangGraph would require reverting the orchestration package and re-introducing a hand-rolled EvidenceBus; the rest of the codebase is unaffected.

---

## 2026-05-25 — Multi-provider model split via NVIDIA NIM + Anthropic

**Decision**: The model stack is split across providers by task:

- **Investigators (5 parallel)** → Llama 3.3 70B Instruct via NVIDIA NIM (`langchain_nvidia_ai_endpoints.ChatNVIDIA`).
- **Synthesizer (build / iteration)** → DeepSeek-R1 via NVIDIA NIM. Strong open-weight thinking model, zero spend.
- **Synthesizer (final rehearsal + demo)** → Anthropic Opus 4.7 via `langchain_anthropic.ChatAnthropic`. Reserved for the moment judges are watching.
- **Embeddings** → NVIDIA `nv-embed-v2` (top-tier MTEB; comparable or better than `sentence-transformers/all-MiniLM-L6-v2` at the same zero marginal cost).
- **Reranker** → NVIDIA `nv-rerankqa-mistral-4b-v3` (or equivalent NV-Rerank endpoint).

The synthesizer model is selectable via env var (e.g. `EXPERTVIEW_SYNTH_MODEL=deepseek-r1` for build, `=opus-4-7` for demo). The factory lives in `src/expertview/agents/llms.py`.

**Why**: The user has a free NVIDIA dev/test API key, and the free-tier NIM catalog covers every step of the pipeline at zero marginal cost — except the moment we want best-in-class synthesizer reasoning quality in front of judges. Llama 3.3 70B is fast and parallel-friendly for the 5-way investigator fan-out (exactly the workload where free hosted inference shines). DeepSeek-R1 is the strongest free thinking model currently hosted on NIM and is more than sufficient for prompt-and-pipeline iteration. Opus 4.7 is the demo quality lever — bought only when it matters. NV-Embed-v2 sits at the top of the MTEB leaderboard; switching to it from local `all-MiniLM-L6-v2` is a genuine retrieval-quality upgrade, not a lateral move. The multi-provider story also strengthens the CV ("model routing across providers, free-tier optimization, quality-bar lever at demo time") more than a single-provider stack would.

**Alternatives considered**:
- Sonnet 4.6 as build-phase synthesizer default (rejected — still paid; the user explicitly requested no Anthropic spend during build).
- Nemotron-Ultra-340B (NVIDIA's own reasoning model) for build-phase synthesizer (viable; kept as the fallback if DeepSeek-R1 disappoints on causal-link reasoning in phase 5 testing).
- Full NVIDIA, no Anthropic at all (rejected — gives up the demo quality lever and weakens the Anthropic-skill demo angle for ReshapeX).
- Embeddings-only on NVIDIA, Anthropic everywhere else (rejected — wastes the free Llama 3.3 70B endpoint that is genuinely the right tool for parallel investigators).

**Reversibility**: Easy. Every model identifier is a string in `agents/llms.py` selectable via env var. Switching back to Anthropic-only or to a different NIM model is a one-line config change.

---

## 2026-05-25 — Demo posture: cloud-only with hotspot mitigation; no offline fallback path

**Decision**: The demo runs against live cloud APIs (NVIDIA NIM, Anthropic, LangSmith). The mitigation for venue-network failure is a personal cellular hotspot, not a dual offline code path. The earlier "ideally without network dependency" language in [vision.md §4](vision.md) success-criterion 4 is amended to "with hotspot-backed network as the failsafe." The LangSmith trace store doubles as a recorded-run fallback (replay a prior successful run from the trace if all networks are down).

**Why**: Building and maintaining a parallel offline path (local embeddings + local LLM via Ollama or similar) doubles the surface area for marginal demo-day safety gain. A modern hotspot is a more credible mitigation than a code path that has to be tested separately. LangSmith trace replay is the secondary fallback — if a prior trace exists for the rehearsed scenario, we can demo from it.

**Alternatives considered**:
- Dual cloud + offline code paths (rejected — engineering cost > marginal safety benefit).
- Cloud-only with no fallback at all (rejected — venue networks fail; a hotspot is cheap insurance).
- Keep offline-first stance (rejected — gives up NV-Embed-v2 + DeepSeek-R1, which are the entire point of the NVIDIA-key reframe).

**Reversibility**: Easy in principle (re-add a local embedding fallback path under the `KnowledgeStore` protocol); cost is build time.

---

## 2026-05-25 — Resolve [open_questions.md](open_questions.md) Q1: LangGraph + LangSmith

**Decision**: The "Agent orchestration library" question is resolved: LangGraph for orchestration (`StateGraph`, `Send`-API parallel branches, conditional-edge spawning), LangSmith for tracing. Supersedes the prior #1 ranking of "Anthropic SDK directly (async client)" in that question. The corresponding open question is removed from [open_questions.md](open_questions.md) per the documentation discipline in [workflow.md §6](workflow.md).

**Why**: See the 2026-05-25 LangGraph adoption decision above.

**Reversibility**: See same.

---

## 2026-05-25 — Resolve [open_questions.md](open_questions.md) Q2: NV-Embed-v2 + NV-Rerank

**Decision**: The "Embeddings provider" question is resolved: NVIDIA `nv-embed-v2` for embeddings and NVIDIA `nv-rerankqa-mistral-4b-v3` (or the current NIM reranker endpoint) for reranking, both via `langchain_nvidia_ai_endpoints`. Supersedes the prior #1 ranking of `sentence-transformers` in that question. The corresponding open question is removed from [open_questions.md](open_questions.md).

**Why**: See the 2026-05-25 multi-provider model split decision above.

**Reversibility**: See same — single config swap.

---

## 2026-05-25 — Resolve [open_questions.md](open_questions.md) Q1 (renumbered): Streamlit demo UI surface

**Decision**: The demo UI is **Streamlit**. Phase 6 builds a single-screen Streamlit app with three regions: incident input, live investigator-status panel + Mermaid topology diagram (rendered via `st.mermaid` from `compiled_graph.get_graph().draw_mermaid()`), and the final causal report with confidence bars + citations. A `--cli` mode using `rich` live tables is kept wired up as the Plan B if Streamlit refuses to cooperate on the venue laptop.

**Why**: Lowest time-to-demo for the exact shape we need (n columns + synthesized report + topology diagram tab). Python-native; `st.empty()` + `st.fragment` handles live updates cheaply; `st.mermaid` renders the LangGraph topology natively; widely familiar to judges. NiceGUI was the technically better fit (async-first, real WebSockets matching our LangGraph asyncio model 1:1), but Streamlit's familiarity wins on demo-day risk.

**Alternatives considered**: NiceGUI (viable — better technical fit, lost on demo-day risk), Gradio (acceptable — multi-panel live updates need custom blocks against its single-form idiom), CLI-only with `rich` (acceptable; kept as Plan B regardless), Textual TUI (acceptable but terminal projection at the venue is risky), custom HTML/SSE FastAPI dashboard (rejected — front-end project on top of an already-ambitious backend), Reflex/Pynecone (rejected — overkill).

**Reversibility**: Easy. UI lives in its own `src/expertview/ui/` package behind no other module; can be swapped without touching orchestration, agents, or rag. The CLI mode is kept regardless.

---

## 2026-05-25 — Resolve [open_questions.md](open_questions.md) Q2 (renumbered): CNC out-of-tolerance demo scenario

**Decision**: The rehearsed demo scenario is: **a CNC machine producing out-of-tolerance parts on shift 3, line 2, after maintenance on a hydraulic cylinder, with a recent batch of bearings from a new supplier**.

Mock corpora and investigator prompts are tuned around this scenario. Spawning trigger: the mechanical investigator finds a bearing anomaly → conditional edge routes to a supplier-history sub-investigator node under `supply_chain`. Domain coverage by design: mechanical (hydraulic + bearing), supply chain (new supplier batch), human factors (shift change / post-maintenance handover), environmental (lubricant temperature drift), process (synthesizer's job to connect the threads). The scenario file lives at `data/incidents/cnc_out_of_tolerance.yaml`.

**Why**: Cleanest mapping of the architecture onto a story judges can follow in 60 seconds. Hits all 5 domains naturally; has an obvious spawning trigger (bearing anomaly → supplier sub-investigation); legible to non-experts ("a machine is making bad parts"). The bottling-line foam-fill scenario was the close second on visceral legibility but lost on domain-coverage spread.

**Alternatives considered**: Bottling-line foam-fill defect (viable; legibility was even better but domain coverage thinner), pharmaceutical tablet weight variance (acceptable; USP/granulation jargon costs the lay audience), gas-turbine vibration exceedance (acceptable; narrower audience), battery-cell capacity drift (acceptable; topical but jargon-heavy), semiconductor wafer yield drop (rejected — best technical depth, worst demo legibility).

**Reversibility**: Easy. Scenario is one YAML file plus corpus-specific clue documents; a second scenario is required by phase 5 anyway (evidence-weighted convergence safety check), so the system is built to be scenario-pluggable.

---

## 2026-05-25 — Resolve [open_questions.md](open_questions.md) Q3 (renumbered): Vector store via LangChain `InMemoryVectorStore`

**Decision**: The `KnowledgeStore` protocol is implemented in v1 by wrapping **LangChain `InMemoryVectorStore`** (from `langchain-core`). One store per domain, embedded at process startup via `NVIDIAEmbeddings(model="nvidia/nv-embed-v2")`. No on-disk persistence yet.

**Why**: Zero infra; ships with `langchain-core`; <10 LOC to wrap behind the `KnowledgeStore` protocol; trivially debuggable; embedding once at process startup is fine at <1k docs/domain. Every "feature" of a heavier vector DB is overkill at this scale, and `InMemoryVectorStore` is the lowest-friction LangChain idiom.

**Alternatives considered**: `FAISS` via `langchain-community` (viable; file-backed persistence avoids re-embedding on startup — promote to #1 if rehearsal shows NIM embedding-quota strain), `Chroma` via `langchain-chroma` (acceptable; metadata filtering + collections-per-domain, worth it only at >5k docs or with rich metadata-filter needs).

**Reversibility**: Easy. The whole point of the `KnowledgeStore` protocol is swap-in cost = one file. FAISS is the pre-identified upgrade path if embedding-on-startup quota becomes a concern.

---

## 2026-05-25 — Resolve [open_questions.md](open_questions.md) Q4 (renumbered): Hybrid mock corpora — Claude drafts + hand curation

**Decision**: Mock corpora are generated by a **hybrid approach**: Claude drafts 5–10 docs per domain in a dev session (not at build runtime), then the user hand-curates for plausibility and to plant the specific clues the rehearsed CNC scenario's causal chain needs to retrieve. Outputs land in `data/domains/<domain>/*.md`.

**Why**: Only this approach satisfies both "enough corpus volume to feel real" and "specific clues in specific docs for the demo to work." Claude generates the volume in minutes; hand curation guarantees the demo's causal chain is supported by retrievable evidence. Fully hand-authored trades hours of work for control we already get from the curation step. Fully Claude-generated with no curation is a coin-flip on whether the planted clues land where the investigators retrieve them.

**Alternatives considered**: Fully hand-authored (viable; control is maximum, time cost is hours), fully Claude-generated with no curation (rejected — this is what kills the demo on the day).

**Reversibility**: Easy. Corpora are flat files in `data/domains/`; iterate freely.

---

## 2026-05-25 — Defer [open_questions.md](open_questions.md) Q5 (renumbered): Anthropic spend cap + NIM quota tracking

**Decision**: The Anthropic spend cap and NIM monthly quota tracking are **deferred** until there is a fully functional end-to-end demo. The decision is recorded here (rather than left in `open_questions.md`) so the deferral itself is auditable. Build-phase iteration runs entirely on the NVIDIA NIM free tier (Llama 3.3 70B for investigators, DeepSeek-R1 for the synthesizer, NV-Embed-v2 for embeddings, NV-Rerank for reranking), so iteration cost is $0 in Anthropic terms. Anthropic Opus 4.7 is wired through `agents/llms.py` for the eventual demo-path swap (`EXPERTVIEW_SYNTH_MODEL=opus-4-7`) but is not exercised during build. If, once the end-to-end demo runs cleanly on DeepSeek-R1, the Opus 4.7 polish appears materially worth the spend, the cap will be locked then.

**Why**: Per the user's instruction on 2026-05-25 — "ignore the Anthropic part, it will be implemented later once there is a fully functional demo if seems necessary." Naming a spend cap now is premature when the question is whether the lever is needed at all. The free-tier-first build path already makes "no Anthropic spend during build" enforceable via the env-var swap. NIM quota tracking can ride on LangSmith metadata once traces start landing — no separate tooling required pre-demo.

**Alternatives considered**: Lock a soft Anthropic cap now in the $20–$50 range (viable; deferred so a number is not invented before the question matters), commit to zero-Anthropic permanently with DeepSeek-R1 as the demo synthesizer (viable fallback; preserved until rehearsals show whether Opus 4.7 polish is worth the spend).

**Reversibility**: Easy — this is a budgeting decision, not a code commit. Revisit at the end of phase 5 or earlier if NIM quota becomes a concern. The synthesizer swap is one env-var change.

---

## (All phase-0 open questions resolved as of 2026-05-25)

All five questions previously tracked in [open_questions.md](open_questions.md) are now either locked (Q1–Q4) or formally deferred with revisit trigger (Q5). Phase 1 (Skeleton + contracts) is unblocked. New open questions arising during phase 1+ should be appended to [open_questions.md](open_questions.md) per [workflow.md §6](workflow.md).

---

## 2026-05-25 — Lightweight GitHub Flow for repository collaboration

**Decision**: ExpertView uses a lightweight GitHub Flow / trunk-based workflow. `main` is the stable demo-ready branch. Work happens in short-lived `feature/*`, `fix/*`, `docs/*`, and `chore/*` branches, then merges through pull requests with automated checks. Demo-ready states are marked with annotated tags such as `v0.1.0-demo`.

**Why**: This is a solo-built pre-hackathon and portfolio project. The repository needs enough process to show professional branch discipline, review checkpoints, quality gates, and release traceability, but not enough ceremony to look artificially enterprise-scale. A lightweight flow keeps the demo branch trustworthy and easy to explain to a company.

**Alternatives considered**: Full GitFlow with `develop`, `release/*`, and `hotfix/*` branches (rejected — useful for teams maintaining multiple production versions, unnecessary here); direct commits to `main` (rejected — weak review and traceability story); branch-per-phase without PRs (rejected — planning is visible, but integration discipline is not).

**Reversibility**: Easy. If ExpertView later becomes a multi-release product with more contributors, the project can introduce a heavier release strategy. Until then, the lightweight workflow is the honest fit.
