"""Tests for evaluate.py's H1 (per-turn consistency) lane and H2 wrapper."""

import json
from unittest import TestCase

from evaluate import (
    _quote_is_verbatim,
    DECISION_TO_SCORE,
    NO_SUPPLIED_FACT,
    build_h1_prompt,
    compute_consistency,
    evaluate_h1_turn,
    evaluate_h2_trial,
    format_turn_context,
    parse_h1_response,
)


def trajectory(condition="U", run_id="run-001", trial_id="trial-001"):
    return {
        "schema_version": 1,
        "record_type": "controlled_dialogue_trajectory",
        "generation_run_id": run_id,
        "pilot_id": "pilot-001",
        "trial_id": trial_id,
        "scene_id": 19,
        "target_character_id": 1,
        "context_condition": condition,
        "priority_policy_id": "primary_four_level" if condition == "P" else None,
        "pilot_conditions": ["U", "S", "P"],
        "scene": {
            "event": "Secret meeting",
            "time": "Late evening",
            "location": "Shrieking Shack",
            "description": "A cautious private meeting.",
        },
        "target": {
            "name": "Neville Longbottom",
            "position": "Standing by the door",
            "states": "Nervous, alert",
            "description": "Nervous but loyal and determined.",
        },
        "action_reference": "Warn Luna about the incoming patrol.",
        "turns": [
            {
                "round": 1,
                "player_dialogue": "What did you want to tell me?",
                "npc_dialogue": "Keep your voice down.",
                "npc_observation": 'Luna: "What did you want to tell me?"',
            },
            {
                "round": 2,
                "player_dialogue": "Is it about the patrol?",
                "npc_dialogue": "I've got your back, I promise.",
                "npc_observation": 'Luna: "Is it about the patrol?"',
            },
            {
                "round": 3,
                "player_dialogue": "So we're safe?",
                "npc_dialogue": "I don't think I can promise anything right now.",
                "npc_observation": 'Luna: "So we\'re safe?"',
            },
        ],
    }


# The default npc_dialogue used wherever a test calls parse_h1_response() directly
# rather than through evaluate_h1_turn() (which pulls the real per-round dialogue out
# of the trajectory record itself).
NPC_DIALOGUE = "Keep your voice down."

VALID_H1_RESPONSE = json.dumps(
    {
        "context_use": {"decision": "PASS", "evidence": "Uses the patrol fact."},
        "world_consistency": {
            "claims": [
                {
                    "claim": "the player should keep quiet",
                    "quote": "Keep your voice down",
                    "consistent": True,
                    "checked_against": NO_SUPPLIED_FACT,
                },
            ],
        },
        "no_contradiction": {"decision": "NA", "contradicted_round": None, "evidence": None},
    }
)


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


class FormatTurnContextTests(TestCase):
    def test_omits_future_turns(self):
        _, _, _, prior_text, current_text = format_turn_context(trajectory(), 2)

        self.assertIn("Round 1", prior_text)
        self.assertNotIn("Round 2", prior_text)
        self.assertIn("Round 2", current_text)
        self.assertNotIn("Round 3", current_text)
        self.assertNotIn("So we're safe?", prior_text)
        self.assertNotIn("So we're safe?", current_text)

    def test_first_round_has_no_prior_turns(self):
        _, _, _, prior_text, current_text = format_turn_context(trajectory(), 1)

        self.assertIn("none", prior_text.lower())
        self.assertIn("Round 1", current_text)

    def test_character_text_excludes_beliefs(self):
        _, character_text, _, _, _ = format_turn_context(trajectory(), 1)

        self.assertIn("Standing by the door", character_text)
        self.assertIn("Nervous, alert", character_text)
        self.assertNotIn("self_belief", character_text)
        self.assertNotIn("environment_belief", character_text)

    def test_prompt_is_condition_blind(self):
        prompt = build_h1_prompt(trajectory("P"), 1)

        self.assertNotIn("context_condition", prompt)
        self.assertNotIn("primary_four_level", prompt)
        self.assertIn("Warn Luna about the incoming patrol.", prompt)


class H1PromptRuleTests(TestCase):
    def test_prompt_treats_dodging_as_context_use_failure(self):
        prompt = build_h1_prompt(trajectory(), 1)

        self.assertIn("Dodging is a failure", prompt)
        self.assertIn("Going along with the player counts as a claim", prompt)
        self.assertIn("Never write a supplied fact as the claim", prompt)

    def test_prompt_examples_do_not_reuse_pilot_scene_content(self):
        # The examples must not echo the scenes being evaluated, or the judge is
        # primed on the exact trials it scores.
        from evaluate import H1_METRIC_CRITERIA, H1_RESPONSE_FORMAT

        rubric = H1_METRIC_CRITERIA + H1_RESPONSE_FORMAT
        for pilot_term in ("Shrieking", "Luna", "Neville", "Hogwarts", "moon",
                           "McGonagall", "Niffler", "Dumbledore", "Dementor"):
            self.assertNotIn(pilot_term, rubric)


class H1PromptExampleTests(TestCase):
    def test_every_format_example_is_valid_and_writes_evidence_before_decision(self):
        import re
        from evaluate import H1_RESPONSE_FORMAT

        blocks = re.findall(r"\n(\{\n.*?\n\})\n", H1_RESPONSE_FORMAT, re.S)[1:]
        self.assertGreaterEqual(len(blocks), 6)
        decisions = []
        for block in blocks:
            self.assertNotRegex(block, r'"decision": "[A-Z]+", "(evidence|contradicted_round)"')
            example = json.loads(block)
            dialogue = " ".join(c["quote"] for c in example["world_consistency"]["claims"])
            decisions.append(parse_h1_response(json.dumps(example), dialogue)["no_contradiction"]["decision"])
        # At least one full example shows No Contradiction failing on a fact only
        # the player established, which the judge previously never saw in full.
        self.assertGreaterEqual(decisions.count("FAIL"), 3)


class ParseH1ResponseTests(TestCase):
    def test_parses_valid_response(self):
        parsed = parse_h1_response(VALID_H1_RESPONSE, NPC_DIALOGUE)

        self.assertEqual("PASS", parsed["context_use"]["decision"])
        self.assertEqual("PASS", parsed["world_consistency"]["decision"])
        self.assertEqual(1, len(parsed["world_consistency"]["claims"]))
        self.assertEqual("NA", parsed["no_contradiction"]["decision"])
        self.assertIsNone(parsed["no_contradiction"]["contradicted_round"])

    def test_parses_response_wrapped_in_a_markdown_json_fence(self):
        # Reproduces a real gpt-4o failure: "Expecting value: line 1 column 1 (char 0)"
        # is not unique to an empty response -- it also fires for any text that
        # doesn't start with valid JSON at position 0, including a ```json fence some
        # models add despite being told to return only the JSON object.
        fenced = f"```json\n{VALID_H1_RESPONSE}\n```"

        parsed = parse_h1_response(fenced, NPC_DIALOGUE)

        self.assertEqual("PASS", parsed["context_use"]["decision"])

    def test_parses_response_with_a_conversational_preamble(self):
        prefaced = f"Sure, here is the evaluation:\n{VALID_H1_RESPONSE}"

        parsed = parse_h1_response(prefaced, NPC_DIALOGUE)

        self.assertEqual("PASS", parsed["context_use"]["decision"])

    def test_still_rejects_genuinely_non_json_text(self):
        with self.assertRaisesRegex(ValueError, "did not return valid JSON"):
            parse_h1_response("not json at all, no braces here", NPC_DIALOGUE)

    def test_world_consistency_decision_is_na_when_claims_empty(self):
        payload = json.loads(VALID_H1_RESPONSE)
        payload["world_consistency"] = {"claims": []}

        parsed = parse_h1_response(json.dumps(payload), NPC_DIALOGUE)

        self.assertEqual("NA", parsed["world_consistency"]["decision"])

    def test_world_consistency_decision_is_fail_when_any_claim_inconsistent(self):
        # Reproduces the real bug: a response with several claims, only one false.
        # FAIL must win even though most claims (and the chosen "safe" one) are true.
        payload = json.loads(VALID_H1_RESPONSE)
        payload["world_consistency"] = {
            "claims": [
                {
                    "claim": "the moon is bright",
                    "quote": "the moon is bright",
                    "consistent": False,
                    "checked_against": "Moon is hidden behind clouds",
                },
                {
                    "claim": "they should keep quiet",
                    "quote": "keep quiet",
                    "consistent": True,
                    "checked_against": NO_SUPPLIED_FACT,
                },
            ]
        }

        parsed = parse_h1_response(json.dumps(payload), NPC_DIALOGUE)

        self.assertEqual("FAIL", parsed["world_consistency"]["decision"])
        self.assertEqual(2, len(parsed["world_consistency"]["claims"]))

    def test_world_consistency_rejects_a_decision_field(self):
        # The judge must not be able to self-report a decision for this metric at all.
        payload = json.loads(VALID_H1_RESPONSE)
        payload["world_consistency"] = {"decision": "PASS", "claims": []}

        with self.assertRaisesRegex(ValueError, "exactly one key: claims"):
            parse_h1_response(json.dumps(payload), NPC_DIALOGUE)

    def test_world_consistency_rejects_claim_missing_text(self):
        payload = json.loads(VALID_H1_RESPONSE)
        payload["world_consistency"] = {
            "claims": [{"quote": "Keep your voice down", "consistent": True, "checked_against": NO_SUPPLIED_FACT}]
        }

        with self.assertRaisesRegex(ValueError, "non-empty claim text"):
            parse_h1_response(json.dumps(payload), NPC_DIALOGUE)

    def test_world_consistency_requires_checked_against_when_inconsistent(self):
        payload = json.loads(VALID_H1_RESPONSE)
        payload["world_consistency"] = {
            "claims": [{"claim": "the moon is bright", "consistent": False, "checked_against": None}]
        }

        with self.assertRaisesRegex(ValueError, "requires non-empty checked_against"):
            parse_h1_response(json.dumps(payload), NPC_DIALOGUE)

    def test_world_consistency_requires_checked_against_when_consistent_too(self):
        # checked_against is required on every claim now, not only inconsistent ones --
        # see the 2026-09-16 provenance entry (required-on-every-claim redesign).
        payload = json.loads(VALID_H1_RESPONSE)
        payload["world_consistency"] = {
            "claims": [{"claim": "safe claim", "consistent": True, "checked_against": None}]
        }

        with self.assertRaisesRegex(ValueError, "requires non-empty checked_against"):
            parse_h1_response(json.dumps(payload), NPC_DIALOGUE)

    def test_world_consistency_rejects_no_supplied_fact_sentinel_when_inconsistent(self):
        # The escape valve for "nothing addresses this claim" only makes sense for a
        # true claim -- an inconsistent claim must always name what it actually conflicts with.
        payload = json.loads(VALID_H1_RESPONSE)
        payload["world_consistency"] = {
            "claims": [{"claim": "the moon is bright", "consistent": False, "checked_against": NO_SUPPLIED_FACT}]
        }

        with self.assertRaisesRegex(ValueError, "no-supplied-fact placeholder"):
            parse_h1_response(json.dumps(payload), NPC_DIALOGUE)

    def test_world_consistency_requires_quote(self):
        payload = json.loads(VALID_H1_RESPONSE)
        payload["world_consistency"] = {
            "claims": [
                {
                    "claim": "safe claim",
                    "consistent": True,
                    "checked_against": NO_SUPPLIED_FACT,
                }
            ]
        }

        with self.assertRaisesRegex(ValueError, "requires a non-empty quote"):
            parse_h1_response(json.dumps(payload), NPC_DIALOGUE)

    def test_world_consistency_flags_a_quote_that_does_not_appear_in_the_response(self):
        # A fabricated/misrepresenting quote is flagged, not rejected -- it's a
        # content-quality signal, not a format violation, so it must not trigger a retry.
        payload = json.loads(VALID_H1_RESPONSE)
        payload["world_consistency"] = {
            "claims": [
                {
                    "claim": "safe claim",
                    "quote": "this exact phrase was never said",
                    "consistent": True,
                    "checked_against": NO_SUPPLIED_FACT,
                }
            ]
        }

        parsed = parse_h1_response(json.dumps(payload), NPC_DIALOGUE)

        self.assertEqual("PASS", parsed["world_consistency"]["decision"])
        self.assertFalse(parsed["world_consistency"]["claims"][0]["quote_verified"])

    def test_world_consistency_verifies_a_quote_that_matches_modulo_whitespace_and_curly_quotes(self):
        payload = json.loads(VALID_H1_RESPONSE)
        payload["world_consistency"] = {
            "claims": [
                {
                    "claim": "safe claim",
                    "quote": "Keep   your\nvoice down",
                    "consistent": True,
                    "checked_against": NO_SUPPLIED_FACT,
                }
            ]
        }

        parsed = parse_h1_response(json.dumps(payload), NPC_DIALOGUE)

        self.assertTrue(parsed["world_consistency"]["claims"][0]["quote_verified"])

    def test_world_consistency_accepts_checked_against_when_consistent(self):
        # A judge citing the supporting fact for a true claim is valid and useful --
        # only citing nothing (null) is no longer valid at all; see the 2026-09-16
        # provenance entries (checked_against redesign, then required-on-every-claim).
        payload = json.loads(VALID_H1_RESPONSE)
        payload["world_consistency"] = {
            "claims": [
                {
                    "claim": "safe claim",
                    "quote": "Keep your voice down",
                    "consistent": True,
                    "checked_against": "Scene: some supporting fact",
                },
            ]
        }

        parsed = parse_h1_response(json.dumps(payload), NPC_DIALOGUE)

        self.assertEqual("PASS", parsed["world_consistency"]["decision"])
        self.assertEqual(
            "Scene: some supporting fact",
            parsed["world_consistency"]["claims"][0]["checked_against"],
        )

    def test_world_consistency_accepts_no_supplied_fact_sentinel_when_consistent(self):
        payload = json.loads(VALID_H1_RESPONSE)
        payload["world_consistency"] = {
            "claims": [
                {
                    "claim": "safe claim",
                    "quote": "Keep your voice down",
                    "consistent": True,
                    "checked_against": NO_SUPPLIED_FACT,
                }
            ]
        }

        parsed = parse_h1_response(json.dumps(payload), NPC_DIALOGUE)

        self.assertEqual("PASS", parsed["world_consistency"]["decision"])
        self.assertEqual(
            NO_SUPPLIED_FACT,
            parsed["world_consistency"]["claims"][0]["checked_against"],
        )

    def test_rejects_invalid_json(self):
        with self.assertRaisesRegex(ValueError, "valid JSON"):
            parse_h1_response("not json", NPC_DIALOGUE)

    def test_rejects_missing_metric_key(self):
        payload = json.loads(VALID_H1_RESPONSE)
        del payload["world_consistency"]
        with self.assertRaisesRegex(ValueError, "exactly the keys"):
            parse_h1_response(json.dumps(payload), NPC_DIALOGUE)

    def test_rejects_bad_decision_value(self):
        payload = json.loads(VALID_H1_RESPONSE)
        payload["context_use"]["decision"] = "MAYBE"
        with self.assertRaisesRegex(ValueError, "PASS, FAIL, or NA"):
            parse_h1_response(json.dumps(payload), NPC_DIALOGUE)

    def test_requires_evidence_when_pass_or_fail(self):
        payload = json.loads(VALID_H1_RESPONSE)
        payload["context_use"]["evidence"] = None
        with self.assertRaisesRegex(ValueError, "requires evidence"):
            parse_h1_response(json.dumps(payload), NPC_DIALOGUE)

    def test_rejects_evidence_when_na(self):
        payload = json.loads(VALID_H1_RESPONSE)
        payload["no_contradiction"]["evidence"] = "should not be here"
        with self.assertRaisesRegex(ValueError, "must be null"):
            parse_h1_response(json.dumps(payload), NPC_DIALOGUE)

    def test_requires_contradicted_round_when_fail(self):
        payload = json.loads(VALID_H1_RESPONSE)
        payload["no_contradiction"] = {
            "decision": "FAIL",
            "evidence": "Contradicts round 2.",
            "contradicted_round": None,
        }
        with self.assertRaisesRegex(ValueError, "integer contradicted_round"):
            parse_h1_response(json.dumps(payload), NPC_DIALOGUE)

    def test_rejects_contradicted_round_when_not_fail(self):
        payload = json.loads(VALID_H1_RESPONSE)
        payload["no_contradiction"]["contradicted_round"] = 1
        with self.assertRaisesRegex(ValueError, "null unless"):
            parse_h1_response(json.dumps(payload), NPC_DIALOGUE)


class ComputeConsistencyTests(TestCase):
    def test_averages_applicable_scores(self):
        decisions = {
            "context_use": {"decision": "PASS"},
            "world_consistency": {"decision": "FAIL"},
            "no_contradiction": {"decision": "NA"},
        }
        self.assertEqual(0.5, compute_consistency(decisions))

    def test_returns_none_when_all_na(self):
        decisions = {
            "context_use": {"decision": "NA"},
            "world_consistency": {"decision": "NA"},
            "no_contradiction": {"decision": "NA"},
        }
        self.assertIsNone(compute_consistency(decisions))

    def test_decision_to_score_mapping(self):
        self.assertEqual({"PASS": 1, "FAIL": 0, "NA": None}, DECISION_TO_SCORE)


class EvaluateH1TurnTests(TestCase):
    def _response_citing_player(self, consistent):
        return json.dumps({
            "context_use": {"decision": "PASS", "evidence": "Uses the patrol fact."},
            "world_consistency": {"claims": [{
                "quote": "Keep your voice down",
                "claim": "the player should keep quiet",
                "consistent": consistent,
                "checked_against": "Round 2 — Player: 'we should be quiet'",
            }]},
            "no_contradiction": {"decision": "NA", "contradicted_round": None, "evidence": None},
        })

    def test_consistent_claim_citing_player_is_repaired_and_flagged(self):
        judge = FakeJudge([self._response_citing_player(True)])

        result = evaluate_h1_turn(trajectory(), 1, judge, retries=3)

        self.assertEqual(1, len(judge.prompts))
        claim = result["decisions"]["world_consistency"]["claims"][0]
        self.assertEqual(NO_SUPPLIED_FACT, claim["checked_against"])
        self.assertTrue(claim["checked_against_repaired"])
        self.assertEqual(1.0, result["consistency"])

    def test_rubric_versions_rebuild_older_prompts(self):
        record = trajectory()
        record["player"] = {"name": "Luna Lovegood"}
        v11, v13, v14 = (build_h1_prompt(record, 1, v) for v in (11, 13, 14))

        self.assertIn("getting at least one right and none wrong is PASS", v11)
        self.assertNotIn("Characters present:", v11)
        self.assertNotIn("concession phrased as a rebuttal", v11)
        self.assertIn("Characters present:", v13)
        self.assertIn("concession phrased as a rebuttal", v13)
        self.assertNotIn("the decision is FAIL. ", v13.split("[World Consistency]")[0][-400:])
        self.assertNotIn("acknowledging the question without answering it", v13)
        self.assertIn("acknowledging the question without answering it", v14)
        self.assertEqual(v14, build_h1_prompt(record, 1))
        with self.assertRaises(ValueError):
            build_h1_prompt(record, 1, 12)

    def test_change_13_rubric_and_player_name(self):
        record = trajectory()
        record["player"] = {"name": "Luna Lovegood"}
        prompt = build_h1_prompt(record, 1)

        self.assertIn("Characters present:", prompt)
        self.assertIn("Luna Lovegood, who speaks the lines marked Player", prompt)
        self.assertIn("even if the response states another of them wrongly", prompt)
        self.assertIn("a concession phrased as a rebuttal still goes along with the claim", prompt)
        self.assertIn("A concession phrased as a rebuttal is also acceptance", prompt)
        # Change 14: Context Use decision must follow its evidence; non-answers are dodges.
        self.assertIn("if your evidence says the response accepts, goes along with, concedes, or does not correct the player's claim, the decision is FAIL", prompt)
        self.assertIn("acknowledging the question without answering it", prompt)
        # Records without a player profile render as before.
        self.assertNotIn("Characters present:", build_h1_prompt(trajectory(), 1))

    def test_quote_check_ignores_letter_case(self):
        self.assertTrue(_quote_is_verbatim("we've got each other", "We've got each other's backs."))
        self.assertFalse(_quote_is_verbatim("we have each other", "We've got each other's backs."))

    def test_round_one_ignores_malformed_no_contradiction(self):
        # Qwen2.5-14B (pilot 1 t05 S) answered PASS with no evidence on round 1 four
        # times; the answer is replaced by NA anyway, so it must not fail the turn.
        payload = json.loads(VALID_H1_RESPONSE)
        payload["no_contradiction"] = {"evidence": None, "contradicted_round": None, "decision": "PASS"}

        parsed = parse_h1_response(json.dumps(payload), NPC_DIALOGUE, round_number=1)

        self.assertEqual("NA", parsed["no_contradiction"]["decision"])
        with self.assertRaisesRegex(ValueError, "requires evidence"):
            parse_h1_response(json.dumps(payload), NPC_DIALOGUE, round_number=2)

    def test_turn_records_attempts_and_time(self):
        judge = FakeJudge(["not json", self._response_citing_player(True)])

        result = evaluate_h1_turn(trajectory(), 1, judge, retries=3)

        self.assertEqual(2, result["judge_attempts"])
        self.assertIsInstance(result["judge_seconds"], float)
        self.assertGreaterEqual(result["judge_seconds"], 0)

    def test_conversation_conflict_moves_out_of_world_consistency(self):
        # Pilot 1 t11 U R8: the judge kept marking the claim inconsistent against
        # "Round 2: ..." while No Contradiction correctly failed against round 2.
        record = trajectory()
        record["turns"][1]["npc_dialogue"] = "Um, yes, two knocks—just like we practiced."
        response = json.dumps({
            "context_use": {"decision": "FAIL", "evidence": "goes along with the false claim."},
            "world_consistency": {"claims": [{
                "quote": "Um, yes, two knocks",
                "claim": "the signal is two knocks",
                "consistent": False,
                "checked_against": "Round 2: Signal = three taps on the window.",
            }]},
            "no_contradiction": {
                "decision": "FAIL",
                "contradicted_round": 1,
                "evidence": "Round 1: 'three taps on the window.' This response: 'two knocks'.",
            },
        })
        judge = FakeJudge([response])

        result = evaluate_h1_turn(record, 2, judge, retries=3)

        self.assertEqual(1, len(judge.prompts))
        decisions = result["decisions"]
        claim = decisions["world_consistency"]["claims"][0]
        self.assertEqual("PASS", decisions["world_consistency"]["decision"])
        self.assertEqual("FAIL", decisions["no_contradiction"]["decision"])
        self.assertTrue(claim["checked_against_repaired"])
        self.assertEqual(
            {"consistent": False, "checked_against": "Round 2: Signal = three taps on the window."},
            claim["original_verdict"],
        )

    def test_consistent_claim_citing_a_conversation_round_is_repaired(self):
        response = json.dumps({
            "context_use": {"decision": "PASS", "evidence": "Uses the patrol fact."},
            "world_consistency": {"claims": [{
                "quote": "Keep your voice down",
                "claim": "the player should keep quiet",
                "consistent": True,
                "checked_against": "Round 2: Signal = three taps on the window",
            }]},
            "no_contradiction": {"decision": "NA", "contradicted_round": None, "evidence": None},
        })
        judge = FakeJudge([response])

        result = evaluate_h1_turn(trajectory(), 1, judge, retries=3)

        claim = result["decisions"]["world_consistency"]["claims"][0]
        self.assertEqual(NO_SUPPLIED_FACT, claim["checked_against"])
        self.assertTrue(claim["checked_against_repaired"])

    def test_prompt_treats_earlier_player_facts_as_established(self):
        prompt = build_h1_prompt(trajectory(), 1)

        self.assertIn("a statement of fact the player made in an earlier turn is established", prompt)
        self.assertIn("the earlier statement still holds", prompt)
        self.assertIn("The player's current line is never evidence", prompt)
        self.assertIn("Agreeing with the character's own earlier statement does not excuse a contradiction", prompt)

    def test_prompt_requires_checking_misquotes_against_own_earlier_turns(self):
        prompt = build_h1_prompt(trajectory(), 1)

        self.assertIn("Check every claim in the current response", prompt)
        self.assertIn("agreeing with a misquote of its own earlier words is a contradiction", prompt)
        self.assertIn("Never cite the player's lines", prompt)

    def test_retries_until_valid_response(self):
        judge = FakeJudge(["not json", "still not json", VALID_H1_RESPONSE])

        record = trajectory()
        record["trial_type"] = 1
        result = evaluate_h1_turn(record, 1, judge, retries=3)

        self.assertEqual(1, result["trial_type"])
        self.assertEqual(3, len(judge.prompts))
        self.assertEqual("H1", result["hypothesis"])
        self.assertEqual("trial-001", result["trial_id"])
        self.assertEqual("pilot-001", result["pilot_id"])
        self.assertEqual(1, result["round"])
        self.assertEqual(1.0, result["consistency"])

    def test_world_consistency_fail_derived_from_one_bad_claim_among_several(self):
        # End-to-end reproduction of the real bug: a response makes several claims,
        # only one of which is false. FAIL must still win, and the parsed claim list
        # must be visible in the output rather than collapsed into one evidence string.
        response = json.dumps({
            "context_use": {"decision": "PASS", "evidence": "Uses the elicited fact."},
            "world_consistency": {
                "claims": [
                    {
                        "claim": "the moon is bright",
                        "quote": "the moon is bright",
                        "consistent": False,
                        "checked_against": "Moon is hidden behind clouds",
                    },
                    {
                        "claim": "they should keep quiet",
                        "quote": "keep quiet",
                        "consistent": True,
                        "checked_against": NO_SUPPLIED_FACT,
                    },
                ]
            },
            "no_contradiction": {
                "decision": "PASS",
                "contradicted_round": None,
                "evidence": "Consistent with round 1.",
            },
        })
        judge = FakeJudge([response])

        result = evaluate_h1_turn(trajectory(), 2, judge, retries=1)

        world_consistency = result["decisions"]["world_consistency"]
        self.assertEqual("FAIL", world_consistency["decision"])
        self.assertEqual(0, world_consistency["score"])
        self.assertEqual(2, len(world_consistency["claims"]))
        self.assertNotIn("evidence", world_consistency)
        # consistency must reflect the FAIL, not be inflated by the other two PASSes.
        self.assertEqual(2 / 3, result["consistency"])

    def test_a_fabricated_quote_is_flagged_not_retried(self):
        # An unverifiable quote is a content-quality problem, not a format violation --
        # it must not consume a retry attempt, unlike every other validation failure.
        response = json.dumps({
            "context_use": {"decision": "PASS", "evidence": "Uses the elicited fact."},
            "world_consistency": {
                "claims": [
                    {
                        "claim": "the player should keep quiet",
                        "quote": "a line the NPC never actually said",
                        "consistent": True,
                        "checked_against": NO_SUPPLIED_FACT,
                    }
                ]
            },
            "no_contradiction": {"decision": "NA", "contradicted_round": None, "evidence": None},
        })
        judge = FakeJudge([response])

        result = evaluate_h1_turn(trajectory(), 1, judge, retries=3)

        self.assertEqual(1, len(judge.prompts))
        self.assertFalse(
            result["decisions"]["world_consistency"]["claims"][0]["quote_verified"]
        )
        self.assertEqual("PASS", result["decisions"]["world_consistency"]["decision"])

    def test_round_one_no_contradiction_is_forced_to_na_even_if_judge_says_pass(self):
        # Reproduces a real judge failure mode: at round 1 the judge sometimes reasons
        # correctly ("no prior turn to contradict") but mislabels it PASS instead of NA.
        mislabeled_response = json.dumps({
            "context_use": {"decision": "PASS", "evidence": "Uses the elicited fact."},
            "world_consistency": {"claims": []},
            "no_contradiction": {
                "decision": "PASS",
                "contradicted_round": None,
                "evidence": "This is the first turn; no prior statements to contradict.",
            },
        })
        judge = FakeJudge([mislabeled_response])

        result = evaluate_h1_turn(trajectory(), 1, judge, retries=1)

        self.assertEqual(
            {"decision": "NA", "score": None, "evidence": None, "contradicted_round": None},
            result["decisions"]["no_contradiction"],
        )
        # consistency must reflect the forced NA (averaging only the other two PASSes),
        # not whatever the judge originally said.
        self.assertEqual(1.0, result["consistency"])

    def test_no_contradiction_is_not_overridden_after_round_one(self):
        round_two_fail_response = json.dumps({
            "context_use": {"decision": "NA", "evidence": None},
            "world_consistency": {
                "claims": [
                    {
                        "claim": "safe claim",
                        "quote": "I've got your back",
                        "consistent": True,
                        "checked_against": NO_SUPPLIED_FACT,
                    }
                ]
            },
            "no_contradiction": {
                "decision": "FAIL",
                "contradicted_round": 1,
                "evidence": "Round 1: 'Keep your voice down.' This response: 'I've got your back, I promise.'",
            },
        })
        judge = FakeJudge([round_two_fail_response])

        result = evaluate_h1_turn(trajectory(), 2, judge, retries=1)

        self.assertEqual("FAIL", result["decisions"]["no_contradiction"]["decision"])
        self.assertEqual(1, result["decisions"]["no_contradiction"]["contradicted_round"])

    def test_raises_after_exhausting_retries(self):
        judge = FakeJudge(["bad", "still bad"])

        with self.assertRaisesRegex(ValueError, "did not return a valid H1 decision"):
            evaluate_h1_turn(trajectory(), 1, judge, retries=2)

    def test_retries_past_an_empty_judge_response(self):
        # A deterministic empty completion must be retried like any other malformed
        # response, not treated as "" and passed straight to json.loads.
        judge = FakeJudge([
            ("", {"finish_reason": "content_filter"}, {}),
            VALID_H1_RESPONSE,
        ])

        result = evaluate_h1_turn(trajectory(), 1, judge, retries=2)

        self.assertEqual(1.0, result["consistency"])

    def test_final_error_surfaces_finish_reason_when_always_empty(self):
        judge = FakeJudge([("", {"finish_reason": "content_filter"}, {})] * 2)

        with self.assertRaisesRegex(ValueError, r"finish_reason='content_filter'"):
            evaluate_h1_turn(trajectory(), 1, judge, retries=2)


class EvaluateH2TrialTests(TestCase):
    def test_tags_result_with_hypothesis(self):
        valid_scores = "\n".join(
            f"{metric}: 4"
            for metric in (
                "Knowledge Accuracy",
                "Emotional Expression",
                "Personality Traits",
                "Behavioral Accuracy",
                "Immersion",
                "Adaptability",
                "Behavioral Coherence",
            )
        )
        judge = FakeJudge(["No serious issue.", valid_scores])

        record = trajectory()
        record["trial_type"] = 2
        result = evaluate_h2_trial(record, judge, score_retries=2)

        self.assertEqual("H2", result["hypothesis"])
        self.assertEqual(4.0, result["average"])
        self.assertEqual(2, result["trial_type"])


if __name__ == "__main__":
    import unittest

    unittest.main()
