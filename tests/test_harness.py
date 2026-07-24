from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from culture_agent.catalog import CatalogItem
from culture_agent.database import CultureDatabase
from culture_agent.harness import CultureHarness
from culture_agent.model import OfflineModel


class RecordingModel:
    name = "recording-model"

    def __init__(self) -> None:
        self.messages: list[dict[str, str]] = []
        self.thinking = False
        self.system = ""

    def complete(
        self,
        system: str,
        messages: list[dict[str, str]],
        *,
        thinking: bool = False,
    ) -> str:
        self.system = system
        self.messages = messages
        self.thinking = thinking
        return "这里有五部适合你此刻心情的电影。"


class StubCatalog:
    def candidates(
        self,
        message: str,
        kind: str,
        limit: int = 12,
        language: str = "en",
    ) -> list[CatalogItem]:
        del message, limit
        return [
            CatalogItem(
                provider="wikidata",
                provider_id="Q147235",
                title="Legally Blonde",
                kind=kind,
                year=2001,
                creator="Robert Luketic",
                source_url="https://www.wikidata.org/wiki/Q147235",
            )
        ]


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
        self.assertIn("everyday_life", result.created_entry["tags"])
        self.assertIn("slow_paced", result.created_entry["tags"])

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

    def test_unquoted_english_record_is_parsed_and_canonicalized(self) -> None:
        result = self.harness.chat(
            "I watched Arrival, 9/10. I loved its restrained science-fiction atmosphere."
        )
        self.assertEqual(result.intent, "record")
        self.assertEqual(result.created_entry["title"], "Arrival")
        self.assertEqual(result.created_entry["tags"], ["restrained", "science_fiction"])
        self.assertIn("restrained", result.reply)
        self.assertIn("science fiction", result.reply)

    def test_unquoted_english_book_is_detected(self) -> None:
        result = self.harness.chat(
            "I finished reading Invisible Cities, 8.5/10. It felt gentle and dreamlike."
        )
        self.assertEqual(result.created_entry["title"], "Invisible Cities")
        self.assertEqual(result.created_entry["kind"], "book")
        self.assertIn("gentle", result.created_entry["tags"])

    def test_legacy_localized_tags_are_read_as_canonical_ids(self) -> None:
        self.harness.database.add_entry({
            "title": "Legacy",
            "creator": "",
            "kind": "film",
            "status": "finished",
            "rating": 8,
            "reflection": "old record",
            "tags": ["科幻"],
        })
        self.assertEqual(
            self.harness.database.list_entries()[0]["tags"],
            ["science_fiction"],
        )

    def test_english_memory_context_uses_english_tag_labels(self) -> None:
        model = RecordingModel()
        database = CultureDatabase(Path(self.temp_dir.name) / "english-context.db")
        harness = CultureHarness(database, model)
        harness.chat("I watched Arrival, 9/10. Restrained science fiction.")

        harness.chat("Tell me more about why it worked for me.")

        context = model.messages[0]["content"]
        self.assertIn("tags: restrained, science fiction", context)
        self.assertNotIn("标签", context)

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

    def test_thinking_policy_is_task_specific(self) -> None:
        model = RecordingModel()
        database = CultureDatabase(Path(self.temp_dir.name) / "thinking.db")
        harness = CultureHarness(database, model)

        result = harness.chat("请综合分析这些作品之间的共同主题")

        self.assertTrue(result.thinking_used)
        self.assertTrue(model.thinking)

    def test_english_complex_request_enables_thinking(self) -> None:
        model = RecordingModel()
        database = CultureDatabase(Path(self.temp_dir.name) / "thinking-en.db")
        harness = CultureHarness(database, model)
        harness.chat("I watched Arrival, 9/10. Restrained science fiction.")

        result = harness.chat("How has my taste changed over time?")

        self.assertTrue(result.thinking_used)
        self.assertTrue(model.thinking)

    def test_catalog_candidates_ground_recommendation_prompt(self) -> None:
        model = RecordingModel()
        database = CultureDatabase(Path(self.temp_dir.name) / "catalog.db")
        harness = CultureHarness(database, model, StubCatalog())

        result = harness.chat("推荐一部2000年后的轻松喜剧电影")

        self.assertEqual(result.catalog_items[0].provider_id, "Q147235")
        self.assertIn("Q147235", model.system)
        self.assertFalse(model.thinking)

    def test_complex_profile_uses_thinking_with_grounded_memories(self) -> None:
        model = RecordingModel()
        database = CultureDatabase(Path(self.temp_dir.name) / "profile-thinking.db")
        harness = CultureHarness(database, model)
        harness.chat("我看完《花样年华》，9分，喜欢克制的爱情。")

        result = harness.chat("请深入分析我的偏好和其中可能存在的矛盾")

        self.assertEqual(result.intent, "profile")
        self.assertTrue(result.thinking_used)
        self.assertTrue(model.thinking)
        self.assertIn("《花样年华》", model.system)


if __name__ == "__main__":
    unittest.main()

