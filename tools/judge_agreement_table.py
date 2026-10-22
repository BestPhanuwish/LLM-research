"""Compare H1 judge runs with the author's blind human labels for one pilot run.

Adds or updates one row per judge model in a comparison table (CSV and
Markdown): agreement, Cohen's kappa (pooled and per metric), how many human
FAILs the judge also failed, and an estimated cost. Also writes each judge's
disagreements with the human labels for review.

Items are (turn, metric) pairs. Round-1 No Contradiction is excluded (both
sides are fixed to NA by rule, so it would inflate agreement), as are items the
human marked EXCLUDE (t11 R6 when R3 gave no specific answer). Labels are
PASS / FAIL / NA, and NA is kept as a label.

Cost is estimated from the prompt and response text saved in each result row
(tiktoken o200k_base, so approximate for non-OpenAI tokenizers) times the
model's OpenRouter price. It does not count retries or hidden reasoning tokens.

Usage:
    python tools/judge_agreement_table.py \
        --human data/.../human_labels_luna_neville.csv \
        --key data/.../blind_key_luna_neville.csv \
        --results output/evaluation/h1_consistency.jsonl [more result files] \
        --out data/.../judge_comparison_luna_neville
"""

from __future__ import annotations

import argparse
import csv
import datetime
import json
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

import tiktoken

METRICS = ("context_use", "world_consistency", "no_contradiction")
OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
# Judge change 11 (21 Oct 2026) rewrote the Context Use rubric; this phrase only
# appears in prompts from that version on.
PROMPT_V11_MARKER = "Decide which of three kinds of turn"

TABLE_COLUMNS = (
    "judge_model",
    "prompt",
    "n_items",
    "agreement",
    "cohen_kappa",
    "kappa_context_use",
    "kappa_world_consistency",
    "kappa_no_contradiction",
    "human_fails_caught",
    "judge_extra_fails",
    "est_cost_usd",
    "median_sec_per_turn",
    "total_min",
    "price_in_out_per_mtok",
    "generation_run_id",
    "results_file",
    "updated",
)


def cohen_kappa(pairs: list[tuple[str, str]]) -> float | None:
    if not pairs:
        return None
    n = len(pairs)
    observed = sum(a == b for a, b in pairs) / n
    left, right = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    expected = sum(left[label] * right[label] for label in left) / (n * n)
    if expected == 1:
        return None
    return (observed - expected) / (1 - expected)


def load_human(human_path: Path, key_path: Path) -> tuple[dict, str]:
    with key_path.open(encoding="utf-8") as file:
        key = {(row["trial_id"], row["version"]): row["context_condition"] for row in csv.DictReader(file)}
    labels, run_ids = {}, set()
    with human_path.open(encoding="utf-8-sig") as file:
        for row in csv.DictReader(file):
            run_ids.add(row["generation_run_id"])
            condition = key[(row["trial_id"], row["version"])]
            for metric in METRICS:
                value = row[metric].strip().upper()
                if value not in {"PASS", "FAIL", "NA", "EXCLUDE"}:
                    raise SystemExit(f"Unlabelled or invalid {metric} in {row['trial_id']} {row['version']} R{row['round']}")
                labels[(row["trial_id"], condition, int(float(row["round"])), metric)] = value
    if len(run_ids) != 1:
        raise SystemExit(f"Human sheet spans several runs: {sorted(run_ids)}")
    return labels, run_ids.pop()


def load_prices() -> dict[str, tuple[float, float]]:
    try:
        with urllib.request.urlopen(OPENROUTER_MODELS_URL, timeout=30) as response:
            models = json.load(response)["data"]
    except OSError as error:
        print(f"Could not fetch OpenRouter prices ({error}); cost left blank.")
        return {}
    return {
        model["id"]: (float(model["pricing"]["prompt"]), float(model["pricing"]["completion"]))
        for model in models
        if model.get("pricing")
    }


def price_for(model: str, prices: dict) -> tuple[float, float] | None:
    for candidate in (model, f"openai/{model}"):
        if candidate in prices:
            return prices[candidate]
    return None


def compare(judge_rows: list[dict], human: dict, encoding, prices: dict) -> tuple[dict, list[dict]]:
    pairs_by_metric = defaultdict(list)
    disagreements = []
    input_tokens = output_tokens = 0
    for row in judge_rows:
        input_tokens += len(encoding.encode(row.get("prompt", "")))
        output_tokens += len(encoding.encode(row.get("judge_response", "")))
        for metric in METRICS:
            item = (row["trial_id"], row["context_condition"], row["round"], metric)
            human_label = human.get(item)
            if human_label is None or human_label == "EXCLUDE":
                continue
            if metric == "no_contradiction" and row["round"] == 1:
                continue
            judge_label = row["decisions"][metric]["decision"]
            pairs_by_metric[metric].append((human_label, judge_label))
            if human_label != judge_label:
                decision = row["decisions"][metric]
                disagreements.append({
                    "trial_id": row["trial_id"],
                    "context_condition": row["context_condition"],
                    "round": row["round"],
                    "metric": metric,
                    "human": human_label,
                    "judge": judge_label,
                    "judge_evidence": decision.get("evidence") or json.dumps(decision.get("claims"), ensure_ascii=False),
                })

    pooled = [pair for metric in METRICS for pair in pairs_by_metric[metric]]
    human_fails = [pair for pair in pooled if pair[0] == "FAIL"]
    model = judge_rows[0]["judge_model"]
    prompt_version = prompt_version_of(judge_rows[0])
    price = price_for(model, prices)
    cost = None if price is None else input_tokens * price[0] + output_tokens * price[1]

    # judge_seconds exists only in rows from evaluate.py runs after 21 Oct 2026.
    seconds = sorted(row["judge_seconds"] for row in judge_rows if row.get("judge_seconds") is not None)
    median_seconds = seconds[len(seconds) // 2] if seconds else None
    total_minutes = sum(seconds) / 60 if seconds and len(seconds) == len(judge_rows) else None

    def fmt(value, digits=3):
        return "" if value is None else f"{value:.{digits}f}"

    summary = {
        "judge_model": model,
        "prompt": prompt_version,
        "n_items": len(pooled),
        "agreement": fmt(sum(a == b for a, b in pooled) / len(pooled)),
        "cohen_kappa": fmt(cohen_kappa(pooled)),
        **{f"kappa_{metric}": fmt(cohen_kappa(pairs_by_metric[metric])) for metric in METRICS},
        "human_fails_caught": f"{sum(b == 'FAIL' for _, b in human_fails)}/{len(human_fails)}",
        "judge_extra_fails": sum(a != "FAIL" and b == "FAIL" for a, b in pooled),
        "est_cost_usd": fmt(cost, 4),
        "median_sec_per_turn": fmt(median_seconds, 1),
        "total_min": fmt(total_minutes, 1),
        "price_in_out_per_mtok": "" if price is None else f"{price[0] * 1e6:g}/{price[1] * 1e6:g}",
    }
    return summary, disagreements


# Judge change 13 (22 Oct 2026) added partial-answer, concession and player-name
# wording; this phrase only appears from that version on.
PROMPT_V13_MARKER = "a concession phrased as a rebuttal"
# Judge change 14 (22 Oct 2026): Context Use decision must follow its evidence.
PROMPT_V14_MARKER = "concedes, or does not correct the player's claim, the decision is FAIL"


def prompt_version_of(row: dict) -> str:
    prompt = row.get("prompt", "")
    if PROMPT_V14_MARKER in prompt:
        return "change 14"
    if PROMPT_V13_MARKER in prompt:
        return "change 13"
    return "change 11" if PROMPT_V11_MARKER in prompt else "before change 11"


def write_markdown(path: Path, rows: list[dict]) -> None:
    shown = ("judge_model", "prompt", "agreement", "cohen_kappa", "est_cost_usd",
             "median_sec_per_turn", "total_min", "kappa_context_use",
             "kappa_world_consistency", "kappa_no_contradiction", "human_fails_caught",
             "judge_extra_fails", "n_items")
    lines = [
        "# Judge comparison against human labels",
        "",
        "Generated by `tools/judge_agreement_table.py`; do not edit by hand. Agreement and "
        "Cohen's kappa are pooled over Context Use, World Consistency and No Contradiction "
        "(round-1 No Contradiction excluded). `est_cost_usd` is the estimated H1 cost of "
        "judging this one pilot run (saved prompt and response tokens times the OpenRouter "
        "price; retries and hidden reasoning tokens not counted).",
        "",
        "| " + " | ".join(shown) + " |",
        "|" + "---|" * len(shown),
    ]
    lines += ["| " + " | ".join(str(row.get(column, "")) for column in shown) + " |" for row in rows]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--human", type=Path, required=True)
    parser.add_argument("--key", type=Path, required=True)
    parser.add_argument("--results", type=Path, nargs="+", required=True)
    parser.add_argument("--out", type=Path, required=True, help="output path prefix (no extension)")
    args = parser.parse_args()

    human, run_id = load_human(args.human, args.key)
    encoding = tiktoken.get_encoding("o200k_base")
    prices = load_prices()

    table_path = args.out.with_suffix(".csv")
    existing = {}
    if table_path.exists():
        with table_path.open(encoding="utf-8") as file:
            for row in csv.DictReader(file):
                # Rows written before the prompt column existed used the old rubric.
                row["prompt"] = row.get("prompt") or "before change 11"
                existing[(row["judge_model"], row["generation_run_id"], row["prompt"])] = row

    for results_path in args.results:
        by_model = defaultdict(list)
        with results_path.open(encoding="utf-8") as file:
            for line in file:
                if line.strip():
                    row = json.loads(line)
                    if row.get("generation_run_id") == run_id:
                        by_model[(row["judge_model"], prompt_version_of(row))].append(row)
        if not by_model:
            print(f"{results_path}: no rows for run {run_id}")
        for (model, prompt_version), rows in by_model.items():
            summary, disagreements = compare(rows, human, encoding, prices)
            summary.update(
                generation_run_id=run_id,
                results_file=str(results_path),
                updated=datetime.date.today().isoformat(),
            )
            existing[(model, run_id, prompt_version)] = summary
            safe = model.replace("/", "_").replace(":", "_")
            if prompt_version != "before change 11":
                safe += "_" + prompt_version.replace(" ", "")
            with args.out.parent.joinpath(f"{args.out.name}_disagreements_{safe}.csv").open(
                "w", newline="", encoding="utf-8"
            ) as file:
                fields = ["trial_id", "context_condition", "round", "metric", "human", "judge", "judge_evidence"]
                writer = csv.DictWriter(file, fieldnames=fields)
                writer.writeheader()
                writer.writerows(disagreements)
            print(f"{model} ({prompt_version}): agreement {summary['agreement']}, kappa {summary['cohen_kappa']}, "
                  f"FAILs caught {summary['human_fails_caught']}, est. cost ${summary['est_cost_usd']}")

    rows = sorted(existing.values(), key=lambda row: -float(row["cohen_kappa"] or -1))
    with table_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(TABLE_COLUMNS))
        writer.writeheader()
        writer.writerows({column: row.get(column, "") for column in TABLE_COLUMNS} for row in rows)
    write_markdown(args.out.with_suffix(".md"), rows)
    print(f"Table: {table_path}")


if __name__ == "__main__":
    main()
