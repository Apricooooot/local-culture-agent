from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from culture_agent.database import CultureDatabase
from culture_agent.harness import CultureHarness
from culture_agent.model import OfflineModel


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


if __name__ == "__main__":
    unittest.main()

