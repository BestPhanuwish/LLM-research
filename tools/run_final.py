"""Run one seed of the final study for one or more pilots: generate, then judge.

Written 22 Oct 2026 for the final study (pilots 1-10, several generation seeds).
Every (seed, pilot) pair gets its own folder:

    output/final/seed{N}/p{NN}/trajectory.jsonl      simulator.py --pilot ... --seed N
    output/final/seed{N}/p{NN}/h1_consistency.jsonl  evaluate.py --h1-only
    output/final/seed{N}/p{NN}/h2_realism.jsonl      evaluate.py --h2-only

Steps that are already complete are skipped, so the same command can be rerun
after an interruption. Generation is skipped when the trajectory holds one row
per trial and condition; a partial trajectory stops the run (delete it and
rerun), because the simulator appends and a second run would mix two
generation_run_ids. H1 and H2 always run: evaluate.py skips turns and trials it
has already scored, so a rerun only fills in what is missing.

Examples:
    python tools/run_final.py --seed 2 --pilot 1 2 3
    python tools/run_final.py --seed 1 --pilot 1 2 3 4 5 --skip-generation --h2-only
    python tools/run_final.py --seed 3 --pilot 6 --dry-run
"""

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FINAL_DIR = ROOT / "output" / "final"
PILOT_DIR = ROOT / "data" / "research_annotations"
PLAY_CONFIG = ROOT / "config" / "play.yaml"
EVALUATE_CONFIG = ROOT / "config" / "evaluate.yaml"
PILOT_RUN_CONFIG = ROOT / "config" / "pilot_run_config.json"


def pilot_manifest(number):
    """Pilot 1's manifest predates the numbering, so it has no number."""
    name = "characterbox_pilot.json" if number == 1 else f"characterbox_pilot{number}.json"
    return PILOT_DIR / name


def run_dir(seed, number):
    return FINAL_DIR / f"seed{seed}" / f"p{number:02d}"


def count_rows(path):
    if not path.exists():
        return 0
    with open(path, encoding="utf8") as file:
        return sum(1 for line in file if line.strip())


def expected_trajectory_rows(manifest):
    with open(manifest, encoding="utf8") as file:
        trials = json.load(file)["trials"]
    with open(PILOT_RUN_CONFIG, encoding="utf8") as file:
        conditions = json.load(file)["conditions"]
    return len(trials) * len(conditions)


def run(command, dry_run):
    print("$", shlex.join(str(part) for part in command), flush=True)
    if not dry_run:
        subprocess.run(command, cwd=ROOT, check=True)


def run_pilot(seed, number, args):
    manifest = pilot_manifest(number)
    if not manifest.exists():
        raise SystemExit(f"No manifest for pilot {number}: {manifest}")
    folder = run_dir(seed, number)
    trajectory = folder / "trajectory.jsonl"
    print(f"\n=== seed {seed}, pilot {number} -> {folder} ===", flush=True)

    expected = expected_trajectory_rows(manifest)
    rows = count_rows(trajectory)
    if args.skip_generation or rows == expected:
        print(f"generation: skipped ({rows}/{expected} trajectory rows)")
    elif rows:
        raise SystemExit(
            f"{trajectory} is partial ({rows}/{expected} rows). Delete it and rerun."
        )
    else:
        run([sys.executable, "simulator.py", "-c", PLAY_CONFIG, "--pilot", manifest,
             "--seed", str(seed), "--trajectory-output", trajectory], args.dry_run)

    if not args.dry_run and count_rows(trajectory) != expected:
        raise SystemExit(f"{trajectory} has {count_rows(trajectory)}/{expected} rows; not judging.")

    if not args.h2_only:
        run([sys.executable, "evaluate.py", trajectory, "-c", EVALUATE_CONFIG, "--h1-only",
             "--h1-output", folder / "h1_consistency.jsonl"], args.dry_run)
    if not args.h1_only:
        run([sys.executable, "evaluate.py", trajectory, "-c", EVALUATE_CONFIG, "--h2-only",
             "--h2-output", folder / "h2_realism.jsonl"], args.dry_run)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--seed", type=int, required=True, help="generation seed")
    parser.add_argument("--pilot", type=int, nargs="+", required=True, help="pilot numbers, e.g. 1 2 3")
    parser.add_argument("--skip-generation", action="store_true",
                        help="judge an existing trajectory without generating")
    judges = parser.add_mutually_exclusive_group()
    judges.add_argument("--h1-only", action="store_true", help="run only the H1 consistency judge")
    judges.add_argument("--h2-only", action="store_true", help="run only the H2 realism judge")
    parser.add_argument("--dry-run", action="store_true", help="print the commands without running them")
    args = parser.parse_args()
    for number in args.pilot:
        run_pilot(args.seed, number, args)


if __name__ == "__main__":
    main()
