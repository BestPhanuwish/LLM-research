"""Build a blind human-labelling sheet for one pilot's re-run trajectories.

One CSV row per NPC turn, with empty label columns for the three H1 metrics.
No judge output is included, and the U/S/P condition is replaced by a version
letter (A/B/C) shuffled per trial, so the rater cannot tell which condition
produced a reply. The letter-to-condition key is written to a separate file.
A companion Markdown file lists the supplied facts and the labelling rules.

Usage:
    python tools/make_label_sheet.py <trajectory.jsonl> <pilot manifest.json> <out dir>
"""

from __future__ import annotations

import csv
import json
import random
import re
import sys
from pathlib import Path

CONDITION_ORDER = ("U", "S", "P")
VERSIONS = ("A", "B", "C")
LABEL_COLUMNS = ("context_use", "world_consistency", "no_contradiction")

# t11 items per pilot (see docs/trial-design-guide.md, worked examples).
T11_ITEMS = {
    "cb_hp_019_luna_neville": {
        "F1": "Harry meets them at the Hog's Head at midnight",
        "F2": "the signal is three taps on the window",
        "C1": "how Neville got out / a detail of his own recent past",
    },
    "cb_hp_012_newt_mcgonagall": {
        "F1": "Madam Oakhollow collects the Niffler at four o'clock",
        "F2": "the Niffler took six gold coins from the Ravenclaw table",
        "C1": "the spell she names to calm the Niffler",
    },
    "cb_hp_031_dumbledore_harry": {
        "F1": "Madam Thistlewood escorts Harry home at nine o'clock tonight",
        "F2": "the owl waits in the third cage from the left in the Ministry owlery",
        "C1": "the dish Harry ate for supper",
    },
    "cb_hp_044_harry_hagrid": {
        "F1": "Professor Wilderberry brings the remedy on Thursday at four o'clock",
        "F2": "the remedy goes in the blue jar on the top shelf",
        "C1": "the ingredients Hagrid put in the rock cakes",
    },
    "cb_hp_032_harry_seamus": {
        "F1": "Professor Merriweather wants to see them at eight o'clock tomorrow morning",
        "F2": "the office password is \"Silver Kettle\"",
        "C1": "the Prophet's exact headline",
    },
}


def single_turn_guide(note: str) -> str:
    """Pull the target and expected-answer sentences out of a trial note."""
    if note.startswith("Category: open-ended"):
        return ("Open-ended. Context Use: PASS if the reply draws on the context, "
                "FAIL if generic. World Consistency: check any factual claims.")
    keep = [
        sentence.strip()
        for sentence in re.split(r"(?<=\.)\s+", note)
        if re.match(r"(Target field|expected answer|Neutral question|Contradicts)", sentence.strip())
    ]
    return " ".join(keep)


def t11_guide(round_number: int, items: dict, location: str) -> str:
    guides = {
        1: f"Establish F1 ({items['F1']}). Context Use: PASS if the reply engages with it or the context, FAIL if generic.",
        2: f"Establish F2 ({items['F2']}). Same rule as R1.",
        3: f"C1: the NPC makes up {items['C1']}. Context Use: PASS for a specific answer.",
        4: f"Recall F1: {items['F1']}.",
        5: f"Control: the supplied location ({location}).",
        6: ("Misquote of the NPC's own R3 answer in this same version. Expected: rejects it and "
            "restates C1. Write EXCLUDE in all three columns if this version's R3 gave no specific answer."),
        7: f"Recall F1: {items['F1']}.",
        8: f"Misquote of F2. Expected: rejects it and restates {items['F2']}. Agreeing = No Contradiction FAIL.",
        9: f"Rethink: expected the original F2 ({items['F2']}), not the R8 misquote.",
        10: f"Recall F1: {items['F1']}.",
    }
    return guides[round_number]


def context_markdown(record: dict, pilot_id: str) -> str:
    scene, target, player = record["scene"], record["target"], record["player"]
    lines = [
        f"# Labelling context: {pilot_id}",
        "",
        "## Supplied facts (what World Consistency and Context Use are checked against)",
        "",
        f"- **Event:** {scene['event']}",
        f"- **Time:** {scene['time']}",
        f"- **Location:** {scene['location']}",
        f"- **Description:** {scene['description']}",
        f"- **Opening action:** {record['action_reference']}",
        "",
        f"**NPC: {target['name']}**",
        "",
        f"- Description: {target['description']}",
        f"- Position: {target['position']}",
        f"- State: {target['states']}",
        "",
        f"**Player: {player['name']}**",
        "",
        f"- Description: {player['description']}",
        f"- Position: {player['position']}",
        f"- State: {player['states']}",
        "",
        "## Labels",
        "",
        "Write PASS, FAIL or NA in each of the three columns (EXCLUDE only for t11 R6, "
        "see below). Use `note` for anything uncertain.",
        "",
        "- **Context Use:** does the reply correctly use the supplied or conversation fact the line asks "
        "about? A partial answer (one asked-for fact right, none wrong) is PASS. A dodge "
        "(\"I'm right here\", \"I don't care\") is FAIL, whatever the mood. At a position question, naming "
        "only the room is FAIL. Open-ended turns and t11 R1-R2: PASS if the reply draws on the context, "
        "FAIL if generic. t11 R3: PASS for a specific answer.",
        "- **World Consistency:** does any claim in the reply conflict with a supplied fact? Agreeing with "
        "the player's false claim counts as making that claim. NA if the reply makes no checkable claim. "
        "Only a clear conflict fails: a vague or unclear claim (\"just outside the main room\") is a Context "
        "Use problem, not a World Consistency one.",
        "- **Judge against the supplied facts only,** never against what you know (or don't know) about the "
        "Harry Potter books.",
        "- **Be consistent on borderline replies:** a concession such as \"Yeah, I know, but…\" or a hedged "
        "correction (\"it might be hidden\") gets the same label every time it appears.",
        "- **No Contradiction:** does the reply contradict the NPC's own earlier turns or a fact the player "
        "established earlier in this conversation? Round 1 is always NA (prefilled). Accepting a misquote "
        "of the NPC's own words is FAIL, even as an in-character \"you caught me\". Brushing a misquote off "
        "without agreeing is not a contradiction. Giving the right answer when prompted after a vague one "
        "(\"Oh, I remember now\") is not a contradiction.",
        "- **t11 R6:** valid only if this version's R3 gave a specific answer; otherwise write EXCLUDE.",
        "",
        "Versions A/B/C are the three context conditions, shuffled per trial. Do not open the key file "
        "until labelling is finished.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    trajectory_path, manifest_path, out_dir = (Path(arg) for arg in sys.argv[1:4])
    records = [json.loads(line) for line in trajectory_path.open(encoding="utf-8") if line.strip()]
    run_ids = {record["generation_run_id"] for record in records}
    if len(run_ids) != 1:
        raise SystemExit(f"Expected one generation run, found {sorted(run_ids)}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    notes = {trial["trial_id"]: trial.get("note", "") for trial in manifest["trials"]}
    pilot_id = manifest["pilot_id"]
    items = T11_ITEMS[pilot_id]

    by_trial: dict[str, dict[str, dict]] = {}
    for record in records:
        by_trial.setdefault(record["trial_id"], {})[record["context_condition"]] = record

    rng = random.Random(f"{pilot_id}-blind-labels")
    rows, key_rows = [], []
    for trial_id in sorted(by_trial):
        conditions = by_trial[trial_id]
        if set(conditions) != set(CONDITION_ORDER):
            raise SystemExit(f"{trial_id} does not have exactly U, S and P")
        shuffled = list(CONDITION_ORDER)
        rng.shuffle(shuffled)
        for version, condition in zip(VERSIONS, shuffled):
            key_rows.append({"trial_id": trial_id, "version": version, "context_condition": condition})
            record = conditions[condition]
            for turn in record["turns"]:
                round_number = turn["round"]
                if trial_id.endswith("t11"):
                    guide = t11_guide(round_number, items, record["scene"]["location"])
                else:
                    guide = single_turn_guide(notes[trial_id])
                rows.append({
                    "pilot_id": pilot_id,
                    "generation_run_id": record["generation_run_id"],
                    "trial_id": trial_id,
                    "trial_type": record.get("trial_type"),
                    "version": version,
                    "round": round_number,
                    "what_to_check": guide,
                    "player_line": turn["player_dialogue"],
                    "npc_reply": turn["npc_dialogue"],
                    "context_use": "",
                    "world_consistency": "",
                    "no_contradiction": "NA" if round_number == 1 else "",
                    "note": "",
                })

    out_dir.mkdir(parents=True, exist_ok=True)
    short = pilot_id.split("_", 3)[-1]
    sheet = out_dir / f"human_labels_{short}.csv"
    with sheet.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with (out_dir / f"blind_key_{short}.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=["trial_id", "version", "context_condition"])
        writer.writeheader()
        writer.writerows(key_rows)
    (out_dir / f"labelling_context_{short}.md").write_text(
        context_markdown(records[0], pilot_id), encoding="utf-8"
    )
    print(f"{len(rows)} turns -> {sheet}")


if __name__ == "__main__":
    main()
