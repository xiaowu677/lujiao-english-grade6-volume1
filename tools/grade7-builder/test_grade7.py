import unittest
from pathlib import Path

from build_grade7 import (
    CORE_COUNTS,
    FULL_COUNTS,
    TEACHING_OVERRIDES,
    build_content,
    build_scenes,
    derive_units,
    load_workbook_rows,
)


WORKBOOK = Path(
    r"E:\【2】学生题库\【13】单词卡\单词闪记5.0"
    r"\知识闪记-鲁教版7年级英语 上册单词表V4-完整版.xlsx"
)


class Grade7DataTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = load_workbook_rows(WORKBOOK)
        cls.units = derive_units(cls.rows)

    def test_full_and_core_counts(self):
        self.assertEqual(len(self.rows), 370)
        self.assertEqual(
            {unit: len(words) for unit, words in self.units.items()},
            FULL_COUNTS,
        )
        self.assertEqual(
            {
                unit: sum(word["core"] for word in words)
                for unit, words in self.units.items()
            },
            CORE_COUNTS,
        )
        self.assertEqual(sum(word["core"] for word in self.rows), 344)

    def test_capitalized_proper_names_are_not_core(self):
        proper = [row for row in self.rows if row["proper"]]
        self.assertEqual(len(proper), 26)
        self.assertTrue(all(not row["core"] for row in proper))
        self.assertEqual(
            {row["en"] for row in proper},
            {
                "Adam",
                "Mid-Autumn Festival",
                "Beth",
                "Nairobi",
                "New York",
                "Kenya",
                "USA",
                "Central Park",
                "Anna",
                "John",
                "Stockholm",
                "Bright Peak",
                "Hans Christian Andersen",
                "Russian",
                "Guest-Greeting Pine",
                "Sea of Clouds",
                "Seattle",
                "Red Square",
                "Alexander Garden",
                "Vincent",
                "Moscow",
                "Russia",
                "the Victory Museum",
                "Nazi",
                "World War II",
                "the Moscow Metro",
            },
        )

    def test_teaching_overrides_match_real_phrase_rows(self):
        actual = {
            row["en"]
            for row in self.rows
            if row["en"] in TEACHING_OVERRIDES
        }
        self.assertEqual(actual, set(TEACHING_OVERRIDES))

    def test_each_unit_has_four_complete_scenes(self):
        for words in self.units.values():
            scenes = build_scenes(words, include_non_core=True)
            self.assertEqual(len(scenes), 4)
            scene_words = [
                word_en
                for scene in scenes
                for word_en in scene["wordEns"]
            ]
            self.assertEqual(len(scene_words), len(words))
            self.assertEqual(set(scene_words), {word["en"] for word in words})
            for scene in scenes:
                normalized_story = scene["story"].lower()
                for word_en in scene["wordEns"]:
                    self.assertIn(word_en.lower(), normalized_story)

    def test_every_word_has_distinct_training_and_acceptance_contexts(self):
        for words in self.units.values():
            content = build_content(words)
            for row in words:
                training, training_zh, acceptance, acceptance_zh = content[row["en"]]
                self.assertEqual(training.count("{{word}}"), 1)
                self.assertEqual(acceptance.count("{{word}}"), 1)
                self.assertNotEqual(training, acceptance)
                self.assertTrue(training_zh.strip())
                self.assertEqual(acceptance_zh.count("{{word}}"), 1)


if __name__ == "__main__":
    unittest.main()
