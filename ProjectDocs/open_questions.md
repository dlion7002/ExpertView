# ExpertView — Open Questions

> Active questions that need user input. Each question lists ranked options with verdict tags so you can answer with "go with #1" or "actually #N because ...". When a question is answered, **move the answer to [decisions.md](decisions.md) and delete the entry here.**
>
> **Verdict tags**: **Recommended** (the default if you say nothing) · **Viable** (would also work, here's the trade) · **Acceptable** (works but costs something material) · **Avoid** (listed for completeness so you can rule it out explicitly).

---

## Status as of 2026-05-25 (phase-0 question set)

**All phase-0 open questions are resolved or formally deferred.** See [decisions.md](decisions.md) entries dated 2026-05-25 for:

- **Q1 — Demo UI surface** → locked to Streamlit (with a `--cli` `rich` mode kept wired as Plan B).
- **Q2 — Demo incident scenario** → locked to the CNC out-of-tolerance scenario (shift 3, line 2, post-hydraulic-cylinder maintenance, new-supplier bearing batch). Mock corpora + investigator prompts tune around it.
- **Q3 — Vector store integration** → locked to LangChain `InMemoryVectorStore` wrapped behind `KnowledgeStore`. FAISS is the pre-identified upgrade path.
- **Q4 — Mock corpora generation strategy** → locked to hybrid (Claude drafts, user hand-curates for the planted causal-chain clues).
- **Q5 — LLM provider budget tracking** → resolved 2026-05-26. The NIM + Anthropic two-provider plan was superseded by the OpenRouter pivot (see [decisions.md 2026-05-26](decisions.md)); budget tracking now happens via the OpenRouter dashboard against the user's $5 credit, and there is no separate NIM or Anthropic billing relationship to track. The original deferral is no longer load-bearing.

The build ran to completion on these answers; phases 0-7 are all closed. New questions should be appended below per [workflow.md §6](workflow.md).

---

## Active questions

*(none — the phase 0-7 build closed without leaving any open.)*

---

## Skill candidates (not blocking)

If patterns repeat ≥3 times across sessions, promote to a custom Claude skill. None of these are blocking phase 1.

- `rca-investigator-prompt` — would generate investigator prompts with consistent structure (citations required, confidence ∈ [0,1], emit `Finding` JSON).
- `domain-rag-seed` — would scaffold a new knowledge domain (data folder + mock corpus generator + embedding setup + loader entry).
- `agent-trace-replay` — would replay a recorded LangSmith trace (or a vendored JSONL export) for debugging.
