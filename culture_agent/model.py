from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Protocol


class Model(Protocol):
    name: str

    def complete(
        self,
        system: str,
        messages: list[dict[str, str]],
        *,
        thinking: bool = False,
    ) -> str: ...


@dataclass
class OpenAICompatibleModel:
    base_url: str
    model: str
    api_key: str = ""
    timeout: int = 60

    @property
    def name(self) -> str:
        return self.model

    def complete(
        self,
        system: str,
        messages: list[dict[str, str]],
        *,
        thinking: bool = False,
    ) -> str:
        # Remote providers are opt-in. The harness is responsible for retrieving
        # only the minimum local context required for this request.
        body = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, *messages],
            "temperature": 0.6,
        }
        if thinking:
            body["reasoning_effort"] = "medium"
        payload = json.dumps(body).encode()
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

    def complete(
        self,
        system: str,
        messages: list[dict[str, str]],
        *,
        thinking: bool = False,
    ) -> str:
        del thinking
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


@dataclass
class OllamaModel:
    base_url: str
    model: str
    timeout: int = 120

    @property
    def name(self) -> str:
        return self.model

    def complete(
        self,
        system: str,
        messages: list[dict[str, str]],
        *,
        thinking: bool = False,
    ) -> str:
        payload = json.dumps(
            {
                "model": self.model,
                "messages": [{"role": "system", "content": system}, *messages],
                "stream": False,
                "think": thinking,
                "options": {"temperature": 0.6},
            }
        ).encode()
        request = urllib.request.Request(
            f"{self.base_url.rstrip('/')}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                data = json.loads(response.read())
            return data["message"]["content"]
        except (urllib.error.URLError, KeyError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Ollama request failed: {exc}") from exc


def model_from_environment() -> Model:
    provider = os.getenv("CULTURE_AGENT_MODEL_PROVIDER", "offline").lower()
    if provider == "ollama":
        base_url = os.getenv("CULTURE_AGENT_MODEL_BASE_URL", "http://localhost:11434")
        if base_url.rstrip("/").endswith("/v1"):
            base_url = base_url.rstrip("/")[:-3]
        return OllamaModel(
            base_url=base_url,
            model=os.getenv("CULTURE_AGENT_MODEL_NAME", "qwen3:8b"),
        )
    if provider in {"openai", "openai-compatible"}:
        return OpenAICompatibleModel(
            base_url=os.getenv("CULTURE_AGENT_MODEL_BASE_URL", "http://localhost:11434/v1"),
            model=os.getenv("CULTURE_AGENT_MODEL_NAME", "qwen3:8b"),
            api_key=os.getenv("CULTURE_AGENT_API_KEY", ""),
        )
    return OfflineModel()

