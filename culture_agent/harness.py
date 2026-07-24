from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from .catalog import CatalogHub, CatalogItem
from .database import CultureDatabase
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
        language = self._detect_language(message)

        parsed = self._parse_record(message)
        if parsed:
            entry = self.database.add_entry(parsed)
            rating = f"，{entry['rating']:g}/10" if entry["rating"] is not None else ""
            if language == "zh":
                reply = (
                    f"记好了：{self._kind_name(entry['kind'], language)}《{entry['title']}》{rating}。"
                    "你的原始感受已经完整保存在本地。"
                )
                if entry["tags"]:
                    reply += f" 我暂时提取了这些线索：{'、'.join(entry['tags'])}。"
            else:
                rating_en = f", {entry['rating']:g}/10" if entry["rating"] is not None else ""
                reply = (
                    f"Saved locally: {self._kind_name(entry['kind'], language)} "
                    f"《{entry['title']}》{rating_en}. Your original reflection "
                    "has been preserved verbatim."
                )
                if entry["tags"]:
                    reply += f" Initial signals: {', '.join(entry['tags'])}."
            return ChatResult(reply, "record", [entry], entry)

        intent = self._classify(message)
        memories = self._retrieve(message, intent)

        if intent == "library":
            return ChatResult(self._library_reply(memories, language), intent, memories)
        if intent == "recommend":
            catalog_items = self._catalog_candidates(message)
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
            thinking = self._should_think(intent, message)
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

        context = self._memory_context(memories)
        thinking = self._should_think(intent, message)
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
            reply = (
                f"模型暂时不可用（{exc}），但你的本地资料库仍然可以正常记录和查询。"
                if language == "zh"
                else f"The model is unavailable ({exc}), but your local library still works."
            )
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
            "tags": list(entry.get("tags", [])),
        }

    def add_entry(self, entry: dict[str, Any]) -> dict[str, Any]:
        return self.database.add_entry(self.validate_entry(entry))

    def _parse_record(self, message: str) -> dict[str, Any] | None:
        record_signal = any(
            word in message.lower()
            for word in (
                "看完", "读完", "记录", "打分", "评分", "看了", "读了",
                "watched", "finished", "record", "rated", "read",
            )
        )
        title_match = re.search(r"《([^》]{1,100})》", message)
        if not record_signal or not title_match:
            return None

        title = title_match.group(1).strip()
        lowered = message.lower()
        kind = "book" if any(
            word in lowered for word in ("书", "读完", "读了", "阅读", "book", "read")
        ) else "film"
        rating_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:分|/10)", message)
        rating = float(rating_match.group(1)) if rating_match else None
        if rating is not None and not 0 <= rating <= 10:
            raise ValueError("评分需要在 0 到 10 之间")

        creator = ""
        creator_match = re.search(r"([\w\u4e00-\u9fff·]{2,30})(?:的|导演的)《", message)
        if creator_match:
            candidate = creator_match.group(1)
            candidate = re.sub(r"^(?:记录一本书|记录一部电影|我看了|我读了)", "", candidate)
            creator = candidate.strip()

        reflection = message
        tags = self._extract_tags(message)
        return {
            "title": title,
            "creator": creator,
            "kind": kind,
            "status": "finished",
            "rating": rating,
            "reflection": reflection,
            "tags": tags,
        }

    @staticmethod
    def _extract_tags(text: str) -> list[str]:
        signals = {
            "慢节奏": ("慢", "段落略长"),
            "温柔": ("温柔", "治愈"),
            "克制": ("克制", "含蓄"),
            "家庭": ("家庭", "家人"),
            "人生观察": ("人生", "日常"),
            "悬疑": ("悬疑", "推理"),
            "科幻": ("科幻", "未来"),
            "浪漫": ("浪漫", "爱情"),
            "幽默": ("幽默", "好笑"),
            "沉重": ("沉重", "压抑"),
        }
        return [tag for tag, words in signals.items() if any(word in text for word in words)]

    @staticmethod
    def _classify(message: str) -> str:
        lowered = message.lower()
        if any(word in lowered for word in (
            "推荐", "想看", "想读", "看什么", "读什么", "recommend", "suggest",
        )):
            return "recommend"
        if any(word in lowered for word in (
            "资料库", "记录过", "看过什么", "读过什么", "library", "my records",
        )):
            return "library"
        if any(word in lowered for word in (
            "我喜欢", "我的偏好", "品味", "为什么觉得", "my taste",
            "my preferences", "what do i", "what i like",
        )):
            return "profile"
        return "chat"

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
    def _memory_context(memories: list[dict[str, Any]]) -> str:
        if not memories:
            return "暂无相关记录。"
        return "\n".join(
            f"- 《{item['title']}》 {item['rating'] if item['rating'] is not None else '未评分'}/10；"
            f"标签：{','.join(item['tags']) or '无'}；心得：{item['reflection'][:160]}"
            for item in memories
        )

    def _recommend_reply(
        self,
        message: str,
        memories: list[dict[str, Any]],
        language: str,
        history: list[dict[str, str]] | None = None,
        catalog_items: list[CatalogItem] | None = None,
    ) -> str:
        context = self._memory_context(memories)
        candidates = catalog_items or []
        if self.catalog and not candidates:
            return (
                "开放资料库没有返回符合条件的可靠候选。你可以放宽年份、类型或时长条件后重试。"
                if language == "zh"
                else "The open catalogs returned no reliable candidates. Try relaxing the year, genre, or runtime constraints."
            )
        candidate_context = (
            "\n".join(
                f"- [{item.provider}:{item.provider_id}] {item.title}"
                f" ({item.year or 'year unknown'}), creator: {item.creator or 'unknown'},"
                f" source: {item.source_url}"
                for item in candidates
            )
            if candidates
            else "No catalog provider is configured; clearly label any general-knowledge suggestions as unverified."
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
            if language == "zh":
                return (
                    f"推荐模型暂时不可用（{exc}）。你的本地记录没有丢失；"
                    "请确认 Ollama 正在运行后重试。"
                )
            return (
                f"The recommendation model is unavailable ({exc}). Your local "
                "records are safe; confirm that Ollama is running and try again."
            )

    def _catalog_candidates(self, message: str) -> list[CatalogItem]:
        if not self.catalog:
            return []
        kind = "book" if any(
            token in message.lower()
            for token in ("书", "小说", "阅读", "读", "book", "novel", "read")
        ) else "film"
        try:
            return self.catalog.candidates(message, kind, limit=12)
        except (OSError, ValueError, json.JSONDecodeError):
            return []

    @staticmethod
    def _should_think(intent: str, message: str) -> bool:
        if intent in {"record", "library", "recommend"}:
            return False
        lowered = message.lower()
        complex_signals = (
            "比较", "对比", "综合", "深入分析", "年度总结", "年度回顾",
            "复盘", "共同主题", "变化趋势", "矛盾", "联系起来",
            "compare", "contrast", "analyze deeply", "year in review",
            "overall pattern", "trend", "conflicting preferences",
        )
        return any(signal in lowered for signal in complex_signals)

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
        # Small local models occasionally echo the current request once or twice.
        while current and cleaned.startswith(current):
            cleaned = cleaned[len(current):].lstrip(" \t\r\n:：-—")
        return cleaned or reply.strip()

    @staticmethod
    def _library_reply(memories: list[dict[str, Any]], language: str) -> str:
        if not memories:
            if language == "en":
                return "Your local library is empty. Try: “I watched 《Arrival》, 9/10…”"
            return "你的本地资料库还是空的。可以从“我看完《作品名》，8分……”开始。"
        rows = [
            f"{'🎬' if item['kind'] == 'film' else '📚'}《{item['title']}》"
            f" · {item['rating']:g}/10" if item["rating"] is not None
            else f"{'🎬' if item['kind'] == 'film' else '📚'}《{item['title']}》"
            for item in memories[:8]
        ]
        prefix = "这是我找到的本地记录：" if language == "zh" else "Here are your local records:"
        return prefix + "\n" + "\n".join(f"• {row}" for row in rows)

    @staticmethod
    def _profile_reply(memories: list[dict[str, Any]], language: str) -> str:
        rated = [item for item in memories if item["rating"] is not None]
        if not rated:
            if language == "en":
                return (
                    "There are not enough ratings to infer a preference yet. "
                    "Any future inference will cite its evidence and remain correctable."
                )
            return "现在还没有足够的评分来形成偏好判断。我的推断会始终注明依据，并允许你纠正。"
        tags: dict[str, list[str]] = {}
        for item in rated:
            if item["rating"] >= 8:
                for tag in item["tags"]:
                    tags.setdefault(tag, []).append(item["title"])
        if not tags:
            if language == "en":
                return (
                    "I have rating facts, but no stable theme signal yet. "
                    "I will not label your taste prematurely."
                )
            return "目前只有评分事实，尚没有稳定的主题偏好信号；我不会过早给你贴标签。"
        details = [
            f"“{tag}”（依据：{'、'.join('《' + title + '》' for title in titles[:3])}）"
            for tag, titles in list(tags.items())[:5]
        ]
        if language == "en":
            details_en = [
                f"{tag} (evidence: {', '.join('《' + title + '》' for title in titles[:3])})"
                for tag, titles in list(tags.items())[:5]
            ]
            return (
                "Current preference signals: " + "; ".join(details_en)
                + ". These are correctable inferences, not permanent labels."
            )
        return "目前比较明显的偏好线索是：" + "；".join(details) + "。这些只是可纠正的推断。"

    def _profile_model_reply(
        self,
        message: str,
        memories: list[dict[str, Any]],
        language: str,
        history: list[dict[str, str]],
    ) -> str:
        context = self._memory_context(memories)
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

    @staticmethod
    def _kind_name(kind: str, language: str = "zh") -> str:
        if language == "en":
            return "book" if kind == "book" else "film"
        return "书籍" if kind == "book" else "电影"

    @staticmethod
    def _detect_language(message: str) -> str:
        # Language is scoped to the current turn; users can switch naturally
        # without changing a global profile setting.
        cjk_count = sum("\u4e00" <= character <= "\u9fff" for character in message)
        return "zh" if cjk_count >= 2 else "en"

