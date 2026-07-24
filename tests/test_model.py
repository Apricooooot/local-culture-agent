from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from culture_agent.model import OllamaModel


class FakeResponse:
    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps({"message": {"content": "ok"}}).encode()


class OllamaModelTests(unittest.TestCase):
    def test_thinking_flag_is_sent_per_request(self) -> None:
        payloads: list[dict] = []

        def fake_urlopen(request, timeout):
            del timeout
            payloads.append(json.loads(request.data))
            return FakeResponse()

        model = OllamaModel("http://localhost:11434", "qwen3:8b")
        with patch("urllib.request.urlopen", fake_urlopen):
            model.complete("system", [{"role": "user", "content": "simple"}])
            model.complete(
                "system",
                [{"role": "user", "content": "complex"}],
                thinking=True,
            )

        self.assertFalse(payloads[0]["think"])
        self.assertTrue(payloads[1]["think"])


if __name__ == "__main__":
    unittest.main()

