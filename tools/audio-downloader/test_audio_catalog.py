import unittest
from collections import Counter
from pathlib import Path

from audio_catalog import build_catalog


REPO_ROOT = Path(__file__).resolve().parents[2]


class AudioCatalogTest(unittest.TestCase):
    def test_catalog_contains_every_unique_word_and_sentence(self):
        items = build_catalog(REPO_ROOT, course="grade6")

        self.assertEqual(len(items), 968)
        self.assertEqual(
            Counter(item["kind"] for item in items),
            {
                "word": 299,
                "training": 299,
                "acceptance": 298,
                "story": 72,
            },
        )
        self.assertEqual(len({item["id"] for item in items}), len(items))
        self.assertTrue(all(item["text"].strip() for item in items))

    def test_ids_are_safe_stable_filenames(self):
        items = build_catalog(REPO_ROOT, course="grade6")

        for item in items:
            self.assertRegex(item["id"], r"^[a-z]+-[0-9a-f]{16}$")
            self.assertNotIn("/", item["filename"])
            self.assertNotIn("\\", item["filename"])
            self.assertTrue(item["filename"].endswith(".mp3"))

    def test_grade7_catalog_is_separate_from_grade6(self):
        grade6 = build_catalog(REPO_ROOT, course="grade6")
        grade7 = build_catalog(REPO_ROOT, course="grade7")

        self.assertEqual(len(grade6), 968)
        self.assertEqual(len(grade7), 1138)
        self.assertEqual(
            Counter(item["kind"] for item in grade7),
            {
                "word": 370,
                "training": 370,
                "acceptance": 370,
                "story": 28,
            },
        )
        self.assertTrue(all(item["course"] == "grade7" for item in grade7))


if __name__ == "__main__":
    unittest.main()
