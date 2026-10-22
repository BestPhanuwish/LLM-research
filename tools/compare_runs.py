"""Compare two or more generation runs of the same pilot, turn by turn.

Written 14 Oct 2026 to check whether the shared prompt opening (and the move to
OpenRouter) changed pilot 1's replies and scores. Read-only: it never calls a
model. Each run is given as LABEL TRAJECTORY H1 H2, where H1/H2 are evaluate.py
outputs ("-" if not judged yet). Append "#<generation_run_id>" to TRAJECTORY
when the file holds more than one run.

Example:
    python tools/compare_runs.py \
      --run old output/record/Harry_Potter/trajectory/gpt-4o-mini_gpt-4o-mini_trajectory-p1.jsonl \
                output/evaluation/h1_consistency.jsonl output/evaluation/h2_realism.jsonl \
      --run new output/record/Harry_Potter/trajectory/openai-gpt-4o-mini_openai-gpt-4o-mini_trajectory-p1-rerun.jsonl \
                output/evaluation/p1_rerun_h1.jsonl output/evaluation/p1_rerun_h2.jsonl \
      --out output/comparison/p1_old_vs_new.md
"""

import argparse
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean

CONDITIONS = ("U", "S", "P")
TRIAL_TYPE_NAMES = {1: "neutral/open (t01-t06)", 2: "stress (t07-t10)", 3: "multi-turn (t11)"}
H1_METRICS = {"context_use": "CU", "world_consistency": "WC", "no_contradiction": "NC"}
SHORT = {"PASS": "P", "FAIL": "F", "NA": "-", None: "?"}


def read_jsonl(path):
    with open(path, encoding="utf8") as file:
        return [json.loads(line) for line in file if line.strip()]


def load_run(label, trajectory_spec, h1_path, h2_path):
    path, _, run_id = trajectory_spec.partition("#")
    records = read_jsonl(path)
    run_ids = sorted({record["generation_run_id"] for record in records})
    if run_id:
        records = [r for r in records if r["generation_run_id"] == run_id]
    elif len(run_ids) != 1:
        raise SystemExit(
            f"{path} holds {len(run_ids)} runs; append #<id> to choose one: {run_ids}"
        )
    else:
        run_id = run_ids[0]
    if not records:
        raise SystemExit(f"No records for run {run_id} in {path}")

    replies = {}
    for record in records:
        for turn in record["turns"]:
            key = (record["trial_id"], record["context_condition"], turn["round"])
            replies[key] = {
                "trial_type": record["trial_type"],
                "player": turn["player_dialogue"],
                "reply": turn["npc_dialogue"],
            }

    h1 = {}
    if h1_path != "-":
        for row in read_jsonl(h1_path):
            if row["generation_run_id"] == run_id:
                key = (row["trial_id"], row["context_condition"], row["round"])
                h1[key] = row
    h2 = {}
    if h2_path != "-":
        for row in read_jsonl(h2_path):
            if row["generation_run_id"] == run_id:
                h2[(row["trial_id"], row["context_condition"])] = row["average"]

    models = {record.get("generation", {}).get("character_model") for record in records}
    policies = {record.get("priority_policy_id") for record in records} - {None}
    return {
        "label": label,
        "run_id": run_id,
        "path": path,
        "models": sorted(m for m in models if m),
        "policies": sorted(policies),
        "pilot_id": records[0]["pilot_id"],
        "replies": replies,
        "h1": h1,
        "h2": h2,
    }


def decisions(row):
    if row is None:
        return "not judged"
    parts = [
        f"{short}={SHORT.get(row['decisions'][metric]['decision'], '?')}"
        for metric, short in H1_METRICS.items()
    ]
    return f"{row['consistency']:.2f} ({', '.join(parts)})"


def summary_table(runs):
    lines = [
        "| Trial type | Condition | " + " | ".join(f"H1 {r['label']}" for r in runs)
        + " | " + " | ".join(f"H2 {r['label']}" for r in runs) + " |",
        "|---|---|" + "---|" * (2 * len(runs)),
    ]
    for trial_type, type_name in TRIAL_TYPE_NAMES.items():
        for condition in CONDITIONS:
            h1_cells, h2_cells = [], []
            for run in runs:
                scores = [
                    row["consistency"]
                    for (trial, cond, _), row in run["h1"].items()
                    if cond == condition
                    and run["replies"].get((trial, cond, row["round"]), {}).get("trial_type") == trial_type
                    and row["consistency"] is not None
                ]
                h1_cells.append(f"{mean(scores):.2f} (n={len(scores)})" if scores else "-")
                realism = [
                    value for (trial, cond), value in run["h2"].items()
                    if cond == condition
                    and run["replies"].get((trial, cond, 1), {}).get("trial_type") == trial_type
                ]
                h2_cells.append(f"{mean(realism):.2f}" if realism else "-")
            lines.append(
                f"| {type_name} | {condition} | " + " | ".join(h1_cells)
                + " | " + " | ".join(h2_cells) + " |"
            )
    return "\n".join(lines)


def changed_decisions(runs):
    """Turns whose H1 consistency differs between the first run and any other."""
    base = runs[0]
    changes = defaultdict(int)
    rows = []
    for key in sorted(base["h1"]):
        base_score = base["h1"][key]["consistency"]
        for other in runs[1:]:
            other_row = other["h1"].get(key)
            if other_row is None or other_row["consistency"] == base_score:
                continue
            direction = "better" if (other_row["consistency"] or 0) > (base_score or 0) else "worse"
            changes[(other["label"], key[1], direction)] += 1
            rows.append(
                f"| {key[0][-3:]} R{key[2]} | {key[1]} | {other['label']} | "
                f"{decisions(base['h1'][key])} | {decisions(other_row)} |"
            )
    if not rows:
        return "No turn changed its H1 consistency score."
    counts = ", ".join(
        f"{label} {condition} {direction}: {n}"
        for (label, condition, direction), n in sorted(changes.items())
    )
    header = (
        f"Counts against {base['label']}: {counts}\n\n"
        f"| Turn | Cond | Run | {base['label']} | other |\n|---|---|---|---|---|"
    )
    return header + "\n" + "\n".join(rows)


def reply_by_reply(runs):
    base = runs[0]
    out = []
    current_trial = None
    for key in sorted(base["replies"], key=lambda k: (k[0], k[2], CONDITIONS.index(k[1]))):
        trial, condition, round_number = key
        if trial != current_trial:
            current_trial = trial
            trial_type = base["replies"][key]["trial_type"]
            out.append(f"\n### {trial} ({TRIAL_TYPE_NAMES.get(trial_type, trial_type)})\n")
        player = base["replies"][key]["player"]
        out.append(f"**R{round_number} · {condition}** · Player: {player}\n")
        for run in runs:
            entry = run["replies"].get(key)
            reply = entry["reply"] if entry else "(missing)"
            if entry and entry["player"] != player:
                reply += " ⚠ player line differs from the first run"
            out.append(f"- *{run['label']}* [{decisions(run['h1'].get(key))}]: {reply}")
        out.append("")
    return "\n".join(out)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--run", nargs=4, action="append", required=True,
        metavar=("LABEL", "TRAJECTORY", "H1", "H2"),
        help="repeat for each run; the first run is the baseline",
    )
    parser.add_argument("--out", type=Path, required=True, help="Markdown report path")
    args = parser.parse_args()
    if len(args.run) < 2:
        parser.error("give at least two --run arguments")

    runs = [load_run(*spec) for spec in args.run]
    if len({run["pilot_id"] for run in runs}) != 1:
        raise SystemExit("Runs come from different pilots; compare the same pilot only.")

    header = [f"# Run comparison: {runs[0]['pilot_id']}\n"]
    for run in runs:
        header.append(
            f"- **{run['label']}**: run `{run['run_id']}`, model {', '.join(run['models'])}, "
            f"P policy {', '.join(run['policies']) or '-'}, "
            f"{len(run['h1'])} H1 turns, {len(run['h2'])} H2 trials judged (`{run['path']}`)"
        )
    report = "\n".join(header) + (
        "\n\nH1 cells: consistency (CU Context Use, WC World Consistency, NC No Contradiction; P PASS, F FAIL, - NA).\n"
        "\n## Mean scores\n\n" + summary_table(runs)
        + "\n\n## Turns whose H1 score changed\n\n" + changed_decisions(runs)
        + "\n\n## Reply by reply\n" + reply_by_reply(runs) + "\n"
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report, encoding="utf8")
    print(f"Report written to {args.out}")


if __name__ == "__main__":
    main()
