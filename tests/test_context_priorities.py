"""Tests for reusable field-group context-priority policies."""

import copy
import json
import unittest
from pathlib import Path

from dataloader.context_priorities import (
    CHARACTERBOX_CONTEXT_FIELDS,
    PriorityConfigValidationError,
    load_validated_priority_config,
    validate_priority_config,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PRIORITY_CONFIG = REPOSITORY_ROOT / "config" / "context_priorities.json"


class ContextPriorityConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with PRIORITY_CONFIG.open(encoding="utf-8") as file:
            cls.config = json.load(file)

    def test_primary_policy_assigns_all_thirteen_fields_once(self):
        config = load_validated_priority_config(PRIORITY_CONFIG)
        policy = config["policies"][0]
        assigned_fields = [
            field
            for group in policy["priorities"]
            for field in group["fields"]
        ]

        self.assertEqual("primary_four_level", policy["policy_id"])
        self.assertEqual([1, 2, 3, 4], [item["priority"] for item in policy["priorities"]])
        self.assertEqual(13, len(assigned_fields))
        self.assertEqual(CHARACTERBOX_CONTEXT_FIELDS, set(assigned_fields))
        self.assertNotIn("action_reference", policy["priorities"][0]["fields"])
        self.assertIn("action_reference", policy["priorities"][2]["fields"])

    def test_rejects_missing_context_field(self):
        config = copy.deepcopy(self.config)
        config["policies"][0]["priorities"][1]["fields"].remove("event")

        with self.assertRaisesRegex(
            PriorityConfigValidationError,
            "missing context fields: event",
        ):
            validate_priority_config(config)

    def test_rejects_field_assigned_to_two_priorities(self):
        config = copy.deepcopy(self.config)
        config["policies"][0]["priorities"][1]["fields"].append("event")

        with self.assertRaisesRegex(
            PriorityConfigValidationError,
            "fields assigned more than once: event",
        ):
            validate_priority_config(config)

    def test_rejects_unknown_context_field(self):
        config = copy.deepcopy(self.config)
        config["policies"][0]["priorities"][0]["fields"].append("plot")

        with self.assertRaisesRegex(
            PriorityConfigValidationError,
            "unknown context fields: plot",
        ):
            validate_priority_config(config)

    def test_rejects_priority_number_gap(self):
        config = copy.deepcopy(self.config)
        config["policies"][0]["priorities"][3]["priority"] = 7

        with self.assertRaisesRegex(
            PriorityConfigValidationError,
            "priorities must be unique and continuous from 1",
        ):
            validate_priority_config(config)

    def test_rejects_empty_priority_group(self):
        config = copy.deepcopy(self.config)
        config["policies"][0]["priorities"][3]["fields"] = []

        with self.assertRaisesRegex(
            PriorityConfigValidationError,
            "priority 4 fields must be non-empty",
        ):
            validate_priority_config(config)


if __name__ == "__main__":
    unittest.main()
