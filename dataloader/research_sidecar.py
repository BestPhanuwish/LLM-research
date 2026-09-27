"""Load and validate research trial selectors kept outside CharacterBox data."""

import argparse
import json
from pathlib import Path


ALLOWED_DATASET_SOURCES = {"characterbox_generated", "original_story"}
ALLOWED_MANIFEST_FIELDS = {
    "schema_version",
    "dataset_source",
    "source_dataset",
    "pilot_id",
    "scene_id",
    "player_character_id",
    "target_character_id",
    "action_id",
    "trials",
}
ALLOWED_TRIAL_FIELDS = {"trial_id", "turns", "note"}
ALLOWED_TURN_FIELDS = {"round", "player_dialogue"}
ALLOWED_PILOT_CONFIG_FIELDS = {"schema_version", "conditions", "priority_policy_id"}


class SidecarValidationError(ValueError):
    """Raised when a pilot manifest or pilot run-config violates its contract."""


def _require(condition, message):
    if not condition:
        raise SidecarValidationError(message)


def _matches_by_id(items, key, value):
    return [item for item in items if item.get(key) == value]


def validate_sidecar(sidecar, dataset):
    """Validate one schema-v4 pilot manifest: scene/character identity shared
    by every trial, plus an ordered list of independent dialogue-only trials."""
    _require(sidecar.get("schema_version") == 4, "schema_version must be 4")
    unexpected_fields = set(sidecar) - ALLOWED_MANIFEST_FIELDS
    _require(
        not unexpected_fields,
        "unsupported pilot fields: " + ", ".join(sorted(unexpected_fields)),
    )
    _require(
        sidecar.get("dataset_source") in ALLOWED_DATASET_SOURCES,
        "dataset_source must be characterbox_generated or original_story",
    )
    scenes = dataset.get("scenes")
    _require(isinstance(scenes, list), "source dataset must contain a scenes list")

    pilot_id = sidecar.get("pilot_id")
    _require(isinstance(pilot_id, str) and pilot_id, "pilot_id is required")

    scene_id = sidecar.get("scene_id")
    matching_scenes = [
        (index, scene)
        for index, scene in enumerate(scenes)
        if scene.get("id") == scene_id
    ]
    _require(
        len(matching_scenes) == 1,
        f"{pilot_id}: scene_id {scene_id!r} must identify one scene",
    )
    _, scene = matching_scenes[0]

    characters = scene.get("characters", [])
    player_character_id = sidecar.get("player_character_id")
    _require(
        len(_matches_by_id(characters, "id", player_character_id)) == 1,
        f"{pilot_id}: player_character_id {player_character_id!r} "
        "must identify one character",
    )
    target_character_id = sidecar.get("target_character_id")
    _require(
        len(_matches_by_id(characters, "id", target_character_id)) == 1,
        f"{pilot_id}: target_character_id {target_character_id!r} "
        "must identify one character",
    )
    _require(
        player_character_id != target_character_id,
        f"{pilot_id}: player and target characters must be different",
    )

    # Action Reference is scene/target-NPC truth, not a per-trial choice: every
    # trial in a pilot shares the same target NPC in the same scene, so there is
    # exactly one canonical Action Reference for the whole pilot.
    actions = scene.get("actions", [])
    action_id = sidecar.get("action_id")
    matching_actions = _matches_by_id(actions, "action_id", action_id)
    _require(
        len(matching_actions) == 1,
        f"{pilot_id}: action_id {action_id!r} must identify one action",
    )
    _require(
        matching_actions[0].get("character_id") == target_character_id,
        f"{pilot_id}: action does not belong to target character",
    )

    trials = sidecar.get("trials")
    _require(isinstance(trials, list) and trials, f"{pilot_id}: trials must be a non-empty list")
    trial_ids = set()
    for trial in trials:
        _require(isinstance(trial, dict), f"{pilot_id}: each trial must be an object")
        unexpected_trial_fields = set(trial) - ALLOWED_TRIAL_FIELDS
        _require(
            not unexpected_trial_fields,
            f"{pilot_id}: unsupported trial fields: "
            + ", ".join(sorted(unexpected_trial_fields)),
        )
        trial_id = trial.get("trial_id")
        _require(isinstance(trial_id, str) and trial_id, f"{pilot_id}: trial_id is required")
        _require(trial_id not in trial_ids, f"{pilot_id}: duplicate trial_id {trial_id!r}")
        trial_ids.add(trial_id)

        if "note" in trial:
            note = trial.get("note")
            _require(
                isinstance(note, str) and note.strip(),
                f"{trial_id}: note must be a non-empty string when present",
            )

        turns = trial.get("turns")
        _require(isinstance(turns, list) and turns, f"{trial_id}: turns must be non-empty")
        for index, turn in enumerate(turns, start=1):
            _require(isinstance(turn, dict), f"{trial_id}: turn {index} must be an object")
            unexpected_turn_fields = set(turn) - ALLOWED_TURN_FIELDS
            _require(
                not unexpected_turn_fields,
                f"{trial_id}: turn {index} has unsupported fields: "
                + ", ".join(sorted(unexpected_turn_fields)),
            )
            _require(
                turn.get("round") == index,
                f"{trial_id}: turn rounds must be sequential from 1",
            )
            dialogue = turn.get("player_dialogue")
            _require(isinstance(dialogue, str), f"{trial_id}: turn {index} player_dialogue must be a string")
            _require(
                dialogue.strip(),
                f"{trial_id}: turn {index} requires non-empty player dialogue",
            )

    return sidecar


def validate_pilot_config(config):
    """Validate one reusable pilot run-config: which conditions to run and,
    when P is included, which frozen priority policy to use."""
    _require(config.get("schema_version") == 1, "schema_version must be 1")
    unexpected_fields = set(config) - ALLOWED_PILOT_CONFIG_FIELDS
    _require(
        not unexpected_fields,
        "unsupported pilot config fields: " + ", ".join(sorted(unexpected_fields)),
    )
    conditions = config.get("conditions")
    _require(isinstance(conditions, list) and conditions, "conditions must be a non-empty list")
    _require(
        all(condition in {"U", "S", "P"} for condition in conditions),
        "conditions may contain only U, S, and P",
    )
    _require(len(conditions) == len(set(conditions)), "conditions must be unique")
    if "P" in conditions:
        _require(
            isinstance(config.get("priority_policy_id"), str)
            and config["priority_policy_id"].strip(),
            "priority_policy_id is required when conditions include P",
        )
    return config


def load_validated_pilot_config(config_path):
    """Load and validate a reusable pilot run-config JSON file."""
    with Path(config_path).open(encoding="utf-8") as file:
        config = json.load(file)
    return validate_pilot_config(config)


def _load_sidecar_and_dataset(sidecar_path):
    sidecar_path = Path(sidecar_path).resolve()
    with sidecar_path.open(encoding="utf-8") as file:
        sidecar = json.load(file)
    source_dataset = sidecar.get("source_dataset")
    _require(
        isinstance(source_dataset, str) and source_dataset,
        "source_dataset is required",
    )
    dataset_path = (sidecar_path.parent / source_dataset).resolve()
    _require(dataset_path.is_file(), f"Source dataset not found: {dataset_path}")
    with dataset_path.open(encoding="utf-8") as file:
        dataset = json.load(file)
    return sidecar, dataset


def load_validated_sidecar(sidecar_path):
    """Load a pilot manifest and its relative source dataset, then validate both."""
    sidecar, dataset = _load_sidecar_and_dataset(sidecar_path)
    return validate_sidecar(sidecar, dataset)


def resolve_source_dataset_path(sidecar_path, sidecar=None):
    """Resolve the manifest's dataset path without copying source values."""
    sidecar_path = Path(sidecar_path).resolve()
    if sidecar is None:
        with sidecar_path.open(encoding="utf-8") as file:
            sidecar = json.load(file)
    return (sidecar_path.parent / sidecar["source_dataset"]).resolve()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sidecar", type=Path)
    parser.add_argument(
        "--pilot-config",
        type=Path,
        help="Optional pilot run-config (conditions/priority_policy_id) to also inspect",
    )
    args = parser.parse_args()
    sidecar, dataset = _load_sidecar_and_dataset(args.sidecar)
    validate_sidecar(sidecar, dataset)
    print(f"Validated pilot {sidecar['pilot_id']} from {sidecar['dataset_source']}.")
    scenes = dataset["scenes"]
    scene = _matches_by_id(scenes, "id", sidecar["scene_id"])[0]
    player = _matches_by_id(scene["characters"], "id", sidecar["player_character_id"])[0]
    target = _matches_by_id(scene["characters"], "id", sidecar["target_character_id"])[0]
    action = _matches_by_id(scene["actions"], "action_id", sidecar["action_id"])[0]
    print(f"  Scene: {sidecar['scene_id']} ({scene['event']})")
    print(f"  Player character: {sidecar['player_character_id']} ({player['name']})")
    print(f"  Target character: {sidecar['target_character_id']} ({target['name']})")
    print(f"  Action reference: {action['action']}")
    for trial in sidecar["trials"]:
        print(f"  Trial {trial['trial_id']}:")
        if trial.get("note"):
            print(f"    Note: {trial['note']}")
        for turn in trial["turns"]:
            print(f"    Round {turn['round']} dialogue: {turn['player_dialogue']}")
    if args.pilot_config:
        run_config = load_validated_pilot_config(args.pilot_config)
        print(f"  Conditions: {', '.join(run_config['conditions'])}")
        if run_config.get("priority_policy_id"):
            print(f"  Priority policy: {run_config['priority_policy_id']}")


if __name__ == "__main__":
    main()
