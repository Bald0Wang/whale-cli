---
name: datawhale-learning-journey
description: Guide a Datawhale learner from profile to roadmap, review, project practice, and a local portfolio.
---

Use this skill for sustained learning requests rather than a one-off resource recommendation.

1. Ask only for missing profile fields: current level, target, weekly hours.
2. Use `Agent(datawhale_learning)` when a Datawhale project recommendation needs local knowledge-base evidence.
3. Add concepts and explicit prerequisite links before previewing a roadmap. Show `LearningRoadmap(action: "preview")` first, ask the learner to confirm, then use `generate` only after an explicit confirmation.
4. When asked for a review table or recent-conversation review, call `LearningReview(action: "sync")` then `LearningReview(action: "schedule")`. Use `LearningReview(action: "feedback")` to write a local Markdown checklist. Use `LearningReview(action: "rate")` only after the learner provides a 0-5 recall rating; do not invent progress from chat text alone.
5. When a learner says a planned task is done, first call `LearningRoadmap(action: "status")`, complete that existing item, then regenerate only if a new route is actually needed.
6. Plan a practice project before cloning it. Cloning needs user approval.
7. Add evidence after a real exercise, project change, reflection, or proposed community supplement.

Keep the language concrete. Explain a term the first time it appears and always expose the learner's next small action.
