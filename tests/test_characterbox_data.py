"""Compatibility tests for the copied CharacterBox records and loader."""

import json
import unittest
from pathlib import Path

from dataloader.data import Data


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
HARRY_POTTER_DATA = (
    REPOSITORY_ROOT / "data" / "generated_data" / "Harry_Potter.json"
)


class CharacterBoxDataCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.data = Data(
            {"scene_path": str(HARRY_POTTER_DATA), "scene_id": 0},
            logger=None,
        )

    def test_scene_string_matches_characterbox_format(self):
        expected = (
            "Event: An Unusual Encounter on Privet Drive\n"
            "Time: Early morning and just before midnight\n"
            "Location: Privet Drive and at the corner of Privet Drive\n"
            "Description: An extraordinary sequence of events unfolds on "
            "Privet Drive, where a cat displays human-like behavior and a "
            "mysterious cloaked figure appears out of the blue, causing a "
            "sense of intrigue and unease among the residents."
        )

        self.assertEqual(expected, self.data.init_scene)

    def test_character_string_matches_characterbox_format(self):
        expected_first_character = (
            "Name: Mr. Dursley\n"
            "Position: Driving to work and later in his garden\n"
            "States: Puzzled, inquisitive, and eventually, apprehensive\n"
            "Description: A robust man with a minimal neck and a prominent "
            "mustache, Mr. Dursley is the managing director of Grunnings, a "
            "company that manufactures drills."
        )

        self.assertEqual(expected_first_character, str(self.data.characters[0]))
        self.assertTrue(self.data.init_characters.startswith(expected_first_character))

    def test_loader_preserves_gender_without_changing_character_string(self):
        first_character = self.data.characters[0]

        self.assertEqual("Mr. Dursley", first_character.name)
        self.assertEqual("Male", first_character.gender)
        self.assertNotIn("Gender:", str(first_character))

    def test_actions_keep_original_dictionary_interface(self):
        self.assertEqual(3, len(self.data.init_actions))
        self.assertIsInstance(self.data.init_actions[0], dict)
        self.assertEqual("Mr. Dursley", self.data.init_actions[0]["character"])

    def test_sanitised_development_file_has_50_scenes_and_no_chunks(self):
        with HARRY_POTTER_DATA.open(encoding="utf-8") as file:
            work = json.load(file)

        self.assertEqual(50, len(work["scenes"]))
        self.assertTrue(all("chunk" not in scene for scene in work["scenes"]))


if __name__ == "__main__":
    unittest.main()
