"""Grounded retrieval for the Datawhale learning-planning subagent."""
from __future__ import annotations

import json
import math
import os
import re
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any


PROJECT_DATAWHALE_KB_PATH = Path(__file__).resolve().parents[3] / ".whale_cli" / "datawhale_bm25_documents.jsonl"


@dataclass(frozen=True)
class DatawhaleDocument:
    title: str
    url: str
    text: str
    tags: tuple[str, ...]
    tokens: tuple[str, ...]
    stars: int


def default_datawhale_kb_path() -> Path:
    """Resolve the project corpus, with an opt-in override for deployments."""
    configured = os.getenv("DATAWHALE_KB_PATH")
    if configured:
        return Path(configured).expanduser()
    return PROJECT_DATAWHALE_KB_PATH


def _tokenize(value: str) -> tuple[str, ...]:
    """Keep the JSONL's existing tokens and add deterministic query tokens."""
    normalized = value.lower()
    terms = re.findall(r"[a-z0-9][a-z0-9_+.-]*", normalized)
    for group in re.findall(r"[\u4e00-\u9fff]+", normalized):
        terms.append(group)
        terms.extend(group[index : index + 2] for index in range(max(0, len(group) - 1)))
    return tuple(term for term in terms if len(term) > 1)


class DatawhaleKnowledgeBase:
    """Read a JSONL corpus and rank it with the standard Okapi BM25 formula."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else default_datawhale_kb_path()

    @property
    def available(self) -> bool:
        return self.path.is_file()

    @lru_cache(maxsize=1)
    def documents(self) -> tuple[DatawhaleDocument, ...]:
        records: list[DatawhaleDocument] = []
        if not self.available:
            return tuple()
        with self.path.open("r", encoding="utf-8") as source:
            for line in source:
                try:
                    raw = json.loads(line)
                    metadata = raw.get("metadata") or {}
                    records.append(
                        DatawhaleDocument(
                            title=str(raw.get("title") or "Untitled Datawhale project"),
                            url=str(raw.get("url") or ""),
                            text=str(raw.get("text") or ""),
                            tags=tuple(str(tag) for tag in raw.get("tags") or []),
                            tokens=tuple(str(token).lower() for token in raw.get("tokens") or []),
                            stars=int(metadata.get("stars") or 0),
                        )
                    )
                except (TypeError, ValueError, json.JSONDecodeError):
                    continue
        return tuple(records)

    @staticmethod
    def _document_tokens(document: DatawhaleDocument) -> tuple[str, ...]:
        # The corpus provides pre-tokenized text. Title and tags are included so
        # they participate in the same BM25 term-frequency calculation.
        return tuple(token for token in (
            *document.tokens,
            *_tokenize(document.title),
            *_tokenize(" ".join(document.tags)),
        ) if token)

    @lru_cache(maxsize=1)
    def _index(self) -> tuple[tuple[tuple[str, ...], ...], tuple[Counter[str], ...], dict[str, float], float]:
        tokenized = tuple(self._document_tokens(document) for document in self.documents())
        if not tokenized:
            return tuple(), tuple(), {}, 0.0
        frequencies = tuple(Counter(tokens) for tokens in tokenized)
        document_frequency = Counter(term for tokens in tokenized for term in set(tokens))
        total_documents = len(tokenized)
        inverse_frequency = {
            term: math.log(1 + (total_documents - count + 0.5) / (count + 0.5))
            for term, count in document_frequency.items()
        }
        average_length = sum(len(tokens) for tokens in tokenized) / total_documents
        return tokenized, frequencies, inverse_frequency, average_length

    def replace_corpus(self, raw: bytes) -> int:
        """Validate then atomically replace this JSONL corpus; return record count."""
        if not raw:
            raise ValueError("Datawhale knowledge base is empty.")
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("Datawhale knowledge base must be UTF-8 JSONL.") from exc
        records = 0
        for line_number, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at line {line_number}.") from exc
            if not isinstance(record, dict) or not str(record.get("title") or "").strip() or not str(record.get("text") or "").strip():
                raise ValueError(f"JSONL line {line_number} needs non-empty title and text.")
            if not isinstance(record.get("tokens", []), list) or not isinstance(record.get("tags", []), list):
                raise ValueError(f"JSONL line {line_number} needs tokens and tags lists.")
            records += 1
        if not records:
            raise ValueError("Datawhale knowledge base has no documents.")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(f".{self.path.name}.upload.tmp")
        try:
            temporary.write_text(text.rstrip() + "\n", encoding="utf-8")
            temporary.replace(self.path)
        finally:
            temporary.unlink(missing_ok=True)
        self.documents.cache_clear()
        self._index.cache_clear()
        return records

    def search(self, query: str, limit: int = 6) -> list[DatawhaleDocument]:
        query_tokens = _tokenize(query)
        if not query_tokens:
            return []
        documents = self.documents()
        tokenized, frequencies, inverse_frequency, average_length = self._index()
        if not documents or not average_length:
            return []
        scored: list[tuple[float, DatawhaleDocument]] = []
        k1 = 1.5
        b = 0.75
        for document, tokens, frequency in zip(documents, tokenized, frequencies):
            score = 0.0
            length_factor = k1 * (1 - b + b * len(tokens) / average_length)
            for term in query_tokens:
                term_frequency = frequency.get(term, 0)
                if term_frequency:
                    score += inverse_frequency.get(term, 0.0) * (term_frequency * (k1 + 1)) / (term_frequency + length_factor)
            if score:
                scored.append((score, document))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [document for _, document in scored[:limit]]

    def context_for(self, query: str, limit: int = 6) -> str:
        matches = self.search(query, limit=limit)
        if not matches:
            return "No relevant Datawhale projects were found in the local corpus."
        sections = []
        for index, document in enumerate(matches, start=1):
            tags = ", ".join(document.tags[:8]) or "untagged"
            sections.append(
                f"[{index}] {document.title}\n"
                f"URL: {document.url or 'not provided'}\n"
                f"Tags: {tags}\n"
                f"Evidence: {document.text[:700]}"
            )
        return "\n\n".join(sections)
