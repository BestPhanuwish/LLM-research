"""Tests for pilot manifests and pilot run-configs kept separate from
CharacterBox data."""

import copy
import json
import unittest
from pathlib import Path

from dataloader.data import Data
from dataloader.research_sidecar import (
    SidecarValidationError,
    load_validated_sidecar,
    validate_pilot_config,
    validate_sidecar,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
HARRY_POTTER_DATA = (
    REPOSITORY_ROOT / "data" / "generated_data" / "Harry_Potter.json"
)
PILOT_SIDECAR = (
    REPOSITORY_ROOT
    / "data"
    / "research_annotations"
    / "characterbox_pilot.json"
)
PILOT_CONFIG = REPOSITORY_ROOT / "config" / "pilot_run_config.json"


class ResearchSidecarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with HARRY_POTTER_DATA.open(encoding="utf-8") as file:
            cls.dataset = json.load(file)
        with PILOT_SIDECAR.open(encoding="utf-8") as file:
            cls.sidecar = json.load(file)
        with PILOT_CONFIG.open(encoding="utf-8") as file:
            cls.pilot_config = json.load(file)

    def test_pilot_selects_values_from_unchanged_characterbox_data(self):
        pilot = load_validated_sidecar(PILOT_SIDECAR)
        data = Data(
            {
                "scene_path": str(HARRY_POTTER_DATA),
                "scene_id": pilot["scene_id"],
            },
            logger=None,
        )

        self.assertEqual("cb_hp_019_luna_neville", pilot["pilot_id"])
        self.assertEqual("Luna Lovegood", data.characters[0].name)
        self.assertEqual("Neville Longbottom", data.characters[1].name)
        self.assertEqual(0, pilot["player_character_id"])
        self.assertEqual(1, pilot["target_character_id"])
        self.assertEqual(1, pilot["action_id"])
        self.assertEqual(4, pilot["schema_version"])
        self.assertEqual(11, len(pilot["trials"]))
        trial = pilot["trials"][0]
        self.assertEqual("cb_hp_019_luna_neville_t01", trial["trial_id"])
        self.assertEqual(1, len(trial["turns"]))
        self.assertNotIn("player_action", trial["turns"][0])
        selected_action = next(
            action
            for action in data.init_actions
            if action["action_id"] == pilot["action_id"]
        )
        self.assertEqual(
            "Neville whispers to Luna, reminding her to keep her voice down "
            "so as not to attract unwanted attention.",
            selected_action["action"],
        )
        self.assertNotIn("facts", pilot)
        self.assertNotIn("evaluation_cases", pilot)
        self.assertNotIn("recent_memory_action_ids", pilot)

    def test_rejects_legacy_copied_world_data(self):
        sidecar = copy.deepcopy(self.sidecar)
        sidecar["facts"] = [{"value": "Invented event"}]

        with self.assertRaisesRegex(
            SidecarValidationError,
            "unsupported pilot fields: facts",
        ):
            validate_sidecar(sidecar, self.dataset)

    def test_rejects_evaluation_cases_field(self):
        sidecar = copy.deepcopy(self.sidecar)
        sidecar["evaluation_cases"] = []

        with self.assertRaisesRegex(
            SidecarValidationError,
            "unsupported pilot fields: evaluation_cases",
        ):
            validate_sidecar(sidecar, self.dataset)

    def test_rejects_recent_memory_action_ids_field(self):
        sidecar = copy.deepcopy(self.sidecar)
        sidecar["recent_memory_action_ids"] = [0]

        with self.assertRaisesRegex(
            SidecarValidationError,
            "unsupported pilot fields: recent_memory_action_ids",
        ):
            validate_sidecar(sidecar, self.dataset)

    def test_pilot_trials_carry_a_category_note(self):
        pilot = load_validated_sidecar(PILOT_SIDECAR)

        for trial in pilot["trials"]:
            self.assertIn("note", trial)
            self.assertIn("Category:", trial["note"])

    def test_accepts_trial_without_a_note(self):
        sidecar = copy.deepcopy(self.sidecar)
        del sidecar["trials"][0]["note"]

        validate_sidecar(sidecar, self.dataset)

    def test_accepts_and_rejects_trial_types(self):
        sidecar = copy.deepcopy(self.sidecar)
        sidecar["trials"][0]["type"] = 2
        validate_sidecar(sidecar, self.dataset)

        for bad_type in (0, 4, "1", True):
            sidecar["trials"][0]["type"] = bad_type
            with self.assertRaisesRegex(
                SidecarValidationError,
                r"type must be one of \[1, 2, 3\]",
            ):
                validate_sidecar(sidecar, self.dataset)

    def test_rejects_blank_note(self):
        sidecar = copy.deepcopy(self.sidecar)
        sidecar["trials"][0]["note"] = "   "

        with self.assertRaisesRegex(
            SidecarValidationError,
            "note must be a non-empty string",
        ):
            validate_sidecar(sidecar, self.dataset)

    def test_rejects_non_string_note(self):
        sidecar = copy.deepcopy(self.sidecar)
        sidecar["trials"][0]["note"] = ["not", "a", "string"]

        with self.assertRaisesRegex(
            SidecarValidationError,
            "note must be a non-empty string",
        ):
            validate_sidecar(sidecar, self.dataset)

    def test_rejects_action_from_another_character(self):
        sidecar = copy.deepcopy(self.sidecar)
        sidecar["action_id"] = 0

        with self.assertRaisesRegex(
            SidecarValidationError,
            "action does not belong to target character",
        ):
            validate_sidecar(sidecar, self.dataset)

    def test_rejects_missing_player_character(self):
        sidecar = copy.deepcopy(self.sidecar)
        sidecar["player_character_id"] = 999

        with self.assertRaisesRegex(
            SidecarValidationError,
            "player_character_id 999 must identify one character",
        ):
            validate_sidecar(sidecar, self.dataset)

    def test_rejects_player_and_target_being_same_character(self):
        sidecar = copy.deepcopy(self.sidecar)
        sidecar["player_character_id"] = 1

        with self.assertRaisesRegex(
            SidecarValidationError,
            "player and target characters must be different",
        ):
            validate_sidecar(sidecar, self.dataset)

    def test_rejects_non_sequential_turn_rounds(self):
        sidecar = copy.deepcopy(self.sidecar)
        sidecar["trials"][0]["turns"][0]["round"] = 2

        with self.assertRaisesRegex(
            SidecarValidationError,
            "turn rounds must be sequential from 1",
        ):
            validate_sidecar(sidecar, self.dataset)

    def test_rejects_blank_player_dialogue(self):
        sidecar = copy.deepcopy(self.sidecar)
        sidecar["trials"][0]["turns"][0]["player_dialogue"] = "  "

        with self.assertRaisesRegex(
            SidecarValidationError,
            "requires non-empty player dialogue",
        ):
            validate_sidecar(sidecar, self.dataset)

    def test_rejects_player_action_in_dialogue_only_turn(self):
        sidecar = copy.deepcopy(self.sidecar)
        sidecar["trials"][0]["turns"][0]["player_action"] = "Luna lowers her wand."

        with self.assertRaisesRegex(
            SidecarValidationError,
            "unsupported fields: player_action",
        ):
            validate_sidecar(sidecar, self.dataset)

    def test_rejects_empty_trials_list(self):
        sidecar = copy.deepcopy(self.sidecar)
        sidecar["trials"] = []

        with self.assertRaisesRegex(
            SidecarValidationError,
            "trials must be a non-empty list",
        ):
            validate_sidecar(sidecar, self.dataset)

    def test_rejects_duplicate_trial_ids(self):
        sidecar = copy.deepcopy(self.sidecar)
        sidecar["trials"].append(copy.deepcopy(sidecar["trials"][0]))

        with self.assertRaisesRegex(
            SidecarValidationError,
            "duplicate trial_id",
        ):
            validate_sidecar(sidecar, self.dataset)

    def test_accepts_multiple_independent_trials_sharing_pilot_identity(self):
        sidecar = copy.deepcopy(self.sidecar)
        first_trial = copy.deepcopy(sidecar["trials"][0])
        second_trial = copy.deepcopy(sidecar["trials"][0])
        second_trial["trial_id"] = "cb_hp_019_luna_neville_synthetic_t99"
        second_trial["turns"][0]["player_dialogue"] = "Did anyone follow you here?"
        sidecar["trials"] = [first_trial, second_trial]

        validated = validate_sidecar(sidecar, self.dataset)

        self.assertEqual(2, len(validated["trials"]))
        self.assertEqual(
            [first_trial["trial_id"], "cb_hp_019_luna_neville_synthetic_t99"],
            [trial["trial_id"] for trial in validated["trials"]],
        )

    def test_pilot_config_accepts_default_run_config(self):
        validated = validate_pilot_config(copy.deepcopy(self.pilot_config))

        self.assertEqual(["U", "S", "P"], validated["conditions"])
        self.assertEqual("primary_five_level", validated["priority_policy_id"])

    def test_pilot_config_rejects_duplicate_conditions(self):
        config = copy.deepcopy(self.pilot_config)
        config["conditions"] = ["S", "S"]

        with self.assertRaisesRegex(
            SidecarValidationError,
            "conditions must be unique",
        ):
            validate_pilot_config(config)

    def test_pilot_config_requires_priority_policy_id_for_p(self):
        config = copy.deepcopy(self.pilot_config)
        del config["priority_policy_id"]

        with self.assertRaisesRegex(
            SidecarValidationError,
            "priority_policy_id is required when conditions include P",
        ):
            validate_pilot_config(config)

    def test_pilot_config_rejects_unknown_fields(self):
        config = copy.deepcopy(self.pilot_config)
        config["extra"] = True

        with self.assertRaisesRegex(
            SidecarValidationError,
            "unsupported pilot config fields: extra",
        ):
            validate_pilot_config(config)


if __name__ == "__main__":
    unittest.main()
