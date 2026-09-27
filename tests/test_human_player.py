"""Tests for CharacterBox HumanPlayer simulator-call compatibility."""

from datetime import datetime
from unittest import TestCase
from unittest.mock import patch

from agents.human_player import HumanPlayer


class HumanPlayerCompatibilityTests(TestCase):
    def setUp(self):
        self.player = HumanPlayer.construct(gender="Female")
        self.now = datetime(2026, 8, 9, 20, 0, 0)

    def test_preserves_source_gender_as_non_prompt_metadata(self):
        self.assertEqual("Female", self.player.gender)

    def test_dynamic_reaction_accepts_simulator_arguments(self):
        with patch("builtins.input", return_value="Luna steps aside") as input_:
            reaction, detail = self.player.take_reaction(
                "Neville moves toward Luna",
                "",
                self.now,
            )

        input_.assert_called_once_with("Enter your reaction: ")
        self.assertEqual("Luna steps aside", reaction)
        self.assertEqual(
            {"text": "Luna steps aside", "source": "human"},
            detail,
        )

    def test_take_action_accepts_simulator_arguments_and_returns_detail(self):
        with patch("builtins.input", return_value="Luna lowers her wand") as input_:
            action, detail = self.player.take_action(
                "Previous observation",
                "Current Action Reference",
                self.now,
            )

        input_.assert_called_once_with("Enter your action: ")
        self.assertEqual("Luna lowers her wand", action)
        self.assertEqual(
            {"text": "Luna lowers her wand", "source": "human"},
            detail,
        )

    def test_generate_dialogue_accepts_simulator_arguments_and_returns_detail(self):
        with patch("builtins.input", return_value="What did you want to tell me?") as input_:
            dialogue, detail = self.player.generate_dialogue(
                "Luna lowers her wand",
                "Current Action Reference",
                self.now,
            )

        input_.assert_called_once_with("Enter your dialogue: ")
        self.assertEqual("What did you want to tell me?", dialogue)
        self.assertEqual(
            {"text": "What did you want to tell me?", "source": "human"},
            detail,
        )


if __name__ == "__main__":
    import unittest

    unittest.main()
