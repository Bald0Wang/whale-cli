"""Product catalogue for the local Datawhale corpus.

The knowledge tornado is deliberately *not* a learner-generated plan.  It is
a deterministic, read-only map of every document imported into a project's
Datawhale BM25 corpus.  Course hierarchy and tags are source evidence; no
mastery or invented prerequisite claims are mixed into this catalogue.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from whale_cli.subagents import DatawhaleKnowledgeBase


TAXONOMY_FILENAME = "datawhale_knowledge_tornado.json"
PAGE_SIZE = 30

_CLUSTERS: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    ("llm-agent", "大模型与智能体", "从提示词、RAG 到 Agent 的应用与工程资料。", ("大模型", "llm", "agent", "智能体", "rag", "提示词", "prompt", "transformer", "gpt", "qwen", "微调", "多模态")),
    ("machine-learning", "机器学习与深度学习", "模型训练、特征、评估与深度学习基础。", ("机器学习", "深度学习", "监督学习", "强化学习", "神经网络", "模型训练", "分类", "回归")),
    ("data-analysis", "数据分析与挖掘", "数据处理、统计、可视化与数据挖掘实践。", ("数据分析", "数据挖掘", "pandas", "numpy", "可视化", "统计", "sql", "数据处理")),
    ("nlp", "自然语言处理", "文本、语言模型、信息抽取与对话相关内容。", ("自然语言处理", "nlp", "文本", "语音", "分词", "信息抽取", "问答")),
    ("computer-vision", "计算机视觉", "图像、视频、检测、分割与视觉模型内容。", ("计算机视觉", "图像", "视觉", "目标检测", "图像分类", "分割", "opencv")),
    ("recommender", "推荐系统", "召回、排序、特征与推荐项目资料。", ("推荐", "rec", "召回", "排序", "广告")),
    ("programming", "编程与开发基础", "Python、前端、算法、环境配置和编程练习。", ("python", "javascript", "c++", "java", "编程", "算法", "环境配置", "代码", "html", "css")),
    ("engineering", "工程化与部署", "MLOps、部署、工具链、开源协作与项目工程。", ("部署", "工程", "docker", "linux", "git", "mcp", "工具实践", "开发工具", "云")),
    ("competition", "竞赛与案例项目", "竞赛解读、案例项目、学习营与真题实践。", ("竞赛", "案例项目", "真题", "学习营", "baseline", "挑战赛")),
)


def _clean(value: object, limit: int = 360) -> str:
    return " ".join(str(value or "").split())[:limit]


def _slug(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return value or "resource"


def _excerpt(value: str, limit: int = 280) -> str:
    cleaned = _clean(value, limit=limit)
    return cleaned + ("..." if len(_clean(value, limit=limit + 1)) > limit else "")


class DatawhaleKnowledgeTornado:
    """Build and browse a source-grounded Datawhale product catalogue."""

    def __init__(self, knowledge_base: DatawhaleKnowledgeBase) -> None:
        self.knowledge_base = knowledge_base
        self.path = knowledge_base.path.parent / TAXONOMY_FILENAME

    def _fingerprint(self) -> str:
        if not self.knowledge_base.available:
            return ""
        stat = self.knowledge_base.path.stat()
        return f"{stat.st_mtime_ns}:{stat.st_size}"

    def _cluster_for(self, document: Any) -> str:
        metadata = document.metadata if isinstance(document.metadata, dict) else {}
        haystack = " ".join((document.title, " ".join(document.tags), str(metadata.get("courseTitle") or ""))).lower()
        for cluster_id, _, _, terms in _CLUSTERS:
            if any(term.lower() in haystack for term in terms):
                return cluster_id
        return "community"

    def _document(self, document: Any, ordinal: int) -> dict[str, Any]:
        metadata = document.metadata if isinstance(document.metadata, dict) else {}
        course = _clean(metadata.get("courseTitle"), 160)
        section = [str(item) for item in metadata.get("sectionPath", []) if str(item).strip()] if isinstance(metadata.get("sectionPath"), list) else []
        document_id = _clean(document.id, 180) or f"resource-{ordinal}-{_slug(document.title)}"
        return {
            "id": document_id,
            "title": _clean(document.title, 220),
            "url": _clean(document.url, 500),
            "source_type": _clean(document.source_type, 60) or "unknown",
            "cluster_id": self._cluster_for(document),
            "course": course,
            "course_id": _clean(metadata.get("courseId"), 80),
            "section_path": section,
            "tags": list(dict.fromkeys(_clean(tag, 50) for tag in document.tags if _clean(tag, 50)))[:12],
            "excerpt": _excerpt(document.text),
            "stars": document.stars,
        }

    def build(self) -> dict[str, Any]:
        """Persist a compact, deterministic catalogue for the active project."""
        documents = [self._document(document, index) for index, document in enumerate(self.knowledge_base.documents(), start=1)]
        counts = Counter(item["cluster_id"] for item in documents)
        cluster_specs = list(_CLUSTERS) + [("community", "社区与其他资源", "尚未归入专门领域的课程、项目与社区资料。", tuple())]
        clusters = [
            {"id": cluster_id, "name": name, "description": description, "document_count": counts.get(cluster_id, 0)}
            for cluster_id, name, description, _ in cluster_specs
            if counts.get(cluster_id, 0)
        ]
        source_counts = Counter(item["source_type"] for item in documents)
        payload = {
            "schema_version": 3,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "corpus_fingerprint": self._fingerprint(),
            "summary": {
                "document_count": len(documents),
                "cluster_count": len(clusters),
                "source_counts": dict(sorted(source_counts.items())),
            },
            "clusters": clusters,
            "documents": documents,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(self.path)
        return payload

    def _catalogue(self) -> dict[str, Any]:
        if not self.knowledge_base.available:
            return {"schema_version": 3, "generated_at": "", "corpus_fingerprint": "", "summary": {"document_count": 0, "cluster_count": 0, "source_counts": {}}, "clusters": [], "documents": []}
        try:
            saved = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            saved = {}
        if not isinstance(saved, dict) or saved.get("schema_version") != 3 or saved.get("corpus_fingerprint") != self._fingerprint():
            return self.build()
        return saved

    @staticmethod
    def _course_groups(documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
        groups: dict[str, dict[str, Any]] = {}
        for item in documents:
            raw_course_id = str(item.get("course_id") or "")
            group_id = f"course:{raw_course_id}" if raw_course_id else f"resource:{item['id']}"
            title = str(item.get("course") or item.get("title") or "未命名资料")
            group = groups.setdefault(group_id, {"id": group_id, "title": title, "document_count": 0, "source_types": set()})
            group["document_count"] += 1
            group["source_types"].add(item.get("source_type") or "unknown")
        return [
            {**group, "source_types": sorted(group["source_types"])}
            for group in sorted(groups.values(), key=lambda item: (-item["document_count"], item["title"]))
        ]

    def snapshot(self, *, cluster_id: str = "", course_id: str = "", query: str = "", source_type: str = "", page: int = 1, page_size: int = PAGE_SIZE) -> dict[str, Any]:
        catalogue = self._catalogue()
        documents = list(catalogue.get("documents") or [])
        query_terms = [term for term in re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]+", query.lower()) if term]

        def matches(item: dict[str, Any]) -> bool:
            if cluster_id and item.get("cluster_id") != cluster_id:
                return False
            item_group = f"course:{item.get('course_id')}" if item.get("course_id") else f"resource:{item.get('id')}"
            if course_id and item_group != course_id:
                return False
            if source_type and item.get("source_type") != source_type:
                return False
            haystack = " ".join((item.get("title", ""), item.get("course", ""), item.get("excerpt", ""), " ".join(item.get("tags") or []))).lower()
            return all(term in haystack for term in query_terms)

        filtered = [item for item in documents if matches(item)]
        page_size = max(1, min(int(page_size or PAGE_SIZE), 60))
        page = max(1, int(page or 1))
        total_pages = max(1, (len(filtered) + page_size - 1) // page_size)
        page = min(page, total_pages)
        start = (page - 1) * page_size
        cluster_lookup = {item["id"]: item for item in catalogue.get("clusters", [])}
        if course_id:
            current_course = next((item for item in self._course_groups(documents) if item["id"] == course_id), None)
            root_label = current_course["title"] if current_course else "课程资料"
            graph_nodes = [{"id": "course-root", "label": root_label, "kind": "root", "count": len(filtered)}]
            graph_nodes.extend({"id": item["id"], "label": item["title"], "kind": "resource", "count": 1} for item in filtered[:42])
            graph_edges = [{"id": f"course-{item['id']}", "source": "course-root", "target": item["id"], "label": "包含"} for item in filtered[:42]]
            navigation = {"level": "course", "title": root_label, "description": "点击资料查看原始链接、标签与课程位置。", "course_id": course_id, "cluster_id": cluster_id}
        elif cluster_id:
            current_cluster = cluster_lookup.get(cluster_id, {"name": "资料领域", "description": ""})
            courses = self._course_groups([item for item in documents if item.get("cluster_id") == cluster_id])
            graph_nodes = [{"id": "cluster-root", "label": current_cluster["name"], "kind": "root", "count": len(courses)}]
            graph_nodes.extend({"id": item["id"], "label": item["title"], "kind": "course", "count": item["document_count"]} for item in courses[:42])
            graph_edges = [{"id": f"cluster-{item['id']}", "source": "cluster-root", "target": item["id"], "label": "课程/项目"} for item in courses[:42]]
            navigation = {"level": "cluster", "title": current_cluster["name"], "description": current_cluster.get("description", ""), "cluster_id": cluster_id}
        else:
            graph_nodes = [{"id": "datawhale", "label": "Datawhale 全部内容", "kind": "root", "count": catalogue["summary"]["document_count"]}]
            graph_nodes.extend({"id": item["id"], "label": item["name"], "kind": "cluster", "count": item["document_count"]} for item in catalogue.get("clusters", []))
            graph_edges = [{"id": f"datawhale-{item['id']}", "source": "datawhale", "target": item["id"], "label": "主题归类"} for item in catalogue.get("clusters", [])]
            navigation = {"level": "overview", "title": "Datawhale 全部内容", "description": "从一个领域进入，再展开课程、项目与章节资料。"}
        return {
            "ready": bool(documents),
            "generated_at": catalogue.get("generated_at", ""),
            "summary": catalogue.get("summary", {}),
            "clusters": catalogue.get("clusters", []),
            "filters": {"cluster_id": cluster_id, "course_id": course_id, "query": query, "source_type": source_type},
            "source_types": sorted((catalogue.get("summary", {}).get("source_counts") or {}).keys()),
            "graph": {"nodes": graph_nodes, "edges": graph_edges},
            "navigation": navigation,
            "documents": filtered[start : start + page_size],
            "pagination": {"page": page, "page_size": page_size, "total": len(filtered), "total_pages": total_pages},
        }

    def document(self, document_id: str) -> dict[str, Any]:
        catalogue = self._catalogue()
        current = next((item for item in catalogue.get("documents", []) if item.get("id") == document_id), None)
        if current is None:
            raise ValueError("找不到这条 Datawhale 资料。")
        tags = set(current.get("tags") or [])
        related = [
            item for item in catalogue.get("documents", [])
            if item.get("id") != document_id and item.get("cluster_id") == current.get("cluster_id") and tags & set(item.get("tags") or [])
        ][:5]
        return {"document": current, "related": related}
