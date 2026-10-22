"""Tests for CharacterBox-compatible controlled-trajectory evaluation."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

import httpx
from openai import RateLimitError

from evaluate_characterbox import (
    CRITIC_CRITERIA,
    METRICS,
    RATE_LIMIT_MAX_ATTEMPTS,
    SCORING_CRITERIA,
    TARGET_ONLY_CRITIC_NOTE,
    TARGET_ONLY_SCORE_NOTE,
    build_critic_prompt,
    build_score_prompt,
    evaluate_trajectory,
    judge_text,
    load_trajectory_run,
    parse_scores,
)


def make_rate_limit_error(retry_after=None):
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    headers = {"Retry-After": str(retry_after)} if retry_after is not None else {}
    response = httpx.Response(429, request=request, headers=headers)
    return RateLimitError("Rate limit reached", response=response, body=None)


class RateLimitedThenSucceedsJudge:
    """Raises RateLimitError on `invoke()` a fixed number of times, then returns
    `final_content` on every call after that."""

    model_name = "fake-judge"

    def __init__(self, num_rate_limit_errors, final_content="hello", retry_after=None):
        self.remaining_errors = num_rate_limit_errors
        self.final_content = final_content
        self.retry_after = retry_after
        self.call_count = 0

    def invoke(self, messages):
        self.call_count += 1
        if self.remaining_errors > 0:
            self.remaining_errors -= 1
            raise make_rate_limit_error(self.retry_after)
        return type("Response", (), {"content": self.final_content})()


def trajectory(condition, run_id="run-001", trial_id="trial-001"):
    return {
        "schema_version": 1,
        "record_type": "controlled_dialogue_trajectory",
        "generation_run_id": run_id,
        "trial_id": trial_id,
        "scene_id": 19,
        "target_character_id": 1,
        "context_condition": condition,
        "priority_policy_id": (
            "primary_four_level" if condition == "P" else None
        ),
        "pilot_conditions": ["U", "S", "P"],
        "scene": {
            "event": "Secret meeting",
            "time": "Late evening",
            "location": "Shrieking Shack",
            "description": "A cautious private meeting.",
        },
        "target": {
            "name": "Neville Longbottom",
            "description": "Nervous but loyal and determined.",
        },
        "turns": [
            {
                "round": 1,
                "player_dialogue": "What did you want to tell me?",
                "npc_dialogue": "Keep your voice down.",
                "npc_observation": 'Luna: "What did you want to tell me?"',
            }
        ],
    }


VALID_RESPONSE = "\n".join(f"{metric}: 4" for metric in METRICS)


class FakeJudge:
    model_name = "fake-judge"

    def __init__(self, responses):
        self.responses = iter(responses)
        self.prompts = []

    def invoke(self, messages):
        self.prompts.append(messages[0].content)
        response = next(self.responses)
        if isinstance(response, str):
            return type("Response", (), {"content": response})()
        # A (content, response_metadata, additional_kwargs) tuple simulates a real
        # AIMessage closely enough to exercise judge_text()'s empty-response diagnostics.
        content, response_metadata, additional_kwargs = response
        return type(
            "Response",
            (),
            {
                "content": content,
                "response_metadata": response_metadata,
                "additional_kwargs": additional_kwargs,
            },
        )()


class CharacterBoxEvaluationTests(TestCase):
    def test_score_parser_requires_all_metrics_in_range(self):
        self.assertEqual(
            {metric: 4 for metric in METRICS},
            parse_scores(VALID_RESPONSE),
        )
        with self.assertRaisesRegex(ValueError, "between 1 and 5"):
            parse_scores(VALID_RESPONSE.replace("Knowledge Accuracy: 4", "Knowledge Accuracy: 9"))
        with self.assertRaisesRegex(ValueError, "Behavioral Coherence"):
            parse_scores(VALID_RESPONSE.replace("Behavioral Coherence: 4", ""))

    def test_loads_latest_complete_paired_run_in_manifest_order(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "trajectory.jsonl"
            records = [
                trajectory("U", "old"),
                trajectory("S", "old"),
                trajectory("P", "old"),
                trajectory("P", "latest"),
                trajectory("U", "latest"),
                trajectory("S", "latest"),
            ]
            path.write_text(
                "".join(json.dumps(record) + "\n" for record in records),
                encoding="utf-8",
            )

            trials = load_trajectory_run(path)

        self.assertEqual(1, len(trials))
        self.assertEqual(["U", "S", "P"], [item["context_condition"] for item in trials[0]])
        self.assertEqual({"latest"}, {item["generation_run_id"] for item in trials[0]})

    def test_loads_every_trial_sharing_one_pilot_generation_run_id(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "trajectory.jsonl"
            records = [
                trajectory("U", "pilot-run", "trial-001"),
                trajectory("S", "pilot-run", "trial-001"),
                trajectory("P", "pilot-run", "trial-001"),
                trajectory("U", "pilot-run", "trial-002"),
                trajectory("S", "pilot-run", "trial-002"),
                trajectory("P", "pilot-run", "trial-002"),
            ]
            path.write_text(
                "".join(json.dumps(record) + "\n" for record in records),
                encoding="utf-8",
            )

            trials = load_trajectory_run(path, "pilot-run")

        self.assertEqual(2, len(trials))
        self.assertEqual(
            ["trial-001", "trial-002"],
            [trial[0]["trial_id"] for trial in trials],
        )
        for trial in trials:
            self.assertEqual(["U", "S", "P"], [item["context_condition"] for item in trial])

    def test_rejects_trial_missing_a_declared_condition(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "trajectory.jsonl"
            records = [
                trajectory("U", "pilot-run", "trial-001"),
                trajectory("S", "pilot-run", "trial-001"),
                trajectory("P", "pilot-run", "trial-001"),
                trajectory("U", "pilot-run", "trial-002"),
                trajectory("S", "pilot-run", "trial-002"),
            ]
            path.write_text(
                "".join(json.dumps(record) + "\n" for record in records),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "trial-002 does not contain exactly"):
                load_trajectory_run(path, "pilot-run")

    def test_prompt_is_condition_blind_and_contains_complete_trajectory(self):
        prompt = build_score_prompt(trajectory("P"), "No serious issue.")

        self.assertNotIn("context_condition", prompt)
        self.assertNotIn("Priority", prompt)
        self.assertNotIn("primary_four_level", prompt)
        self.assertIn("Round: 1", prompt)
        self.assertIn("Keep your voice down.", prompt)
        self.assertIn("No serious issue.", prompt)

    def test_prompts_preserve_characterbox_wording_and_response_example(self):
        critic_prompt = build_critic_prompt(trajectory("U"))
        score_prompt = build_score_prompt(trajectory("U"), "No serious issue.")

        self.assertIn(
            "Please execute the following role-play and identify any issues "
            "based on these strict evaluation criteria:",
            critic_prompt,
        )
        self.assertIn(CRITIC_CRITERIA, critic_prompt)
        self.assertIn(SCORING_CRITERIA, score_prompt)
        self.assertIn("[Response Format Example]:", score_prompt)
        self.assertIn("Knowledge Accuracy: 3", score_prompt)
        self.assertTrue(SCORING_CRITERIA.startswith("\n[Scoring Criteria]:"))
        self.assertTrue(SCORING_CRITERIA.endswith("[Response]:\n\n"))
        self.assertIn(
            "Your resposne must follow the format provided below.", score_prompt
        )

    def test_prompts_name_only_the_target_character(self):
        record = trajectory("U")
        critic_prompt = build_critic_prompt(record)
        score_prompt = build_score_prompt(record, "No serious issue.")
        name = record["target"]["name"]

        self.assertIn(TARGET_ONLY_CRITIC_NOTE.format(name=name), critic_prompt)
        self.assertIn(TARGET_ONLY_SCORE_NOTE.format(name=name), score_prompt)
        # The note follows the retained CharacterBox opening line in each prompt.
        self.assertLess(
            critic_prompt.index("strict evaluation criteria:"),
            critic_prompt.index(f"Evaluate only {name}'s"),
        )
        self.assertLess(
            score_prompt.index("critique and evaluation criteria."),
            score_prompt.index(f"Score only {name};"),
        )

    def test_character_block_includes_position_and_state_when_supplied(self):
        record = trajectory("U")
        record["target"]["position"] = "Hiding behind a large rock."
        record["target"]["states"] = "Nervous but determined."
        for prompt in (build_critic_prompt(record), build_score_prompt(record, "No serious issue.")):
            self.assertIn("Position: Hiding behind a large rock.", prompt)
            self.assertIn("State: Nervous but determined.", prompt)

        bare = build_critic_prompt(trajectory("U"))
        self.assertNotIn("Position:", bare)
        self.assertNotIn("State:", bare)

    def test_evaluation_runs_critique_then_strict_scoring(self):
        judge = FakeJudge(["No serious issue.", "bad format", VALID_RESPONSE])

        result = evaluate_trajectory(trajectory("S"), judge, score_retries=2)

        self.assertEqual(3, len(judge.prompts))
        self.assertEqual({metric: 4 for metric in METRICS}, result["scores"])
        self.assertEqual(4.0, result["average"])

    def test_retries_past_an_empty_score_response(self):
        # A deterministic empty completion (content filter, refusal, truncation) must
        # be retried like any other malformed response, not silently treated as "".
        judge = FakeJudge([
            "No serious issue.",
            ("", {"finish_reason": "content_filter"}, {}),
            VALID_RESPONSE,
        ])

        result = evaluate_trajectory(trajectory("S"), judge, score_retries=2)

        self.assertEqual({metric: 4 for metric in METRICS}, result["scores"])


class JudgeTextTests(TestCase):
    def test_raises_with_finish_reason_on_empty_response(self):
        judge = FakeJudge([("", {"finish_reason": "content_filter"}, {})])

        with self.assertRaisesRegex(ValueError, r"finish_reason='content_filter'"):
            judge_text(judge, "prompt")

    def test_raises_with_refusal_when_present(self):
        judge = FakeJudge([
            ("", {"finish_reason": "stop"}, {"refusal": "I can't help with that."}),
        ])

        with self.assertRaisesRegex(ValueError, "refusal="):
            judge_text(judge, "prompt")

    def test_returns_content_when_non_empty(self):
        judge = FakeJudge(["hello"])

        self.assertEqual("hello", judge_text(judge, "prompt"))

    def test_raises_on_whitespace_only_content(self):
        # A whitespace-only string is truthy in Python, so `if not response.content`
        # alone would miss this and let json.loads("\n") raise its own confusing
        # "Expecting value" error further downstream instead.
        judge = FakeJudge([("\n", {"finish_reason": "stop"}, {})])

        with self.assertRaisesRegex(ValueError, "empty response"):
            judge_text(judge, "prompt")

    def test_retries_past_rate_limit_then_succeeds(self):
        # Reproduces a real production run: gpt-4o's organisation-level TPM limit was
        # exceeded mid-run and openai.RateLimitError propagated straight through
        # judge_text() uncaught, crashing the whole evaluate.py invocation.
        judge = RateLimitedThenSucceedsJudge(num_rate_limit_errors=2, final_content="hello")

        with patch("evaluate_characterbox.time.sleep") as fake_sleep:
            result = judge_text(judge, "prompt")

        self.assertEqual("hello", result)
        self.assertEqual(3, judge.call_count)
        # No Retry-After header on these errors, so falls back to exponential
        # backoff from a 10s base: 10s then 20s before the two retries that
        # preceded success.
        fake_sleep.assert_any_call(10)
        fake_sleep.assert_any_call(20)

    def test_respects_retry_after_header_but_never_waits_less_than_the_floor(self):
        # OpenAI can send a Retry-After as short as 1s, which is too short to
        # actually clear a per-minute token limit -- retrying that fast just burns
        # another attempt against the same window instead of waiting it out.
        judge = RateLimitedThenSucceedsJudge(
            num_rate_limit_errors=1, final_content="hello", retry_after=1
        )

        with patch("evaluate_characterbox.time.sleep") as fake_sleep:
            result = judge_text(judge, "prompt")

        self.assertEqual("hello", result)
        fake_sleep.assert_called_once_with(10)

    def test_honours_a_generous_retry_after_header(self):
        judge = RateLimitedThenSucceedsJudge(
            num_rate_limit_errors=1, final_content="hello", retry_after=45
        )

        with patch("evaluate_characterbox.time.sleep") as fake_sleep:
            result = judge_text(judge, "prompt")

        self.assertEqual("hello", result)
        fake_sleep.assert_called_once_with(45)

    def test_survives_more_rate_limit_errors_than_the_old_five_attempt_cap(self):
        # The old cap gave up after 5 attempts (~75s total); a single sustained
        # spike can easily outlast that. Confirm the fix actually raised the
        # ceiling rather than just changing the backoff math.
        judge = RateLimitedThenSucceedsJudge(num_rate_limit_errors=10, final_content="hello")

        with patch("evaluate_characterbox.time.sleep"):
            result = judge_text(judge, "prompt")

        self.assertEqual("hello", result)
        self.assertEqual(11, judge.call_count)

    def test_raises_after_exhausting_rate_limit_retries(self):
        judge = RateLimitedThenSucceedsJudge(num_rate_limit_errors=RATE_LIMIT_MAX_ATTEMPTS + 5)

        with patch("evaluate_characterbox.time.sleep"):
            with self.assertRaises(RateLimitError):
                judge_text(judge, "prompt")

        self.assertEqual(RATE_LIMIT_MAX_ATTEMPTS, judge.call_count)


if __name__ == "__main__":
    import unittest

    unittest.main()
