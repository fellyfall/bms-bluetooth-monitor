import json
import unittest
from pathlib import Path

from config import load_languages


class LocaleFileTests(unittest.TestCase):
    def test_registered_translation_files_match_english_keys(self):
        locale_dir = Path(__file__).parents[1] / "locales"
        languages = load_languages()
        english = json.loads((locale_dir / "en.json").read_text(encoding="utf-8"))

        for code in languages:
            with self.subTest(language=code):
                translations = json.loads(
                    (locale_dir / f"{code}.json").read_text(encoding="utf-8")
                )
                self.assertEqual(set(translations), set(english))
                self.assertTrue(
                    all(
                        isinstance(value, str) and value
                        for value in translations.values()
                    )
                )


if __name__ == "__main__":
    unittest.main()
