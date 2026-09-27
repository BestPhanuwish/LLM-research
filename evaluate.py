"""Evaluate controlled dialogue trajectories against H1 (per-turn consistency)
and H2 (per-trial realism), one command for a whole pilot run.

H1 is original research code: per-turn Context Use / World Consistency /
No Contradiction, binary PASS/FAIL/N/A with quoted evidence, no reference
response required. See docs/research-contract.md and docs/characterbox-
provenance.md for the design history and the CharacterCraft reference-
dependency finding that ruled out a CharacterCraft-inspired H1/H2 rubric.

H2 reuses evaluate_characterbox.py's CharacterBox-compatible seven-metric
trajectory evaluator unchanged (imported, not re-implemented) — see that
module's header for its own CharacterBox provenance notice.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from yacs.config import CfgNode

from evaluate_characterbox import (
    evaluate_trajectory as characterbox_evaluate_trajectory,
    judge_text,
    load_trajectory_run,
)
from utils import utils


NO_SUPPLIED_FACT = "No supplied fact addresses this claim."

H1_METRIC_CRITERIA = f"""
[Context Use]
Does the response draw on a supplied scene or character fact that the player's current turn made relevant?
- PASS: The player's turn calls for a fact present in the supplied scene, character, or action information, and the response reflects it (a paraphrase or clear reference counts, not just a verbatim quote).
- FAIL: The player's turn calls for a supplied fact, and the response ignores it, dodges, or answers without incorporating it.
- NA: The player's turn does not require or naturally call for any specific supplied fact (casual talk, no direct question, purely emotional exchange).
Steps: read the current turn plus prior history; decide whether answering in character plausibly requires a specific supplied fact; if none, mark NA; if one exists, check whether the response uses it; quote the fact and the relevant part of the response as evidence.

[World Consistency]
Does the response avoid making any claim that contradicts the supplied scene, character, or action information?
List every separate factual claim the response makes, in the order they appear — do not stop at the first one, and do not select only the safest or most obviously-true claim. A "claim" is anything the response asserts as true (about the scene, the world, another character, or itself), not just the one the player's line was probing for; "claim" may paraphrase or summarize what is being asserted. For every claim, also give "quote" — the exact word-for-word fragment of the character's response that this claim is drawn from, copied verbatim character-for-character, not paraphrased, summarized, or reworded, so it can be checked against the actual response text. For each claim, decide whether it is consistent with the supplied scene/character/action information, and always name the specific supplied fact you checked it against in "checked_against" — every claim requires this, not only inconsistent ones. When the claim is inconsistent, this must be the fact it conflicts with (wrong location, inconsistent trait, denies something already established, references an ability/item/person inconsistent with what is supplied, or asserts something no supplied fact supports and the supplied facts imply otherwise). When the claim is consistent, cite the specific supplied fact that supports it; if no supplied fact addresses this claim at all, write the exact text "{NO_SUPPLIED_FACT}" instead of leaving it blank or inventing one. Never use that exact text for an inconsistent claim — an inconsistent claim always names a real, specific fact it conflicts with. If the response makes no checkable claim at all, the claim list is empty.
Do not report a decision label yourself for this metric — only the claim list. The overall decision is derived automatically from it: any single inconsistent claim makes the whole turn FAIL, regardless of how many other claims were consistent.

[No Contradiction]
Does the response avoid contradicting something this character already said earlier in this conversation?
- PASS: The response is consistent with everything this character has said in prior turns.
- FAIL: The response contradicts a specific claim or commitment the character made in an earlier turn.
- NA: This is the character's first turn — no earlier turn exists to contradict.
Steps: review the character's own prior turns (not the player's lines); check whether the current response conflicts with anything said before; if it does, mark FAIL, note which round it contradicts, and quote both statements; if not, mark PASS and quote the current response plus the specific earlier turn(s) it was checked against, even though they do not conflict; if this is round 1, mark NA.
Evidence is required on every PASS and every FAIL for Context Use and No Contradiction, with no exceptions — including a PASS confirming consistency. "No contradiction found" is never acceptable evidence on its own; always name or quote the specific prior turn(s) that were checked. World Consistency instead reports its full claim list, as described above — every claim needs its own consistent/inconsistent judgment, not a single overall justification chosen after the fact.
"""

H1_RESPONSE_FORMAT = f"""
[Response Format]
Return exactly one JSON object with this shape and nothing else:
{{
  "context_use": {{"decision": "PASS|FAIL|NA", "evidence": "quote(s) or null"}},
  "world_consistency": {{"claims": [{{"claim": "text", "quote": "exact verbatim fragment of the response this claim is drawn from", "consistent": true|false, "checked_against": "supplied fact text, or exactly \\"{NO_SUPPLIED_FACT}\\""}}]}},
  "no_contradiction": {{"decision": "PASS|FAIL|NA", "contradicted_round": <int or null>, "evidence": "quote(s) or null"}}
}}
"evidence" must be non-null whenever decision is PASS or FAIL, and null when decision is NA. "contradicted_round" is only ever a number when no_contradiction's decision is FAIL; otherwise it is null. "world_consistency" carries no "decision" field at all — list every claim in "claims" (empty list if the response makes none); "quote" is required (a non-empty, verbatim, word-for-word fragment of the response, never null) on every claim; "checked_against" is required (a non-empty string, never null) on every claim. When "consistent" is false it must name the specific fact the claim conflicts with. When "consistent" is true it may cite a supporting fact, or must be exactly "{NO_SUPPLIED_FACT}" when no supplied fact addresses the claim at all.

[Response Format Example — a response that contradicts an earlier turn]
{{
  "context_use": {{"decision": "PASS", "evidence": "Elicited fact: Location = The Shrieking Shack, Hogwarts. Response: 'We're at the Shrieking Shack, should be safe enough.'"}},
  "world_consistency": {{"claims": [{{"claim": "we're at the Shrieking Shack", "quote": "We're at the Shrieking Shack", "consistent": true, "checked_against": "Scene: Location = The Shrieking Shack, Hogwarts"}}]}},
  "no_contradiction": {{"decision": "FAIL", "contradicted_round": 1, "evidence": "Round 1: 'I've got your back, I promise.' This response: 'I don't think I can promise anything right now.'"}}
}}

[Response Format Example — a response that stays consistent with an earlier turn, with no supplied fact addressing that one claim]
{{
  "context_use": {{"decision": "NA", "evidence": null}},
  "world_consistency": {{"claims": [{{"claim": "the coast is clear", "quote": "it's safe now", "consistent": true, "checked_against": "{NO_SUPPLIED_FACT}"}}]}},
  "no_contradiction": {{"decision": "PASS", "contradicted_round": null, "evidence": "Round 1: 'I've got your back, I promise.' This response: 'Come on, it's safe now.' Both express the same reassuring commitment; no conflict."}}
}}

[Response Format Example — several claims, only one of them false]
A response like "Yeah, it's bright, but let's not let it draw any eyes to us, keep your voice down" makes two separate claims: that the moon/night is bright, and that they should keep quiet. Only the first is checkable against a supplied fact, and it is false — do not let the second, true, safer claim excuse the first:
{{
  "context_use": {{"decision": "PASS", "evidence": "Elicited fact: visibility tonight. Response: 'Yeah, it's bright.'"}},
  "world_consistency": {{"claims": [
    {{"claim": "it is bright / good visibility tonight", "quote": "it's bright", "consistent": false, "checked_against": "Scene description: the moon is hidden behind clouds"}},
    {{"claim": "they should keep their voices down", "quote": "keep your voice down", "consistent": true, "checked_against": "Action Reference: keep her voice down"}}
  ]}},
  "no_contradiction": {{"decision": "PASS", "contradicted_round": null, "evidence": "Round 1: 'let's stick to the plan.' This response: 'let's not draw attention.' Consistent with the earlier caution."}}
}}

[Response]
"""

DECISION_TO_SCORE = {"PASS": 1, "FAIL": 0, "NA": None}


def format_turn_context(record, round_number):
    """Render condition-blind scene/character/history context for one turn,
    truncated to rounds <= round_number so no future turn is visible."""
    scene = record["scene"]
    target = record["target"]
    scene_text = (
        f"Event: {scene['event']}\n"
        f"Time: {scene['time']}\n"
        f"Location: {scene['location']}\n"
        f"Description: {scene['description']}\n"
    )
    character_text = (
        f"Position: {target['position']}\n"
        f"Current State: {target['states']}\n"
        f"Description: {target['description']}\n"
    )
    visible_turns = [turn for turn in record["turns"] if turn["round"] <= round_number]
    prior_turns, current_turn = visible_turns[:-1], visible_turns[-1]

    prior_lines = []
    for turn in prior_turns:
        prior_lines.append(f"Round {turn['round']} — Player: \"{turn['player_dialogue']}\"")
        prior_lines.append(
            f"Round {turn['round']} — {target['name']}: \"{turn['npc_dialogue']}\""
        )
    prior_text = "\n".join(prior_lines) if prior_lines else "(none — this is the first turn)"

    current_text = (
        f"Round {current_turn['round']} — Player: \"{current_turn['player_dialogue']}\"\n"
        f"Round {current_turn['round']} — {target['name']}: \"{current_turn['npc_dialogue']}\""
    )
    return scene_text, character_text, record["action_reference"], prior_text, current_text


def build_h1_prompt(record, round_number):
    scene_text, character_text, action_reference, prior_text, current_text = (
        format_turn_context(record, round_number)
    )
    name = record["target"]["name"]
    return f"""Please evaluate one turn of {name}'s dialogue against the supplied scene and character information, and against the character's own earlier turns in this conversation.

[Scene]
{scene_text}
[Character — {name}]
{character_text}
[Action Reference]
{action_reference}

[Prior turns]
{prior_text}

[Current turn — evaluate this response only]
{current_text}
{H1_METRIC_CRITERIA}{H1_RESPONSE_FORMAT}"""


_QUOTE_NORMALIZE_TABLE = str.maketrans({
    "‘": "'", "’": "'", "“": '"', "”": '"',
})


def _normalize_quote_text(text):
    """Collapse whitespace and fold curly quotes to straight ones so a judge's
    otherwise-verbatim quote isn't flagged unverified over cosmetic differences."""
    return " ".join(text.translate(_QUOTE_NORMALIZE_TABLE).split())


def _quote_is_verbatim(quote, npc_dialogue):
    """Whether `quote` actually appears in the NPC's real dialogue for this turn,
    modulo whitespace/curly-quote normalization -- catches a claim's "quote" being
    paraphrased or invented outright instead of copied from the actual response."""
    return _normalize_quote_text(quote) in _normalize_quote_text(npc_dialogue)


def parse_world_consistency_claims(entry, npc_dialogue):
    """Parse World Consistency's claim list and derive its PASS/FAIL/NA decision: NA if
    there are no claims, FAIL if any claim is inconsistent, PASS otherwise. The judge is
    never asked for, and cannot directly set, the decision label itself for this metric
    — deriving it from the claim list avoids the same self-reported-label-vs-reasoning
    mismatch that round-1 no_contradiction had before it was forced in code (see the
    2026-09-09 provenance entry); this applies the same lesson from the start instead of
    patching it after the fact. See the 2026-09-16 provenance entry.

    Each claim also carries a "quote" -- the verbatim response fragment it was drawn
    from -- checked against `npc_dialogue` and recorded as "quote_verified". An
    unverified quote is flagged in the output rather than rejected/retried: it means
    the judge's "claim" may be paraphrasing or misrepresenting what was actually said,
    which is worth surfacing, but is a content-quality signal, not a format violation
    the retry loop is meant to correct."""
    if not isinstance(entry, dict) or set(entry) != {"claims"}:
        raise ValueError("world_consistency must be an object with exactly one key: claims")
    claims = entry["claims"]
    if not isinstance(claims, list):
        raise ValueError("world_consistency.claims must be a list")

    parsed_claims = []
    any_inconsistent = False
    for index, claim_entry in enumerate(claims):
        if not isinstance(claim_entry, dict):
            raise ValueError(f"world_consistency.claims[{index}] must be an object")
        claim_text = claim_entry.get("claim")
        if not isinstance(claim_text, str) or not claim_text.strip():
            raise ValueError(f"world_consistency.claims[{index}] requires non-empty claim text")
        consistent = claim_entry.get("consistent")
        if not isinstance(consistent, bool):
            raise ValueError(f"world_consistency.claims[{index}].consistent must be true or false")
        checked_against = claim_entry.get("checked_against")
        if not isinstance(checked_against, str) or not checked_against.strip():
            raise ValueError(
                f"world_consistency.claims[{index}] requires non-empty checked_against "
                f"on every claim, not only inconsistent ones"
            )
        if not consistent and checked_against == NO_SUPPLIED_FACT:
            raise ValueError(
                f"world_consistency.claims[{index}] is inconsistent but checked_against "
                f"is the no-supplied-fact placeholder; an inconsistent claim must name "
                f"the real fact it conflicts with"
            )
        quote = claim_entry.get("quote")
        if not isinstance(quote, str) or not quote.strip():
            raise ValueError(f"world_consistency.claims[{index}] requires a non-empty quote")
        if not consistent:
            any_inconsistent = True
        parsed_claims.append({
            "claim": claim_text,
            "quote": quote,
            "quote_verified": _quote_is_verbatim(quote, npc_dialogue),
            "consistent": consistent,
            "checked_against": checked_against,
        })

    if not parsed_claims:
        decision = "NA"
    elif any_inconsistent:
        decision = "FAIL"
    else:
        decision = "PASS"
    return {"decision": decision, "claims": parsed_claims}


def _extract_json_object(text):
    """Best-effort recovery of one JSON object from text a judge wrapped in a markdown
    code fence or a conversational preamble/postamble, despite the prompt asking for
    exactly one JSON object and nothing else -- some models do this anyway. Only ever
    used as a fallback after a direct parse already failed."""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`").strip()
        if stripped.lower().startswith("json"):
            stripped = stripped[len("json"):].strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end != -1 and end > start:
        return stripped[start:end + 1]
    return stripped


def parse_h1_response(response_text, npc_dialogue):
    """Parse and validate one strict H1 decision object. `npc_dialogue` is the actual
    response text this decision is about, used to verify World Consistency's quotes."""
    try:
        data = json.loads(response_text)
    except json.JSONDecodeError:
        try:
            data = json.loads(_extract_json_object(response_text))
        except json.JSONDecodeError as error:
            raise ValueError(f"Judge did not return valid JSON: {error}") from error

    required_metrics = {"context_use", "world_consistency", "no_contradiction"}
    if not isinstance(data, dict) or set(data) != required_metrics:
        raise ValueError(f"Expected exactly the keys {sorted(required_metrics)}")

    parsed = {}
    for metric in ("context_use", "no_contradiction"):
        entry = data[metric]
        if not isinstance(entry, dict):
            raise ValueError(f"{metric} must be an object")
        decision = entry.get("decision")
        if decision not in ("PASS", "FAIL", "NA"):
            raise ValueError(f"{metric} decision must be PASS, FAIL, or NA")
        evidence = entry.get("evidence")
        if decision in ("PASS", "FAIL") and not evidence:
            raise ValueError(f"{metric} requires evidence when decision is {decision}")
        if decision == "NA" and evidence:
            raise ValueError(f"{metric} evidence must be null when decision is NA")
        parsed_entry = {"decision": decision, "evidence": evidence}
        if metric == "no_contradiction":
            contradicted_round = entry.get("contradicted_round")
            if decision == "FAIL":
                if not isinstance(contradicted_round, int) or isinstance(contradicted_round, bool):
                    raise ValueError(
                        "no_contradiction requires an integer contradicted_round when FAIL"
                    )
            elif contradicted_round is not None:
                raise ValueError("contradicted_round must be null unless no_contradiction is FAIL")
            parsed_entry["contradicted_round"] = contradicted_round
        parsed[metric] = parsed_entry

    parsed["world_consistency"] = parse_world_consistency_claims(
        data["world_consistency"], npc_dialogue
    )
    return parsed


def compute_consistency(decisions):
    """Average the applicable (non-NA) metric scores; None if none apply."""
    applicable = [
        DECISION_TO_SCORE[entry["decision"]]
        for entry in decisions.values()
        if entry["decision"] != "NA"
    ]
    if not applicable:
        return None
    return sum(applicable) / len(applicable)


def evaluate_h1_turn(record, round_number, llm, retries=4):
    """Evaluate one turn's Context Use / World Consistency / No Contradiction."""
    prompt = build_h1_prompt(record, round_number)
    npc_dialogue = next(
        turn["npc_dialogue"] for turn in record["turns"] if turn["round"] == round_number
    )
    last_error = None
    response_text = ""
    for attempt in range(1, retries + 1):
        raw_text = None
        try:
            raw_text = judge_text(llm, prompt)
            response_text = raw_text
            decisions = parse_h1_response(response_text, npc_dialogue)
            break
        except ValueError as error:
            last_error = error
            print(
                f"  [H1 retry {attempt}/{retries}] {record['trial_id']} "
                f"{record['context_condition']} round {round_number}: {error}"
            )
            if raw_text is not None:
                print(f"    raw judge response: {raw_text!r}")
    else:
        raise ValueError(f"Judge did not return a valid H1 decision: {last_error}")

    decisions_out = {}
    for metric, entry in decisions.items():
        decisions_out[metric] = {
            "decision": entry["decision"],
            "score": DECISION_TO_SCORE[entry["decision"]],
        }
        if metric == "world_consistency":
            decisions_out[metric]["claims"] = entry["claims"]
        else:
            decisions_out[metric]["evidence"] = entry["evidence"]
        if metric == "no_contradiction":
            decisions_out[metric]["contradicted_round"] = entry["contradicted_round"]

    if round_number == 1:
        # Round 1 has no prior turn to contradict — a structural fact known from
        # round_number alone, not a judgment call. Enforced here rather than trusted to
        # the judge: empirically it mislabels this PASS about as often as NA, since an
        # empty prior-turn history is genuinely ambiguous ("not applicable" vs. "trivially
        # nothing conflicts") in a way no later round ever is. See the 2026-09-09
        # provenance entry.
        decisions_out["no_contradiction"] = {
            "decision": "NA",
            "score": None,
            "evidence": None,
            "contradicted_round": None,
        }

    return {
        "schema_version": 1,
        "hypothesis": "H1",
        "generation_run_id": record["generation_run_id"],
        "pilot_id": record.get("pilot_id"),
        "trial_id": record["trial_id"],
        "scene_id": record["scene_id"],
        "target_character_id": record["target_character_id"],
        "context_condition": record["context_condition"],
        "priority_policy_id": record["priority_policy_id"],
        "judge_model": llm.model_name,
        "round": round_number,
        "decisions": decisions_out,
        "consistency": compute_consistency(decisions_out),
        "prompt": prompt,
        "judge_response": response_text,
    }


def evaluate_h2_trial(record, llm, score_retries=4):
    """H2 realism: CharacterBox's seven-metric trajectory evaluator, unchanged."""
    result = characterbox_evaluate_trajectory(record, llm, score_retries=score_retries)
    result["hypothesis"] = "H2"
    return result


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trajectory", type=Path)
    parser.add_argument("-c", "--config", type=Path, default=Path("config/evaluate.yaml"))
    parser.add_argument("--generation-run-id")
    parser.add_argument(
        "--h1-output", type=Path, default=Path("output/evaluation/h1_consistency.jsonl")
    )
    parser.add_argument(
        "--h2-output", type=Path, default=Path("output/evaluation/h2_realism.jsonl")
    )
    return parser.parse_args()


def main():
    args = parse_args()
    config = CfgNode(new_allowed=True)
    config.merge_from_file(str(args.config))
    api_key_env = config.get("api_key_env", "OPENAI_API_KEY")
    api_key = os.environ.get(api_key_env)
    if not api_key:
        raise ValueError(f"Set {api_key_env} before running evaluation")
    utils.ensure_dir("output/log/evaluation")
    logger = utils.set_logger("evaluation/evaluation.log", "evaluate")
    llm = utils.get_llm(config["judger_llm"], config, logger, api_key, config.get("api_base"))

    trials = load_trajectory_run(args.trajectory, args.generation_run_id)
    total_records = sum(len(trial) for trial in trials)
    total_turns = sum(len(record["turns"]) for trial in trials for record in trial)
    print(
        f"Evaluating run {trials[0][0]['generation_run_id']} with {config['judger_llm']} — "
        f"{len(trials)} trial(s), {total_records} condition-record(s): "
        f"H1 ~{total_turns} judge call(s) (1 per turn), "
        f"H2 ~{total_records * 2} judge call(s) (critique + score per record)."
    )

    args.h1_output.parent.mkdir(parents=True, exist_ok=True)
    args.h2_output.parent.mkdir(parents=True, exist_ok=True)

    with args.h1_output.open("a", encoding="utf-8") as h1_file, args.h2_output.open(
        "a", encoding="utf-8"
    ) as h2_file:
        for trial in trials:
            for record in trial:
                for turn in record["turns"]:
                    result = evaluate_h1_turn(
                        record, turn["round"], llm, retries=config.get("score_retries", 4)
                    )
                    json.dump(result, h1_file, ensure_ascii=False)
                    h1_file.write("\n")
                    summary = ", ".join(
                        f"{metric}={entry['decision']}"
                        for metric, entry in result["decisions"].items()
                    )
                    print(
                        f"[H1] {result['trial_id']} {result['context_condition']} "
                        f"round {result['round']}: {summary}, "
                        f"consistency={result['consistency']}"
                    )

                h2_result = evaluate_h2_trial(
                    record, llm, score_retries=config.get("score_retries", 4)
                )
                json.dump(h2_result, h2_file, ensure_ascii=False)
                h2_file.write("\n")
                score_summary = ", ".join(
                    f"{name}={score}" for name, score in h2_result["scores"].items()
                )
                print(
                    f"[H2] {h2_result['trial_id']} {h2_result['context_condition']}: "
                    f"{score_summary}, Average={h2_result['average']:.3f}"
                )

    print("H1 (consistency) results saved in:", args.h1_output)
    print("H2 (realism) results saved in:", args.h2_output)


if __name__ == "__main__":
    main()
