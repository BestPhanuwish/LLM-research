"""Tests for the final-study runner (tools/run_final.py) and its simulator options."""

import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from simulator import parse_args


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("run_final", REPOSITORY_ROOT / "tools" / "run_final.py")
run_final = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(run_final)


def runner_args(**overrides):
    values = {"skip_generation": False, "h1_only": False, "h2_only": False, "dry_run": True}
    values.update(overrides)
    return SimpleNamespace(**values)


class SimulatorFinalStudyOptionTests(TestCase):
    def test_seed_and_trajectory_output_default_to_none(self):
        with patch("sys.argv", ["simulator.py", "-c", "config/play.yaml"]):
            args = parse_args()
        self.assertIsNone(args.seed)
        self.assertIsNone(args.trajectory_output)

    def test_seed_and_trajectory_output_are_parsed(self):
        with patch("sys.argv", ["simulator.py", "-c", "config/play.yaml", "--seed", "3", "--trajectory-output", "out/t.jsonl"]):
            args = parse_args()
        self.assertEqual(args.seed, 3)
        self.assertEqual(args.trajectory_output, "out/t.jsonl")


class RunFinalTests(TestCase):
    def test_pilot_one_manifest_has_no_number(self):
        self.assertEqual(run_final.pilot_manifest(1).name, "characterbox_pilot.json")
        self.assertEqual(run_final.pilot_manifest(7).name, "characterbox_pilot7.json")

    def test_run_dir_pads_pilot_number(self):
        folder = run_final.run_dir(2, 7)
        self.assertEqual((folder.parent.name, folder.name), ("seed2", "p07"))

    def test_existing_pilots_expect_one_row_per_trial_and_condition(self):
        for number in range(1, 6):
            self.assertEqual(run_final.expected_trajectory_rows(run_final.pilot_manifest(number)), 33)

    def test_partial_trajectory_stops_the_run(self):
        with TemporaryDirectory() as directory, patch.object(run_final, "FINAL_DIR", Path(directory)):
            trajectory = run_final.run_dir(9, 1) / "trajectory.jsonl"
            trajectory.parent.mkdir(parents=True)
            trajectory.write_text(json.dumps({"trial_id": "t01"}) + "\n", encoding="utf8")
            with patch.object(run_final, "run") as run, self.assertRaises(SystemExit):
                run_final.run_pilot(9, 1, runner_args())
            run.assert_not_called()

    def test_complete_trajectory_skips_generation_and_runs_both_judges(self):
        with TemporaryDirectory() as directory, patch.object(run_final, "FINAL_DIR", Path(directory)):
            trajectory = run_final.run_dir(9, 1) / "trajectory.jsonl"
            trajectory.parent.mkdir(parents=True)
            trajectory.write_text("{}\n" * 33, encoding="utf8")
            with patch.object(run_final, "run") as run:
                run_final.run_pilot(9, 1, runner_args(dry_run=False))
            scripts = [call.args[0][1] for call in run.call_args_list]
            lanes = [call.args[0][5] for call in run.call_args_list]
            self.assertEqual(scripts, ["evaluate.py", "evaluate.py"])
            self.assertEqual(lanes, ["--h1-only", "--h2-only"])

    def test_missing_trajectory_generates_with_seed_and_output_path(self):
        with TemporaryDirectory() as directory, patch.object(run_final, "FINAL_DIR", Path(directory)):
            with patch.object(run_final, "run") as run:
                run_final.run_pilot(4, 2, runner_args(h1_only=True))
            generate = [str(part) for part in run.call_args_list[0].args[0]]
            self.assertEqual(generate[1], "simulator.py")
            self.assertEqual(generate[generate.index("--seed") + 1], "4")
            self.assertTrue(generate[generate.index("--trajectory-output") + 1].endswith("seed4/p02/trajectory.jsonl"))
            self.assertEqual(len(run.call_args_list), 2)  # generation + H1 only
