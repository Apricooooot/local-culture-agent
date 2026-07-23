from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .database import CultureDatabase
from .model import Model


SYSTEM_PROMPT = """你是一个温和、诚实的私人书影音伙伴。
用户的数据来自其本地资料库。不要虚构用户偏好，也不要声称记得没有提供的事情。
回答要自然简洁；当引用记忆时，说明依据是哪一条记录。
模型不能直接修改数据库，所有写入由 harness 完成。"""


@dataclass
class ChatResult:
    reply: str
    intent: str
    memories: list[dict[str, Any]]
    created_entry: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "reply": self.reply,
            "intent": self.intent,
            "memories": self.memories,
            "created_entry": self.created_entry,
        }


class CultureHarness:
    def __init__(self, database: CultureDatabase, model: Model) -> None:
        self.database = database
        self.model = model

    def chat(self, message: str) -> ChatResult:
        message = message.strip()
        if not message:
            raise ValueError("Message cannot be empty")

        parsed = self._parse_record(message)
        if parsed:
            entry = self.database.add_entry(parsed)
            rating = f"，{entry['rating']:g}/10" if entry["rating"] is not None else ""
            reply = (
                f"记好了：{self._kind_name(entry['kind'])}《{entry['title']}》{rating}。"
                "你的原始感受已经完整保存在本地。"
            )
            if entry["tags"]:
                reply += f" 我暂时提取了这些线索：{'、'.join(entry['tags'])}。"
            return ChatResult(reply, "record", [entry], entry)

        intent = self._classify(message)
        memories = self._retrieve(message, intent)

        if intent == "library":
            return ChatResult(self._library_reply(memories), intent, memories)
        if intent == "recommend":
            return ChatResult(self._recommend_reply(memories), intent, memories)
        if intent == "profile":
            return ChatResult(self._profile_reply(memories), intent, memories)

        context = self._memory_context(memories)
        try:
            reply = self.model.complete(
                SYSTEM_PROMPT,
                [{"role": "user", "content": f"相关本地记忆：\n{context}\n\n用户：{message}"}],
            )
        except RuntimeError as exc:
            reply = f"模型暂时不可用（{exc}），但你的本地资料库仍然可以正常记录和查询。"
        return ChatResult(reply, "chat", memories)

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
            word in message
            for word in ("看完", "读完", "记录", "打分", "评分", "看了", "读了")
        )
        title_match = re.search(r"《([^》]{1,100})》", message)
        if not record_signal or not title_match:
            return None

        title = title_match.group(1).strip()
        kind = "book" if any(word in message for word in ("书", "读完", "读了", "阅读")) else "film"
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
        if any(word in message for word in ("推荐", "想看", "想读", "看什么", "读什么")):
            return "recommend"
        if any(word in message for word in ("资料库", "记录过", "看过什么", "读过什么")):
            return "library"
        if any(word in message for word in ("我喜欢", "我的偏好", "品味", "为什么觉得")):
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

    def _recommend_reply(self, memories: list[dict[str, Any]]) -> str:
        if not memories:
            return (
                "我还不了解你的口味。先告诉我一两部你喜欢或不喜欢的书/电影，"
                "或者直接说此刻的心情、时长和想探索的方向。"
            )
        liked = [item for item in memories if (item["rating"] or 0) >= 8]
        signals: list[str] = []
        for item in liked:
            signals.extend(item["tags"])
        top_tags = list(dict.fromkeys(signals))[:4]
        evidence = "、".join(f"《{item['title']}》" for item in liked[:3]) or "最近的记录"
        preference = "、".join(top_tags) or "你记录中的情绪和主题"
        return (
            f"根据你对{evidence}的评价，我会优先寻找带有“{preference}”特质、"
            "同时避开你已经记录过的作品。当前 MVP 还没有接入外部作品目录，"
            "所以我不会编造片名；下一步接入目录后，我会给出 3 个候选及各自的命中点和风险点。"
        )

    @staticmethod
    def _library_reply(memories: list[dict[str, Any]]) -> str:
        if not memories:
            return "你的本地资料库还是空的。可以从“我看完《作品名》，8分……”开始。"
        rows = [
            f"{'🎬' if item['kind'] == 'film' else '📚'}《{item['title']}》"
            f" · {item['rating']:g}/10" if item["rating"] is not None
            else f"{'🎬' if item['kind'] == 'film' else '📚'}《{item['title']}》"
            for item in memories[:8]
        ]
        return "这是我找到的本地记录：\n" + "\n".join(f"• {row}" for row in rows)

    @staticmethod
    def _profile_reply(memories: list[dict[str, Any]]) -> str:
        rated = [item for item in memories if item["rating"] is not None]
        if not rated:
            return "现在还没有足够的评分来形成偏好判断。我的推断会始终注明依据，并允许你纠正。"
        tags: dict[str, list[str]] = {}
        for item in rated:
            if item["rating"] >= 8:
                for tag in item["tags"]:
                    tags.setdefault(tag, []).append(item["title"])
        if not tags:
            return "目前只有评分事实，尚没有稳定的主题偏好信号；我不会过早给你贴标签。"
        details = [
            f"“{tag}”（依据：{'、'.join('《' + title + '》' for title in titles[:3])}）"
            for tag, titles in list(tags.items())[:5]
        ]
        return "目前比较明显的偏好线索是：" + "；".join(details) + "。这些只是可纠正的推断。"

    @staticmethod
    def _kind_name(kind: str) -> str:
        return "书籍" if kind == "book" else "电影"

