"""Tests for the English-only CharacterBox Narrator adaptation."""

import re
from datetime import datetime
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from agents.narrator import Narrator
from utils.character import CharacterInfo, SceneInfo


class FakeChain:
    def __init__(self, text):
        self.text = text
        self.inputs = []

    def invoke(self, input):
        self.inputs.append(input)
        return {"text": self.text}


class NarratorEnglishOnlyTests(TestCase):
    def setUp(self):
        self.scene = SceneInfo(
            id=19,
            event="The Secret Meeting",
            time="Late evening",
            location="The Shrieking Shack, Hogwarts",
            description="Wind howls around the isolated building.",
        )
        self.characters = [
            CharacterInfo(
                id=0,
                name="Luna Lovegood",
                gender="Female",
                position="Near the doorway",
                states="Calm and watchful",
                description="An observant and unconventional student.",
            ),
            CharacterInfo(
                id=1,
                name="Neville Longbottom",
                gender="Male",
                position="Inside the room",
                states="Nervous but determined",
                description="A brave and loyal student.",
            ),
        ]
        self.narrator = Narrator.construct(
            id=0,
            name="Narrator",
            scene=self.scene,
            characters=self.characters,
            all_actions=[],
            plots=[],
        )
        self.now = datetime(2026, 8, 9, 20, 0, 0)

    def test_common_reaction_preserves_original_english_prompt(self):
        chain = FakeChain("Neville Longbottom|He steps back.")
        suffix = "Action: {action}\nActor: {actor}\n"

        with patch.object(Narrator, "chain", return_value=chain):
            response = self.narrator._generate_reaction(
                suffix,
                self.now,
                action="Luna lowers her wand.",
                actor="Luna Lovegood",
            )

        expected = (
            "Please act as a screenwriter for a key scene in an art novel that "
            "highlights the characters' unique traits and drives the plot forward\n"
            "Event: The Secret Meeting\n"
            "Time: Late evening\n"
            "Location: The Shrieking Shack, Hogwarts\n"
            "Description: Wind howls around the isolated building.\n"
            f"Characters: {self.characters}\n"
            "There is no one else in the scene other than the above characters.\n"
            "Action: Luna lowers her wand.\n"
            "Actor: Luna Lovegood\n"
        )
        self.assertEqual("Neville Longbottom|He steps back.", response)
        self.assertEqual(expected, self.narrator.all_actions[0]["prompt"])

    def test_update_character_uses_english_parser(self):
        detail = {"text": "fixed"}
        with patch.object(
            Narrator,
            "_generate_reaction",
            return_value=(
                "Position: Beside the window\nState: Alert but composed",
                detail,
            ),
        ) as generate:
            position, state, returned_detail = self.narrator.update_character(
                "Neville Longbottom",
                "Luna enters the room.",
                self.now,
                verbose=True,
            )

        self.assertEqual("Beside the window", position)
        self.assertEqual("Alert but composed", state)
        self.assertIs(detail, returned_detail)
        self.assertIn("Observation: {observation}", generate.call_args.args[0])
        self.assertIn("Position:", generate.call_args.args[0])

    def test_update_scene_uses_english_prompt_and_parser(self):
        chain = FakeChain(
            "- Time: Late evening\n"
            "- Location: The Shrieking Shack, Hogwarts\n"
            "- Description: The open door lets cold wind enter."
        )

        with patch.object(Narrator, "chain", return_value=chain):
            scene, detail = self.narrator.update_scene(
                "Luna opens the door.",
                verbose=True,
            )

        self.assertEqual("Late evening", scene.time)
        self.assertEqual("The Shrieking Shack, Hogwarts", scene.location)
        self.assertEqual("The open door lets cold wind enter.", scene.description)
        rendered_prompt = self.narrator.all_actions[0]["prompt"]
        self.assertIn("Given an initial scene description", rendered_prompt)
        self.assertIn("Observation: Luna opens the door.", rendered_prompt)
        self.assertEqual(chain.text, detail["text"])

    def test_source_contains_no_chinese_text_or_language_branch(self):
        source = (Path(__file__).resolve().parents[1] / "agents" / "narrator.py").read_text(
            encoding="utf-8"
        )

        self.assertNotIn("utils.detect_language", source)
        self.assertIsNone(re.search(r"[\u3400-\u4dbf\u4e00-\u9fff]", source))


if __name__ == "__main__":
    import unittest

    unittest.main()
