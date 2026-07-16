---
name: datawhale-learning
description: Plan a Datawhale learning route from the local project knowledge base.
---

# Datawhale Learning Planning

Use the `Agent` tool with `agent_type: datawhale_learning` when a user asks which
Datawhale projects to study, how to sequence them, or how to choose practice
milestones. Include the learner's current background, target direction, weekly
time budget, and preferred outcome. The subagent grounds recommendations in the
local `datawhale_bm25_documents.jsonl` corpus; do not replace it with guessed
project names.
