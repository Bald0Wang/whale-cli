"""Agent tool adapters for the independent learning-domain services."""
from __future__ import annotations

import json
from pathlib import Path

from ...learning import KnowledgeMap, LearnerProfileService, LearningPortfolio, ObsidianLearningWiki, ProjectCompanion, ReviewScheduler, RoadmapPlanner
from ...learning.store import LearningStore
from ..base import Tool, ok


def _result(payload: object) -> dict:
    return ok(json.dumps(payload, ensure_ascii=False, indent=2), [".whale_cli/learning/state.json"])


class _LearningTool(Tool):
    def __init__(self, workspace: str | Path | None = None) -> None:
        self.store = LearningStore(workspace or Path.cwd())
        self.profiles = LearnerProfileService(self.store)
        self.map = KnowledgeMap(self.store)
        self.roadmap = RoadmapPlanner(self.store, self.profiles)
        self.reviews = ReviewScheduler(self.store)
        self.projects = ProjectCompanion(self.store, workspace or Path.cwd())
        self.portfolio = LearningPortfolio(self.store)
        self.wiki = ObsidianLearningWiki(self.store, workspace or Path.cwd())


class LearnerProfileTool(_LearningTool):
    name = "LearnerProfile"
    description = "Read or update the learner's explicit background, goal, weekly time, and topics."
    schema = {"type": "function", "function": {"name": name, "description": description, "parameters": {"type": "object", "properties": {
        "action": {"type": "string", "enum": ["show", "update"]},
        "level": {"type": "string"}, "goal": {"type": "string"}, "weekly_hours": {"type": "number"},
        "topics": {"type": "array", "items": {"type": "string"}}, "learning_style": {"type": "string"},
    }, "required": ["action"]}}}

    def __call__(self, *, action: str, level: str = "", goal: str = "", weekly_hours: float = 0, topics: list[str] | None = None, learning_style: str = "") -> dict:
        if action == "show":
            return _result({"profile": self.profiles.get(), "missing_fields": self.profiles.missing_fields()})
        if action == "update":
            return _result(self.profiles.update(level=level, goal=goal, weekly_hours=weekly_hours, topics=topics, learning_style=learning_style))
        raise ValueError("action must be show or update")


class KnowledgeMapTool(_LearningTool):
    name = "KnowledgeMap"
    description = "Maintain a learner-owned knowledge map with concepts and inspectable two-way links."
    schema = {"type": "function", "function": {"name": name, "description": description, "parameters": {"type": "object", "properties": {
        "action": {"type": "string", "enum": ["add_node", "link", "show"]}, "title": {"type": "string"},
        "kind": {"type": "string", "enum": ["concept", "resource", "project", "note"]}, "mastery": {"type": "integer"},
        "note": {"type": "string"}, "source": {"type": "string"}, "target": {"type": "string"},
        "relation": {"type": "string", "enum": ["prerequisite", "related", "evidence_for"]}, "concept_id": {"type": "string"},
    }, "required": ["action"]}}}

    def __call__(self, *, action: str, title: str = "", kind: str = "concept", mastery: int = 0, note: str = "", source: str = "", target: str = "", relation: str = "prerequisite", concept_id: str = "") -> dict:
        if action == "add_node":
            return _result(self.map.add_node(title=title, kind=kind, mastery=mastery, note=note))
        if action == "link":
            return _result(self.map.link(source=source, target=target, relation=relation))
        if action == "show":
            return _result(self.map.node(concept_id) if concept_id else self.map.overview())
        raise ValueError("action must be add_node, link, or show")


class LearningRoadmapTool(_LearningTool):
    name = "LearningRoadmap"
    description = "Preview, save after user confirmation, or complete a small learning roadmap from profile and concept dependencies."
    schema = {"type": "function", "function": {"name": name, "description": description, "parameters": {"type": "object", "properties": {
        "action": {"type": "string", "enum": ["preview", "status", "generate", "complete"]}, "weeks": {"type": "integer"}, "roadmap_id": {"type": "string", "description": "Use an existing items[].id such as roadmap-agent-loop. A route_id is accepted only when exactly one item remains unfinished."},
    }, "required": ["action"]}}}

    def approval_action_for(self, args: dict) -> str | None:
        return "save learning roadmap" if args.get("action") == "generate" else None

    def __call__(self, *, action: str, weeks: int = 4, roadmap_id: str = "") -> dict:
        if action == "preview":
            return ok(json.dumps({"weeks": weeks, "items": self.roadmap.preview(weeks=weeks), "requires_confirmation": True}, ensure_ascii=False, indent=2))
        if action == "status":
            return ok(json.dumps(self.roadmap.current(), ensure_ascii=False, indent=2))
        if action == "generate":
            return _result(self.roadmap.generate(weeks=weeks))
        if action == "complete":
            return _result(self.roadmap.mark_done(roadmap_id))
        raise ValueError("action must be preview, status, generate, or complete")


class LearningReviewTool(_LearningTool):
    name = "LearningReview"
    description = "Scan local learning conversations into a review table, read local concept materials, write a Markdown review checklist, show due cards, or record a 0-5 recall rating."
    schema = {"type": "function", "function": {"name": name, "description": description, "parameters": {"type": "object", "properties": {
        "action": {"type": "string", "enum": ["due", "rate", "sync", "schedule", "feedback", "detail"]}, "concept_id": {"type": "string"}, "rating": {"type": "integer", "minimum": 0, "maximum": 5},
    }, "required": ["action"]}}}

    def __call__(self, *, action: str, concept_id: str = "", rating: int = 0) -> dict:
        if action == "due":
            return _result(self.reviews.due())
        if action == "rate":
            result = self.reviews.review(concept_id=concept_id, rating=rating)
            return ok(json.dumps(result, ensure_ascii=False, indent=2), [".whale_cli/learning/state.json", ".whale_cli/learning/review-schedule.json"])
        if action == "sync":
            result = self.reviews.sync_from_conversations(force=True)
            return ok(json.dumps(result, ensure_ascii=False, indent=2), [".whale_cli/learning/state.json", ".whale_cli/learning/review-schedule.json"])
        if action == "schedule":
            return _result(self.reviews.schedule())
        if action == "feedback":
            result = self.reviews.feedback()
            return ok(result["content"], [result["path"]])
        if action == "detail":
            return _result(self.reviews.detail(concept_id))
        raise ValueError("action must be due, rate, sync, schedule, feedback, or detail")


class LearningProjectPlanTool(_LearningTool):
    name = "LearningProjectPlan"
    description = "Create a learner-facing project practice plan with value, prerequisites, outcomes, and evidence; it does not clone the project."
    schema = {"type": "function", "function": {"name": name, "description": description, "parameters": {"type": "object", "properties": {
        "title": {"type": "string"}, "url": {"type": "string"}, "goal": {"type": "string"},
        "learning_value": {"type": "string", "description": "Why this project is worth doing for the learner's current goal."},
        "prerequisites": {"type": "array", "items": {"type": "string"}, "description": "Knowledge or setup the learner should check before starting."},
        "outcomes": {"type": "array", "items": {"type": "string"}, "description": "Observable abilities or deliverables expected after the practice."},
        "first_action": {"type": "string", "description": "One small, safe action the learner can take before cloning or running code."},
    }, "required": ["title", "url", "goal"]}}}

    def __call__(self, *, title: str, url: str, goal: str, learning_value: str = "", prerequisites: list[str] | None = None, outcomes: list[str] | None = None, first_action: str = "") -> dict:
        return _result(self.projects.plan(title=title, url=url, goal=goal, learning_value=learning_value, prerequisites=prerequisites, outcomes=outcomes, first_action=first_action))


class CloneLearningProjectTool(_LearningTool):
    name = "CloneLearningProject"
    description = "Clone an approved Datawhale practice project into a new workspace-local directory."
    approval_action = "clone learning project"
    schema = {"type": "function", "function": {"name": name, "description": description, "parameters": {"type": "object", "properties": {
        "url": {"type": "string"}, "directory": {"type": "string"},
    }, "required": ["url", "directory"]}}}

    def __call__(self, *, url: str, directory: str) -> dict:
        result = self.projects.clone(url=url, directory=directory)
        return ok(json.dumps(result, ensure_ascii=False, indent=2), [result["directory"]])


class LearningPortfolioTool(_LearningTool):
    name = "LearningPortfolio"
    description = "Record learner-owned evidence with related concepts, observable outcomes, artifacts, and next actions; render a local Markdown portfolio and reviewable contribution draft."
    schema = {"type": "function", "function": {"name": name, "description": description, "parameters": {"type": "object", "properties": {
        "action": {"type": "string", "enum": ["add_evidence", "report"]}, "title": {"type": "string"},
        "detail": {"type": "string"}, "kind": {"type": "string", "enum": ["note", "exercise", "project", "reflection", "contribution"]},
        "concepts": {"type": "array", "items": {"type": "string"}, "description": "KnowledgeMap topics or concepts supported by this evidence."},
        "outcome": {"type": "string", "description": "Observable new ability, changed understanding, or proposed community improvement."},
        "artifact": {"type": "string", "description": "A local path, command result, note, commit, or other learner-reviewable output."},
        "next_action": {"type": "string", "description": "The smallest useful next action after this evidence."},
    }, "required": ["action"]}}}

    def __call__(self, *, action: str, title: str = "", detail: str = "", kind: str = "note", concepts: list[str] | None = None, outcome: str = "", artifact: str = "", next_action: str = "") -> dict:
        if action == "add_evidence":
            return _result(self.portfolio.add_evidence(title=title, detail=detail, kind=kind, concepts=concepts, outcome=outcome, artifact=artifact, next_action=next_action))
        if action == "report":
            return ok(self.portfolio.report())
        raise ValueError("action must be add_evidence or report")


class LearningWikiStatusTool(_LearningTool):
    name = "LearningWikiStatus"
    description = "Read the local Obsidian learning Wiki status without changing files."
    schema = {"type": "function", "function": {"name": name, "description": description, "parameters": {"type": "object", "properties": {}}}}

    def __call__(self) -> dict:
        return ok(json.dumps(self.wiki.status(), ensure_ascii=False, indent=2))


class LearningWikiTool(_LearningTool):
    name = "LearningWiki"
    description = "Build a learner-reviewable LLM-Wiki outline, or initialize and sync its Obsidian-compatible Markdown export."
    approval_action = "write learning wiki"
    schema = {"type": "function", "function": {"name": name, "description": description, "parameters": {"type": "object", "properties": {
        "action": {"type": "string", "enum": ["init", "sync", "set_auto_capture", "outline", "show_outline"]}, "vault_dir": {"type": "string"}, "title": {"type": "string"},
        "enabled": {"type": "boolean", "description": "Enable or disable storing future completed conversation turns in the local Wiki."},
        "concept_id": {"type": "string", "description": "KnowledgeMap concept id to decompose or inspect."},
        "positioning": {"type": "string", "description": "Where this topic sits in the learner's current route and what understanding should come first."},
        "learning_value": {"type": "string", "description": "Why this topic matters now: the learner problem it solves and the value of learning it."},
        "outcomes": {"type": "array", "items": {"type": "string"}, "description": "Observable things the learner can independently do after learning this topic."},
        "definition": {"type": "string", "description": "Concise definition, purpose, and boundary of the concept."},
        "mechanism": {"type": "string", "description": "Step-by-step mechanism from input to output."},
        "key_terms": {"type": "array", "items": {"type": "string"}, "description": "Important terms and their short explanations."},
        "practice": {"type": "string", "description": "A small, observable practice task."},
        "pitfalls": {"type": "array", "items": {"type": "string"}, "description": "Common misconceptions or failure cases."},
        "questions": {"type": "array", "items": {"type": "string"}, "description": "Open questions worth revisiting."},
        "sources": {"type": "array", "items": {"type": "string"}, "description": "Learner-provided or verified source labels/URLs only."},
    }, "required": ["action"]}}}

    def approval_action_for(self, args: dict) -> str | None:
        return "write learning wiki" if args.get("action") in {"init", "sync", "outline"} else None

    def __call__(self, *, action: str, vault_dir: str = "", title: str = "", enabled: bool = False, concept_id: str = "", positioning: str = "", learning_value: str = "", outcomes: list[str] | None = None, definition: str = "", mechanism: str = "", key_terms: list[str] | None = None, practice: str = "", pitfalls: list[str] | None = None, questions: list[str] | None = None, sources: list[str] | None = None) -> dict:
        if action == "init":
            result = self.wiki.initialize(vault_dir=vault_dir or "learning-wiki", title=title or "Whale 学习 Wiki")
            changed = [f"{result['vault_dir']}/.wiki-schema.md", f"{result['vault_dir']}/purpose.md", f"{result['vault_dir']}/index.md", f"{result['vault_dir']}/log.md"]
            return ok(json.dumps(result, ensure_ascii=False, indent=2), changed)
        if action == "sync":
            result = self.wiki.sync(vault_dir=vault_dir, title=title)
            changed = [str(Path(path).relative_to(self.projects.workspace)) for path in result.pop("changed_files")]
            return ok(json.dumps(result, ensure_ascii=False, indent=2), changed)
        if action == "set_auto_capture":
            result = self.wiki.set_auto_capture(enabled=enabled)
            return ok(json.dumps(result, ensure_ascii=False, indent=2), [".whale_cli/learning/state.json"])
        if action == "outline":
            result = self.wiki.save_outline(concept_id=concept_id, positioning=positioning, learning_value=learning_value, outcomes=outcomes, definition=definition, mechanism=mechanism, key_terms=key_terms, practice=practice, pitfalls=pitfalls, questions=questions, sources=sources)
            return _result(result)
        if action == "show_outline":
            graph = self.wiki.graph_snapshot()
            node = next((item for item in graph["nodes"] if item["id"] == concept_id), None)
            if node is None:
                raise ValueError("unknown concept")
            return ok(json.dumps({"node": node, "page": self.wiki.render_node_page(concept_id)}, ensure_ascii=False, indent=2))
        raise ValueError("action must be init, sync, set_auto_capture, outline, or show_outline")


class OpenLearningWikiTool(_LearningTool):
    name = "OpenLearningWiki"
    description = "Register the generated local learning Wiki with Obsidian and open its index page or one concept page."
    approval_action = "register and open Obsidian wiki"
    schema = {"type": "function", "function": {"name": name, "description": description, "parameters": {"type": "object", "properties": {
        "concept_id": {"type": "string", "description": "Optional KnowledgeMap concept id to open."},
    }}}}

    def __call__(self, *, concept_id: str = "") -> dict:
        return ok(json.dumps(self.wiki.open_in_obsidian(node_id=concept_id), ensure_ascii=False, indent=2))


class SyncToObsidianVaultTool(_LearningTool):
    name = "SyncToObsidianVault"
    description = "Mirror the generated learning Wiki into an explicit existing Obsidian vault, under Whale Learning Wiki/."
    approval_action = "write external Obsidian vault"
    schema = {"type": "function", "function": {"name": name, "description": description, "parameters": {"type": "object", "properties": {
        "vault_path": {"type": "string", "description": "Existing Obsidian vault path. Omit only when OBSIDIAN_VAULT_PATH is set."},
    }}}}

    def __call__(self, *, vault_path: str = "") -> dict:
        result = self.wiki.sync_to_existing_vault(vault_path=vault_path)
        return ok(json.dumps(result, ensure_ascii=False, indent=2), result["copied_files"])
