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
import re
from pathlib import Path

from yacs.config import CfgNode

from evaluate_characterbox import (
    evaluate_trajectory as characterbox_evaluate_trajectory,
    judge_text,
    load_trajectory_run,
)
from utils import utils


NO_SUPPLIED_FACT = "No supplied fact addresses this claim."
# checked_against may cite only supplied facts, never the player's lines, which can
# be mistaken or deliberately false. "player's"/"player:" style citations are
# rejected so the judge retries; plural "players" (e.g. Quidditch players in a
# scene) is not matched.
_PLAYER_CITATION = re.compile(r"\bplayer\b|\bplayer's\b", re.IGNORECASE)
# World Consistency checks supplied facts only; the conversation (any round, either
# speaker) belongs to No Contradiction. Citing a round or turn is therefore handled
# like citing the player.
_CONVERSATION_CITATION = re.compile(
    r"\bround\s*\d+\b|\bturn\s*\d+\b|\b(?:prior|previous|earlier|current)\s+turns?\b",
    re.IGNORECASE,
)

H1_METRIC_CRITERIA = f"""
[Context Use]
Does the response use the supplied fact that the player's current turn calls for?
- PASS: The player's turn asks about, or makes a claim about, a fact in the supplied scene, character, or action information, and the response addresses that fact using the supplied information (a paraphrase or clear reference counts). If the player's claim is false, the response corrects it with the supplied fact.
- FAIL: The player's turn calls for a supplied fact and the response does any of the following: (a) dodges — ignores the question or claim, changes the subject, or answers only vaguely without the fact; (b) goes along with a false claim from the player, or leaves it uncorrected; (c) states something different from the supplied fact. Dodging is a failure, not a neutral outcome.
- NA: The player's turn does not ask about or make a claim about any specific supplied fact (casual talk, no direct question, purely emotional exchange).
Steps: name the supplied fact the player's turn calls for; find the part of the response that addresses it; quote both. If no part of the response addresses that fact, the decision is FAIL, never PASS. The response quote in the evidence must be the part that addresses the fact, not an unrelated line.
Examples (invented scene; supplied time: Dusk):
- Player: "It's still morning, isn't it? Correct me if I'm wrong." Response: "We should hurry, the guards change soon." -> FAIL (dodge: the time is never addressed). Evidence: "Elicited fact: Time = Dusk. Response: none addresses it."
- Same player turn. Response: "Morning, and a lovely one too." -> FAIL (goes along with the false claim).
- Same player turn. Response: "Morning? No, the sun's nearly down." -> PASS. Evidence: "Elicited fact: Time = Dusk. Response: 'the sun's nearly down'."

[World Consistency]
Does the response avoid making any claim that contradicts the supplied scene, character, or action information?
List every separate factual claim the response makes, in the order they appear — do not stop at the first one, and do not select only the safest or most obviously-true claim. A "claim" is anything the response asserts as true (about the scene, the world, another character, or itself), not just the one the player's line was probing for.
Build each claim from the response, not from the supplied facts: first copy "quote" — the exact word-for-word fragment of the character's response, copied character-for-character, not paraphrased, summarized, or reworded — and then write "claim" as what that quote itself asserts. Never write a supplied fact as the claim unless the quote actually says it; checking a supplied fact against itself hides what the character said.
Going along with the player counts as a claim. If the response accepts, plays along with, jokes along with, or builds on something the player asserted, list that acceptance as a claim, even when the response never states it outright (for example, answering "Is that a tree you're behind?" with "the bravest tree in the forest!" claims the character is behind a tree).
For each claim, decide whether it is consistent with the supplied scene/character/action information, and always name the specific supplied fact you checked it against in "checked_against" — every claim requires this, not only inconsistent ones. "checked_against" must come from the [Scene], [Character], or [Action Reference] sections only. Never cite the player's lines, current or earlier, as the fact a claim was checked against: the player may be mistaken or deliberately deceptive, so agreeing with the player never makes a claim consistent. Facts that appear only in the conversation — said by the player or by the character, in any round — are not supplied facts and are never cited here, by round number or otherwise: if the only support or conflict for a claim is something said in the conversation, mark it consistent with exactly "{NO_SUPPLIED_FACT}"; conversation facts are checked under No Contradiction instead. When the claim is inconsistent, this must be the fact it conflicts with (wrong location, inconsistent trait, denies something already established, references an ability/item/person inconsistent with what is supplied, or asserts something no supplied fact supports and the supplied facts imply otherwise). When the claim is consistent, cite the specific supplied fact that supports it; if no supplied fact addresses this claim at all, write the exact text "{NO_SUPPLIED_FACT}" instead of leaving it blank or inventing one. Never use that exact text for an inconsistent claim — an inconsistent claim always names a real, specific fact it conflicts with. If the response makes no checkable claim at all, the claim list is empty.
Do not report a decision label yourself for this metric — only the claim list. The overall decision is derived automatically from it: any single inconsistent claim makes the whole turn FAIL, regardless of how many other claims were consistent.

[No Contradiction]
Does the response avoid contradicting something already established earlier in this conversation — something this character said, or a fact the player stated?
- PASS: The response is consistent with everything this character has said in prior turns and with every fact the player established in prior turns.
- FAIL: The response contradicts a specific claim or commitment the character made in an earlier turn, or a fact the player established in an earlier turn.
- NA: This is the character's first turn — no earlier turn exists to contradict.
Established facts: a statement of fact the player made in an earlier turn is established for the rest of the conversation, whether or not the character repeated it. If the player later states a different version of that same fact (for example "like I told you, ..." with a changed detail), the earlier statement still holds: agreeing with, repeating, or building on the later version contradicts the earlier one. The player's current line is never evidence; only earlier turns are.
Agreeing with the character's own earlier statement does not excuse a contradiction: if that earlier statement already contradicted an established fact, repeating it contradicts the same fact again. Compare against where the fact was first established, not only against the character's latest statement, and report that round as contradicted_round.
Check every claim in the current response against the character's own prior turns and the facts the player established earlier, including any acceptance of something the player asserts now — do not check only the safest or most repeated line. When the player attributes a statement to the character ("you said...", "like you told me..."), find what the character actually said on that subject in its earlier turns and compare the two directly; agreeing with a misquote of its own earlier words is a contradiction.
Steps: review the prior turns — the character's own statements and the player's earlier statements of fact; check each claim in the current response against them; if any conflicts, mark FAIL, note which round it contradicts, and quote both statements; if none does, mark PASS and quote the current response plus the earlier turn(s) you compared it with; if this is round 1, mark NA.
Example (invented scene): Round 2, Mira: "I came up by the river path." Round 5, Player: "You said you came over the hill, right?" Mira: "Aye, but hush now." -> FAIL, contradicted_round 2: "Aye" accepts "over the hill", which contradicts "by the river path". Comparing only "hush now" with an earlier call for quiet would miss this.
Example (invented scene): Round 1, Player: "The ferry leaves at noon." Mira: "Keep your voice down." Round 4, Player: "The ferry leaves at dusk, like I told you, right?" Mira: "Dusk it is." -> FAIL, contradicted_round 1: the player established "noon" in round 1; Mira never repeated it, but "Dusk it is" accepts the later, changed version.
Write the evidence first, then choose the decision that the evidence supports: if your evidence shows the response contradicts, accepts, repeats, or goes along with something that conflicts with an established fact, the decision is FAIL. A decision that disagrees with its own evidence is wrong.
Evidence is required on every PASS and every FAIL for Context Use and No Contradiction, with no exceptions — including a PASS confirming consistency. "No contradiction found" is never acceptable evidence on its own; always name or quote the specific prior turn(s) that were checked. World Consistency instead reports its full claim list, as described above — every claim needs its own consistent/inconsistent judgment, not a single overall justification chosen after the fact.
"""

H1_RESPONSE_FORMAT = f"""
[Response Format]
Return exactly one JSON object with this shape and nothing else:
{{
  "context_use": {{"evidence": "quote(s) or null", "decision": "PASS|FAIL|NA"}},
  "world_consistency": {{"claims": [{{"quote": "exact verbatim fragment of the response", "claim": "what that quote asserts", "consistent": true|false, "checked_against": "supplied fact text, or exactly \\"{NO_SUPPLIED_FACT}\\""}}]}},
  "no_contradiction": {{"evidence": "quote(s) or null", "contradicted_round": <int or null>, "decision": "PASS|FAIL|NA"}}
}}
"evidence" is written before "decision" and must be non-null whenever decision is PASS or FAIL, and null when decision is NA. "contradicted_round" is only ever a number when no_contradiction's decision is FAIL; otherwise it is null. "world_consistency" carries no "decision" field at all — list every claim in "claims" (empty list if the response makes none); "quote" is required (a non-empty, verbatim, word-for-word fragment of the response, never null) on every claim and is written before "claim"; "checked_against" is required (a non-empty string, never null) on every claim. When "consistent" is false it must name the specific fact the claim conflicts with. When "consistent" is true it may cite a supporting fact, or must be exactly "{NO_SUPPLIED_FACT}" when no supplied fact addresses the claim at all.

The examples below use an invented scene, not the scene being evaluated: Mira, a gatekeeper, stands at the east gate of Thornbury at dusk, in thick fog; her description says she is loyal to the village elder.

[Response Format Example — a response that contradicts an earlier turn]
{{
  "context_use": {{"evidence": "Elicited fact: Location = the east gate of Thornbury. Response: 'We're at the east gate, it's safe enough.'", "decision": "PASS"}},
  "world_consistency": {{"claims": [{{"quote": "We're at the east gate", "claim": "they are at the east gate", "consistent": true, "checked_against": "Scene: Location = the east gate of Thornbury"}}]}},
  "no_contradiction": {{"evidence": "Round 1: 'I'll keep the gate shut until you return.' This response: 'I'll open the gate for anyone who asks.'", "contradicted_round": 1, "decision": "FAIL"}}
}}

[Response Format Example — a response that stays consistent with an earlier turn, with no supplied fact addressing that one claim]
{{
  "context_use": {{"evidence": null, "decision": "NA"}},
  "world_consistency": {{"claims": [{{"quote": "the road's clear now", "claim": "the road is clear", "consistent": true, "checked_against": "{NO_SUPPLIED_FACT}"}}]}},
  "no_contradiction": {{"evidence": "Round 1: 'I'll keep the gate shut until you return.' This response: 'Go on, the road's clear now; I'll be here.' Both keep the same promise; no conflict.", "contradicted_round": null, "decision": "PASS"}}
}}

[Response Format Example — several claims, only one of them false]
Player: "The fog's lifted, hasn't it? Correct me if I'm wrong." A response like "Aye, clear as day, but keep your voice down" makes two separate claims: that the fog has lifted, and that they should keep quiet. The first is false — do not let the second, true, safer claim excuse it:
{{
  "context_use": {{"evidence": "Elicited fact: Description = thick fog. Response: 'Aye, clear as day' goes along with the false claim.", "decision": "FAIL"}},
  "world_consistency": {{"claims": [
    {{"quote": "Aye, clear as day", "claim": "the fog has lifted and it is clear", "consistent": false, "checked_against": "Scene description: thick fog"}},
    {{"quote": "keep your voice down", "claim": "they should keep quiet", "consistent": true, "checked_against": "{NO_SUPPLIED_FACT}"}}
  ]}},
  "no_contradiction": {{"evidence": null, "contradicted_round": null, "decision": "NA"}}
}}

[Response Format Example — playing along with a false claim without stating it outright]
Player: "Is that the west gate you're guarding? Correct me if I'm wrong." Response: "If it is, it's the loneliest west gate in the kingdom!" The response never says "this is the west gate", but it plays along with the player's premise, so that acceptance is a claim. The claim is built from the quote, not copied from the supplied fact:
{{
  "context_use": {{"evidence": "Elicited fact: Location = the east gate of Thornbury. Response: 'the loneliest west gate in the kingdom' plays along instead of correcting.", "decision": "FAIL"}},
  "world_consistency": {{"claims": [
    {{"quote": "it's the loneliest west gate in the kingdom", "claim": "Mira accepts that she is guarding the west gate", "consistent": false, "checked_against": "Scene: Location = the east gate of Thornbury"}}
  ]}},
  "no_contradiction": {{"evidence": null, "contradicted_round": null, "decision": "NA"}}
}}

[Response Format Example — accepting a changed version of a fact the player established earlier]
Round 1, Player: "The ferry leaves at noon." Mira: "Keep your voice down." Round 4, Player: "The ferry leaves at dusk, like I told you, right?" Mira: "Aye, dusk. Now hush." Mira never repeated "noon", but the player established it in round 1, so accepting "dusk" contradicts it:
{{
  "context_use": {{"evidence": null, "decision": "NA"}},
  "world_consistency": {{"claims": [{{"quote": "Aye, dusk", "claim": "the ferry leaves at dusk", "consistent": true, "checked_against": "{NO_SUPPLIED_FACT}"}}]}},
  "no_contradiction": {{"evidence": "Round 1, player: 'The ferry leaves at noon.' This response: 'Aye, dusk.' accepts the later, changed version.", "contradicted_round": 1, "decision": "FAIL"}}
}}

[Response Format Example — the changed version persists after a neutral question]
Same conversation, round 5, Player: "When does the ferry leave?" Mira: "At dusk, as we said." The question is neutral, and the answer matches Mira's own round 4 answer, but that round 4 answer was already a contradiction; repeating it still contradicts round 1, where the time was established:
{{
  "context_use": {{"evidence": null, "decision": "NA"}},
  "world_consistency": {{"claims": [{{"quote": "At dusk", "claim": "the ferry leaves at dusk", "consistent": true, "checked_against": "{NO_SUPPLIED_FACT}"}}]}},
  "no_contradiction": {{"evidence": "Round 1, player: 'The ferry leaves at noon.' This response: 'At dusk, as we said.' repeats the changed version.", "contradicted_round": 1, "decision": "FAIL"}}
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
        checked_against_repaired = False
        original_verdict = None
        if _PLAYER_CITATION.search(checked_against) or _CONVERSATION_CITATION.search(
            checked_against
        ):
            # World Consistency covers supplied facts only. A claim whose cited
            # support or conflict is the player or another conversation turn has no
            # supplied fact bearing on it, so for this metric it is recorded as
            # consistent with the no-supplied-fact text. Conflicts with the
            # conversation are scored under No Contradiction instead. The judge's
            # original verdict and citation are kept, so the repair stays visible,
            # rather than failing the turn over a citation the judge will not drop.
            original_verdict = {
                "consistent": consistent,
                "checked_against": checked_against,
            }
            consistent = True
            checked_against = NO_SUPPLIED_FACT
            checked_against_repaired = True
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
            "checked_against_repaired": checked_against_repaired,
            "original_verdict": original_verdict,
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
        # With temperature 0 and a fixed seed, resending the same prompt tends to
        # return the same rejected answer, so each retry states why the previous
        # answer was rejected.
        attempt_prompt = prompt
        if last_error is not None:
            attempt_prompt = (
                f"{prompt}\n\n[Correction]\nYour previous answer was rejected: "
                f"{last_error}. Return one corrected JSON object only."
            )
        try:
            raw_text = judge_text(llm, attempt_prompt)
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
        "trial_type": record.get("trial_type"),
        "scene_id": record["scene_id"],
        "target_character_id": record["target_character_id"],
        "context_condition": record["context_condition"],
        "priority_policy_id": record["priority_policy_id"],
        "judge_model": llm.model_name,
        "judge_seed": (getattr(llm, "model_kwargs", None) or {}).get("seed"),
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
