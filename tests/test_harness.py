from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from culture_agent.database import CultureDatabase
from culture_agent.harness import CultureHarness
from culture_agent.model import OfflineModel


class RecordingModel:
    name = "recording-model"

    def __init__(self) -> None:
        self.messages: list[dict[str, str]] = []

    def complete(self, system: str, messages: list[dict[str, str]]) -> str:
        del system
        self.messages = messages
        return "这里有五部适合你此刻心情的电影。"


class HarnessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        database = CultureDatabase(Path(self.temp_dir.name) / "test.db")
        self.harness = CultureHarness(database, OfflineModel())

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_natural_language_record(self) -> None:
        result = self.harness.chat(
            "我看完《一一》，9分。很喜欢它从日常小事里观察人生，但有些段落略长。"
        )
        self.assertEqual(result.intent, "record")
        self.assertIsNotNone(result.created_entry)
        self.assertEqual(result.created_entry["title"], "一一")
        self.assertEqual(result.created_entry["kind"], "film")
        self.assertEqual(result.created_entry["rating"], 9)
        self.assertIn("人生观察", result.created_entry["tags"])
        self.assertIn("慢节奏", result.created_entry["tags"])

    def test_book_detection_and_creator(self) -> None:
        result = self.harness.chat(
            "记录一本书：卡尔维诺的《看不见的城市》，8.5分，像在读很多关于城市的梦。"
        )
        self.assertEqual(result.created_entry["kind"], "book")
        self.assertEqual(result.created_entry["creator"], "卡尔维诺")
        self.assertEqual(result.created_entry["rating"], 8.5)

    def test_invalid_rating_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.harness.chat("我看完《测试电影》，12分。")

    def test_profile_is_grounded_in_records(self) -> None:
        self.harness.chat("我看完《花样年华》，9分，喜欢克制的爱情。")
        result = self.harness.chat("我喜欢什么？为什么觉得？")
        self.assertEqual(result.intent, "profile")
        self.assertIn("《花样年华》", result.reply)
        self.assertIn("克制", result.reply)

    def test_manual_entry_validation(self) -> None:
        with self.assertRaises(ValueError):
            self.harness.add_entry({"title": "", "kind": "film"})
        with self.assertRaises(ValueError):
            self.harness.add_entry({"title": "A", "kind": "podcast"})

    def test_english_record_uses_english_reply(self) -> None:
        result = self.harness.chat(
            "I watched 《Arrival》, 9/10. I loved its quiet approach to language and grief."
        )
        self.assertEqual(result.intent, "record")
        self.assertEqual(result.created_entry["title"], "Arrival")
        self.assertEqual(result.created_entry["kind"], "film")
        self.assertIn("Saved locally", result.reply)

    def test_language_can_switch_per_turn(self) -> None:
        english = self.harness.chat("What do I seem to like?")
        chinese = self.harness.chat("我喜欢什么？为什么觉得？")
        self.assertIn("not enough", english.reply.lower())
        self.assertIn("没有足够", chinese.reply)

    def test_recommendation_uses_model_even_without_memories(self) -> None:
        model = RecordingModel()
        database = CultureDatabase(Path(self.temp_dir.name) / "recommend.db")
        harness = CultureHarness(database, model)

        result = harness.chat("今天很累，推荐五部轻松好笑的小妞电影")

        self.assertEqual(result.intent, "recommend")
        self.assertEqual(result.reply, "这里有五部适合你此刻心情的电影。")
        self.assertEqual(model.messages[-1]["content"], "今天很累，推荐五部轻松好笑的小妞电影")

    def test_recommendation_receives_recent_conversation(self) -> None:
        model = RecordingModel()
        database = CultureDatabase(Path(self.temp_dir.name) / "follow-up.db")
        harness = CultureHarness(database, model)
        history = [
            {"role": "user", "content": "推荐一些轻松好笑的小妞电影"},
            {"role": "assistant", "content": "可以看看《伴娘》和《律政俏佳人》。"},
        ]

        result = harness.chat("不想看太老的，2000年以前的不想看", history)

        self.assertEqual(result.intent, "recommend")
        self.assertEqual(model.messages[-3:-1], history)
        self.assertEqual(model.messages[-1]["content"], "不想看太老的，2000年以前的不想看")

    def test_model_echo_is_removed(self) -> None:
        message = "今天很累，推荐一部轻松的电影"
        reply = f"{message}\n\n{message}\n\n可以看看《律政俏佳人》。"

        self.assertEqual(
            CultureHarness._clean_model_reply(reply, message),
            "可以看看《律政俏佳人》。",
        )


if __name__ == "__main__":
    unittest.main()

