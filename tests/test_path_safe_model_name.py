"""Tests for utils.utils.path_safe_model_name() (OpenRouter model ids in record filenames)."""

from unittest import TestCase

from utils import utils


class PathSafeModelNameTest(TestCase):
    def test_openai_ids_are_unchanged(self):
        self.assertEqual("gpt-4o-mini", utils.path_safe_model_name("gpt-4o-mini"))

    def test_openrouter_ids_have_no_path_separator(self):
        self.assertEqual(
            "openai-gpt-4o-mini", utils.path_safe_model_name("openai/gpt-4o-mini")
        )


if __name__ == "__main__":
    import unittest

    unittest.main()
