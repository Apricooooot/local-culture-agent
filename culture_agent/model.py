from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Protocol


class Model(Protocol):
    name: str

    def complete(self, system: str, messages: list[dict[str, str]]) -> str: ...


@dataclass
class OpenAICompatibleModel:
    base_url: str
    model: str
    api_key: str = ""
    timeout: int = 60

    @property
    def name(self) -> str:
        return self.model

    def complete(self, system: str, messages: list[dict[str, str]]) -> str:
        # Remote providers are opt-in. The harness is responsible for retrieving
        # only the minimum local context required for this request.
        payload = json.dumps(
            {
                "model": self.model,
                "messages": [{"role": "system", "content": system}, *messages],
                "temperature": 0.6,
            }
        ).encode()
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = urllib.request.Request(
            f"{self.base_url.rstrip('/')}/chat/completions",
            data=payload,
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                data = json.loads(response.read())
            return data["choices"][0]["message"]["content"]
        except (urllib.error.URLError, KeyError, IndexError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Model request failed: {exc}") from exc


class OfflineModel:
    name = "offline"

    def complete(self, system: str, messages: list[dict[str, str]]) -> str:
        del system
        last = messages[-1]["content"] if messages else ""
        is_chinese = any("\u4e00" <= character <= "\u9fff" for character in last)
        if not is_chinese:
            return (
                "I am running in offline mode. I can still record, search, and "
                "organize your local book and film memories. Tell me a little "
                "more about what you want, and I will use only your local records."
            )
        return (
            "我现在运行在离线模式，仍然可以替你记录、搜索和整理书影音记忆。"
            f"关于“{last[:60]}”，如果你告诉我更多具体偏好，我也可以结合本地记录继续聊。"
        )


def model_from_environment() -> Model:
    provider = os.getenv("CULTURE_AGENT_MODEL_PROVIDER", "offline").lower()
    if provider in {"openai", "openai-compatible", "ollama"}:
        return OpenAICompatibleModel(
            base_url=os.getenv("CULTURE_AGENT_MODEL_BASE_URL", "http://localhost:11434/v1"),
            model=os.getenv("CULTURE_AGENT_MODEL_NAME", "qwen3:8b"),
            api_key=os.getenv("CULTURE_AGENT_API_KEY", ""),
        )
    return OfflineModel()
