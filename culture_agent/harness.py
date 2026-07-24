from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from .catalog import CatalogHub, CatalogItem
from .database import CultureDatabase
from .i18n import (
    RECORD_SIGNALS,
    canonical_tag,
    classify_intent,
    detect_language,
    extract_creator,
    extract_rating,
    extract_tags,
    extract_title,
    has_signal,
    is_book_request,
    join_localized,
    localized_tags,
    should_think,
    tag_label,
    translate,
)
from .model import Model


SYSTEM_PROMPT = """You are a warm, honest companion for books and films.
Reply in the language used by the user's current message.
User data comes from a local library. Never invent a preference or claim to
remember something that was not provided. When using memory, identify the
supporting record. The model cannot write to storage; all writes are performed
and validated by the harness.
Use the recent conversation to resolve follow-up constraints and references.
Answer directly. Do not repeat, quote, or paraphrase the user's request before
answering."""


@dataclass
class ChatResult:
    reply: str
    intent: str
    memories: list[dict[str, Any]]
    created_entry: dict[str, Any] | None = None
    thinking_used: bool = False
    catalog_items: list[CatalogItem] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "reply": self.reply,
            "intent": self.intent,
            "memories": self.memories,
            "created_entry": self.created_entry,
            "thinking_used": self.thinking_used,
            "catalog_items": [
                item.as_dict() for item in (self.catalog_items or [])
            ],
        }


class CultureHarness:
    def __init__(
        self,
        database: CultureDatabase,
        model: Model,
        catalog: CatalogHub | None = None,
    ) -> None:
        self.database = database
        self.model = model
        self.catalog = catalog

    def chat(
        self,
        message: str,
        history: list[dict[str, str]] | None = None,
    ) -> ChatResult:
        message = message.strip()
        if not message:
            raise ValueError("Message cannot be empty")
        recent_history = self._normalize_history(history)
        language = detect_language(message)
        intent = classify_intent(message)

        # Explicit conversational intents take precedence over heuristic
        # unquoted-title parsing. This prevents phrases such as "a film that
        # makes me happy after watching it" from becoming a fake record.
        parsed = self._parse_record(message, language) if intent == "chat" else None
        if parsed:
            entry = self.database.add_entry(parsed)
            rating = (
                translate(language, "rating", value=f"{entry['rating']:g}")
                if entry["rating"] is not None
                else ""
            )
            reply = translate(
                language,
                "saved",
                kind=translate(language, entry["kind"]),
                title=entry["title"],
                rating=rating,
            )
            if entry["tags"]:
                reply += translate(
                    language,
                    "signals",
                    tags=join_localized(
                        localized_tags(entry["tags"], language),
                        language,
                    ),
                )
            return ChatResult(reply, "record", [entry], entry)

        memories = self._retrieve(message, intent)

        if intent == "library":
            return ChatResult(self._library_reply(memories, language), intent, memories)
        if intent == "recommend":
            catalog_items = self._catalog_candidates(message, language)
            return ChatResult(
                self._recommend_reply(
                    message,
                    memories,
                    language,
                    recent_history,
                    catalog_items,
                ),
                intent,
                memories,
                catalog_items=catalog_items,
            )
        if intent == "profile":
            thinking = should_think(message)
            if thinking and memories:
                return ChatResult(
                    self._profile_model_reply(
                        message,
                        memories,
                        language,
                        recent_history,
                    ),
                    intent,
                    memories,
                    thinking_used=True,
                )
            return ChatResult(self._profile_reply(memories, language), intent, memories)

        context = self._memory_context(memories, language)
        thinking = should_think(message)
        try:
            reply = self.model.complete(
                SYSTEM_PROMPT,
                [
                    {
                        "role": "system",
                        "content": f"Relevant local memories for this turn:\n{context}",
                    },
                    *recent_history,
                    {"role": "user", "content": message},
                ],
                thinking=thinking,
            )
            reply = self._clean_model_reply(reply, message)
        except RuntimeError as exc:
            reply = translate(language, "model_unavailable", error=exc)
        return ChatResult(reply, "chat", memories, thinking_used=thinking)

    @staticmethod
    def validate_entry(entry: dict[str, Any]) -> dict[str, Any]:
        title = str(entry.get("title", "")).strip()
        kind = str(entry.get("kind", "")).lower()
        if not title:
            raise ValueError("Title is required")
        if kind not in {"book", "film"}:
            raise ValueError("Kind must be 'book' or 'film'")
        rating = entry.get("rating")
        if rating is not None:
            rating = float(rating)
            if not 0 <= rating <= 10:
                raise ValueError("Rating must be between 0 and 10")
        return {
            "title": title,
            "creator": str(entry.get("creator", "")).strip(),
            "kind": kind,
            "status": str(entry.get("status", "finished")).strip() or "finished",
            "rating": rating,
            "reflection": str(entry.get("reflection", "")).strip(),
            "tags": [
                canonical_tag(str(tag).strip())
                for tag in entry.get("tags", [])
                if str(tag).strip()
            ],
        }

    def add_entry(self, entry: dict[str, Any]) -> dict[str, Any]:
        return self.database.add_entry(self.validate_entry(entry))

    @staticmethod
    def _parse_record(message: str, language: str) -> dict[str, Any] | None:
        if not has_signal(message, RECORD_SIGNALS):
            return None
        title = extract_title(message, language)
        if not title:
            return None
        rating = extract_rating(message)
        if rating is not None and not 0 <= rating <= 10:
            raise ValueError(translate(language, "rating_invalid"))
        return {
            "title": title,
            "creator": extract_creator(message, language),
            "kind": "book" if is_book_request(message) else "film",
            "status": "finished",
            "rating": rating,
            "reflection": message,
            "tags": extract_tags(message),
        }

    def _retrieve(self, message: str, intent: str) -> list[dict[str, Any]]:
        if intent in {"recommend", "profile"}:
            entries = self.database.list_entries(50)
            return sorted(
                entries,
                key=lambda item: (item["rating"] is not None, item["rating"] or 0),
                reverse=True,
            )[:8]
        matches = self.database.search(message, 8)
        return matches or self.database.list_entries(5)

    @staticmethod
    def _memory_context(memories: list[dict[str, Any]], language: str) -> str:
        if not memories:
            return translate(language, "no_memories")
        rows = []
        for item in memories:
            rating = (
                f"{item['rating']:g}/10"
                if item["rating"] is not None
                else translate(language, "unrated")
            )
            tags = join_localized(localized_tags(item["tags"], language), language)
            rows.append(
                f"- {item['title']} {rating}; "
                f"{translate(language, 'memory_tags')}: "
                f"{tags or translate(language, 'none')}; "
                f"{translate(language, 'memory_reflection')}: "
                f"{item['reflection'][:160]}"
            )
        return "\n".join(rows)

    def _recommend_reply(
        self,
        message: str,
        memories: list[dict[str, Any]],
        language: str,
        history: list[dict[str, str]] | None = None,
        catalog_items: list[CatalogItem] | None = None,
    ) -> str:
        context = self._memory_context(memories, language)
        candidates = catalog_items or []
        candidate_context = (
            "\n".join(
                f"- [{item.provider}:{item.provider_id}] {item.title}"
                f" ({item.year or 'year unknown'}), creator: {item.creator or 'unknown'},"
                f" source: {item.source_url}"
                for item in candidates
            )
            if candidates
            else (
                "The configured catalogs returned no verified candidates. "
                "Continue with real, widely known general-knowledge suggestions "
                "and clearly label them as unverified."
                if self.catalog
                else "No catalog provider is configured; clearly label any "
                "general-knowledge suggestions as unverified."
            )
        )
        recommendation_system = f"""{SYSTEM_PROMPT}

For this recommendation request, preserve every constraint established in the
recent conversation unless the user changes it. Treat the current message as a
follow-up to the previous recommendations when appropriate.
Recommend up to five real, widely known books or films. Give a brief reason for
each and one useful caveat when relevant. Do not recommend titles already in
the local records. You may use general cultural knowledge. Never create a
plausible-sounding title, translated title, release year, creator, or plot
detail. Omit any candidate whose identity or basic facts you are unsure about.
Do not discuss catalog availability unless the user asks about it.

Relevant local records:
{context}

Verified catalog candidates:
{candidate_context}

When verified candidates are present, recommend only titles from that list and
preserve their IDs, years, creators, and source URLs exactly."""
        try:
            reply = self.model.complete(
                recommendation_system,
                [
                    *self._normalize_history(history),
                    {"role": "user", "content": message},
                ],
                thinking=False,
            )
            return self._clean_model_reply(reply, message)
        except RuntimeError as exc:
            return translate(language, "recommendation_unavailable", error=exc)

    def _catalog_candidates(self, message: str, language: str) -> list[CatalogItem]:
        if not self.catalog:
            return []
        kind = "book" if is_book_request(message) else "film"
        try:
            return self.catalog.candidates(message, kind, limit=12, language=language)
        except (OSError, ValueError, json.JSONDecodeError):
            return []

    @staticmethod
    def _normalize_history(
        history: list[dict[str, str]] | None,
    ) -> list[dict[str, str]]:
        if not isinstance(history, list):
            return []
        normalized: list[dict[str, str]] = []
        for item in history[-12:]:
            if not isinstance(item, dict):
                continue
            role = item.get("role")
            content = item.get("content")
            if role not in {"user", "assistant"} or not isinstance(content, str):
                continue
            content = content.strip()
            if content:
                normalized.append({"role": role, "content": content[:4000]})
        return normalized

    @staticmethod
    def _clean_model_reply(reply: str, message: str) -> str:
        cleaned = re.sub(r"<think>.*?</think>", "", reply, flags=re.DOTALL).strip()
        current = message.strip()
        while current and cleaned.startswith(current):
            cleaned = cleaned[len(current):].lstrip(" \t\r\n:：-—")
        return cleaned or reply.strip()

    @staticmethod
    def _library_reply(memories: list[dict[str, Any]], language: str) -> str:
        if not memories:
            return translate(language, "library_empty")
        rows = []
        for item in memories[:8]:
            icon = "🎬" if item["kind"] == "film" else "📚"
            rating = (
                f" · {item['rating']:g}/10"
                if item["rating"] is not None
                else ""
            )
            rows.append(f"• {icon} {item['title']}{rating}")
        return translate(language, "library_prefix") + "\n" + "\n".join(rows)

    @staticmethod
    def _profile_reply(memories: list[dict[str, Any]], language: str) -> str:
        rated = [item for item in memories if item["rating"] is not None]
        if not rated:
            return translate(language, "profile_insufficient")
        tags: dict[str, list[str]] = {}
        for item in rated:
            if item["rating"] >= 8:
                for value in item["tags"]:
                    tags.setdefault(canonical_tag(value), []).append(item["title"])
        if not tags:
            return translate(language, "profile_unstable")
        details = []
        for tag, titles in list(tags.items())[:5]:
            evidence = join_localized(
                titles[:3],
                language,
            )
            details.append(
                f"{tag_label(tag, language)} "
                f"({translate(language, 'evidence')}: {evidence})"
            )
        return translate(
            language,
            "profile_result",
            details="; ".join(details),
        )

    def _profile_model_reply(
        self,
        message: str,
        memories: list[dict[str, Any]],
        language: str,
        history: list[dict[str, str]],
    ) -> str:
        context = self._memory_context(memories, language)
        system = f"""{SYSTEM_PROMPT}

Analyze patterns across the user's local records. Separate direct facts from
inferences, cite the supporting titles for every preference claim, discuss
contradictory evidence, and avoid permanent personality labels.

Local records:
{context}"""
        try:
            reply = self.model.complete(
                system,
                [*history, {"role": "user", "content": message}],
                thinking=True,
            )
            return self._clean_model_reply(reply, message)
        except RuntimeError:
            return self._profile_reply(memories, language)

