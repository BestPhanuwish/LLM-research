"""Load and validate reusable CharacterBox context-priority policies."""

import argparse
import json
from pathlib import Path


CHARACTERBOX_CONTEXT_FIELDS = {
    "event",
    "time",
    "location",
    "description",
    "name",
    "character_description",
    "position",
    "states",
    "self_belief",
    "env_belief",
    "recent_memory",
    "observation",
    "action_reference",
}


class PriorityConfigValidationError(ValueError):
    """Raised when a context-priority policy is incomplete or ambiguous."""


def _require(condition, message):
    if not condition:
        raise PriorityConfigValidationError(message)


def validate_priority_config(config):
    """Validate all decoded priority policies and their field assignments."""
    _require(config.get("schema_version") == 1, "schema_version must be 1")
    policies = config.get("policies")
    _require(
        isinstance(policies, list) and policies,
        "policies must be a non-empty list",
    )

    policy_ids = set()
    for policy in policies:
        policy_id = policy.get("policy_id")
        _require(isinstance(policy_id, str) and policy_id, "policy_id is required")
        _require(policy_id not in policy_ids, f"Duplicate policy_id: {policy_id}")
        policy_ids.add(policy_id)
        if "conflict_rule" in policy:
            _require(
                isinstance(policy["conflict_rule"], str)
                and policy["conflict_rule"].strip(),
                f"{policy_id}: conflict_rule must be a non-empty string",
            )
        priorities = policy.get("priorities")
        _require(
            isinstance(priorities, list) and priorities,
            f"{policy_id}: priorities must be a non-empty list",
        )

        numbers = []
        assigned_fields = []
        for group in priorities:
            number = group.get("priority")
            _require(
                isinstance(number, int) and not isinstance(number, bool) and number > 0,
                f"{policy_id}: priorities must be positive integers",
            )
            numbers.append(number)
            _require(
                isinstance(group.get("name"), str) and group["name"].strip(),
                f"{policy_id}: priority {number} requires a name",
            )
            _require(
                isinstance(group.get("instruction"), str)
                and group["instruction"].strip(),
                f"{policy_id}: priority {number} requires an instruction",
            )
            fields = group.get("fields")
            _require(
                isinstance(fields, list) and fields,
                f"{policy_id}: priority {number} fields must be non-empty",
            )
            _require(
                all(isinstance(field, str) for field in fields),
                f"{policy_id}: priority {number} fields must be strings",
            )
            assigned_fields.extend(fields)

        expected_numbers = list(range(1, len(priorities) + 1))
        _require(
            sorted(numbers) == expected_numbers and len(numbers) == len(set(numbers)),
            f"{policy_id}: priorities must be unique and continuous from 1",
        )
        duplicates = {
            field for field in assigned_fields if assigned_fields.count(field) > 1
        }
        _require(
            not duplicates,
            f"{policy_id}: fields assigned more than once: "
            + ", ".join(sorted(duplicates)),
        )
        unknown = set(assigned_fields) - CHARACTERBOX_CONTEXT_FIELDS
        _require(
            not unknown,
            f"{policy_id}: unknown context fields: " + ", ".join(sorted(unknown)),
        )
        missing = CHARACTERBOX_CONTEXT_FIELDS - set(assigned_fields)
        _require(
            not missing,
            f"{policy_id}: missing context fields: " + ", ".join(sorted(missing)),
        )

    return config


def load_validated_priority_config(config_path):
    """Load and validate a context-priority configuration file."""
    with Path(config_path).open(encoding="utf-8") as file:
        config = json.load(file)
    return validate_priority_config(config)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    args = parser.parse_args()
    config = load_validated_priority_config(args.config)
    print(f"Validated {len(config['policies'])} priority policy/policies.")
    for policy in config["policies"]:
        print(f"{policy['policy_id']}: {len(policy['priorities'])} levels")
        for group in sorted(
            policy["priorities"], key=lambda item: item["priority"]
        ):
            print(
                f"  Priority {group['priority']} — {group['name']}: "
                + ", ".join(group["fields"])
            )
            print(f"    {group['instruction']}")


if __name__ == "__main__":
    main()
