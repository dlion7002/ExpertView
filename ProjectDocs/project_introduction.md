General context: I have a hackaton for a company called shapeX that will do a 1 day and my objective is to win it alone so i will build the ExpertView project with two main objectives in mind:
    - To have a really strong base for the competition, so if the final competitions structure align i can use it as my project and do small final touches and modifications in the event. And also to learn and have strong fundamentals
    - To have clean architectur and desing so i can rehuse as much as possible for a new project if the final day instructions require me to build someting different.

Definition of the project Idea:


1. Problem Statement
When an operational incident occurs — a manufacturing process fails, a system degrades, a product goes out-of-spec, a service disruption happens — Root Cause Analysis (RCA) is expensive, slow, and structurally broken. The core problem is not lack of data: organizations have more data than ever. The problem is that the data lives across completely different domains (mechanical, process, supply chain, environmental, human factors) and no single expert or team can investigate all domains simultaneously.
Current state: investigation is sequential. One team checks the machine, then passes findings to the process team, which passes to supply chain. Each handoff introduces delay and information loss. Mean time to root cause spans days to weeks. Corrective actions are delayed. The same root causes recur because the full picture was never assembled.
The structural insight: RCA requires parallel hypothesis pursuit across heterogeneous knowledge domains, with convergence to a weighted causal explanation. This is not a workflow that can be made faster — it is a problem that requires a different shape.

2. Why This Genuinely Requires Multi-Agent Architecture
This is not a pipeline with an orchestrator label on top. The multi-agent requirement is structural, not stylistic:
Different knowledge bases, irreconcilable in a single context. A mechanical investigator needs hydraulic manuals, maintenance logs, torque specs, and FMEA documents. A supply chain investigator needs vendor QC certificates, batch traceability, and delivery manifests. A human factors investigator needs shift logs, training records, and operator SOPs. No single agent can hold all of this with effective retrieval — domain-specific RAG stores are architecturally necessary.
Parallel hypotheses are correct by design. You do not know ex-ante which domain contains the root cause. Sequential investigation is structurally wrong: if the root cause is in supply chain but you investigate mechanical first, you lose days before arriving. All hypotheses must run simultaneously.
Sub-investigation spawning is dynamic and unpredictable. A mechanical investigator may discover an anomaly that requires a sub-investigation into the specific component's supplier history. This spawns a new agent dynamically — the depth of the investigation tree is unknown at the start.
Evidence convergence requires inter-agent communication. The synthesis is not a simple aggregation. Investigators must share partial findings. If the environmental investigator finds a temperature spike and the mechanical investigator finds bearing failure, the synthesizer must recognize the causal link. This requires agents to read each other's outputs and adjust confidence scores.
Pattern: Parallel Hypotheses + Recursive Sub-Investigation + Evidence-Weighted Convergence.
