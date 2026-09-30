"""Evaluate controlled dialogue trajectories with CharacterBox's seven metrics."""

from __future__ import annotations

# Adapted from CharacterBox evaluate.py at commit 5c19141e.
# Original copyright (c) 2023 Lei Wang; MIT licensed.
# The critic text, scoring prompt/rubric, seven metric names, 1/3/5 anchors,
# response example, and critique-then-score sequence are retained verbatim.
# Input normalisation, paired-run selection, blinding, validation, output
# schema, CLI, and provider invocation are research adaptations.
# See docs/characterbox-provenance.md and characterbox-change-record.md.

import argparse
import json
import logging
import os
import re
import time
from pathlib import Path

from langchain.schema import HumanMessage
from openai import RateLimitError
from yacs.config import CfgNode

from utils import utils


METRICS = (
    "Knowledge Accuracy",
    "Emotional Expression",
    "Personality Traits",
    "Behavioral Accuracy",
    "Immersion",
    "Adaptability",
    "Behavioral Coherence",
)


CRITIC_CRITERIA = """Strict Evaluation Criteria:
1. Factual Accuracy: Identify and point out any elements that do not accurately match the historical or factual backdrop.
2. Character Consistency: Explicitly highlight inconsistencies between the character's actions, dialogues, and their predefined traits and goals.
3. Logical Coherence: Point out any logical fallacies or actions that contradict the established context or character logic.
4. Content Redundancy: Identify repetitions in dialogue or action that could detract from engagement and realism.
5. Emotional Expression: Assess whether emotional responses and expressions are appropriate and convincingly portrayed, highlighting any discrepancies.
6. Interaction Adaptability: Critique the character's interactions with others, noting any unnatural or contextually inappropriate responses.
7. Creativity and Originality: Evaluate the creativity of responses and actions, pointing out generic or unoriginal content.
8. Detail Handling: Scrutinize the level of detail in scene setting and character enactment, marking areas lacking depth or accuracy.
9. Style Consistency: Ensure that the narrative and linguistic style remains consistent, identifying any deviations.
10. Fluency and Quality: Critically assess the smoothness and quality of the text, highlighting any grammatical errors or awkward phrasings.
Condense the issues into one paragraph."""


SCORING_CRITERIA = """
[Scoring Criteria]:
1. Knowledge Accuracy:
   - 1 Point: Information is often incorrect or irrelevant, significantly inconsistent with the character's background.
   - 3 Points: Information is generally accurate, though there are occasional errors or some details are not very relevant to the character's background.
   - 5 Points: Information is always accurate and highly relevant to the character's historical or professional background, demonstrating deep knowledge and skills.
2. Emotional Expression:
   - 1 Point: Emotional expression is monotonous or inappropriate, not aligning with the dialogue content and context.
   - 3 Points: Emotional expression is moderately varied, usually matching the content, but lacks depth and subtlety.
   - 5 Points: Emotional expression is rich and profound, highly consistent with the dialogue content and context, showing complex and nuanced emotions.
3. Personality Traits:
   - 1 Point: The displayed personality traits often conflict with or lack consistency with the character's setup.
   - 3 Points: Personality traits generally match the character's setup, though there are occasional inconsistencies.
   - 5 Points: Consistently displays behavior and language choices that match the core personality traits of the character, showcasing the character's uniqueness.
4. Behavioral Accuracy:
   - 1 Point: The model fails to capture or reproduce the character's unique behaviors and linguistic habits.
   - 3 Points: The model reflects the character's behaviors and linguistic habits to some extent, but not precisely or completely.
   - 5 Points: The model accurately mimics and reproduces the character's specific behaviors, linguistic habits, and catchphrases.
5. Immersion:
   - 1 Point: Character portrayal is often inconsistent, making it difficult for users to immerse or understand the character.
   - 3 Points: Character is mostly consistent, but occasional contradictions slightly affect immersion.
   - 5 Points: Character portrayal is always consistent, enhancing user immersion and effectively showing self-awareness and character limitations.
6. Adaptability:
   - 1 Point: Character portrayal lacks adaptability in the development of the dialogue, unable to handle new situations reasonably.
   - 3 Points: Character adapts to changes in the dialogue in most situations, though occasionally it may not be very flexible.
   - 5 Points: Character flexibly handles any new situations in the dialogue, always maintaining character consistency and adjusting to new directions.
7. Behavioral Coherence:
   - 1 Point: Character's behavior and responses are often logically disordered, not matching the dialogue or plot development.
   - 3 Points: Character's behavior and responses are generally logically coherent, though occasionally there may be unreasonable aspects.
   - 5 Points: Character's behavior and responses are always logically consistent, reasonably adjusting based on the progression of the dialogue and plot development.

[Evaluation Steps]:
1. Contextual Understanding: Examine the character's profile and background information thoroughly to fully grasp the nuances of their context, motivations, and historical background.
2. Behavioral Observation: Monitor how the character reacts across different scenarios, paying special attention to their decisions, dialogues, and interactions.
3. Critique Analysis: Evaluate the character based on issues and weaknesses identified in external critiques, ensuring a focused assessment that considers these specific points.
4. Criteria-Based Assessment: Analyze each observed behavior using the criteria to systematically evaluate the consistency and effectiveness of the character's portrayal. Your resposne must follow the format provided below.

[Response Format]:
Knowledge Accuracy: [1-5]
Emotional Expression: [1-5]
Personality Traits: [1-5]
Behavioral Accuracy: [1-5]
Immersion: [1-5]
Adaptability: [1-5]
Behavioral Coherence: [1-5]

[Response Format Example]:
Knowledge Accuracy: 3
Emotional Expression: 3
Personality Traits: 3
Behavioral Accuracy: 3
Immersion: 3
Adaptability: 3
Behavioral Coherence: 3

[Response]:

"""


def parse_scores(response):
    """Parse exactly one in-range score for every CharacterBox metric."""
    scores = {}
    for metric in METRICS:
        matches = re.findall(
            rf"(?mi)^\s*{re.escape(metric)}\s*:\s*\[?\s*(\d+)\s*\]?\s*$",
            response,
        )
        if len(matches) != 1:
            raise ValueError(f"Expected exactly one {metric} score")
        score = int(matches[0])
        if score not in range(1, 6):
            raise ValueError(f"{metric} score must be between 1 and 5")
        scores[metric] = score
    return scores


def load_trajectory_run(path, generation_run_id=None):
    """Load every complete per-trial paired condition set sharing one
    generation_run_id, defaulting to the latest run in JSONL. A pilot
    invocation shares one generation_run_id across every trial and every
    condition, so a run is a list of trials, each a list of that trial's
    condition records in declared-condition order."""
    records = []
    with Path(path).open(encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            record = json.loads(line)
            if record.get("record_type") != "controlled_dialogue_trajectory":
                raise ValueError(f"Line {line_number} is not a controlled trajectory")
            records.append(record)
    if not records:
        raise ValueError("Trajectory file is empty")

    selected_run_id = generation_run_id or records[-1].get("generation_run_id")
    if not selected_run_id:
        raise ValueError("A generation_run_id is required")
    selected = [
        record
        for record in records
        if record.get("generation_run_id") == selected_run_id
    ]
    if not selected:
        raise ValueError(f"Unknown generation_run_id: {selected_run_id}")

    expected_conditions = selected[0].get("pilot_conditions") or [
        selected[0]["context_condition"]
    ]
    by_trial = {}
    for record in selected:
        trial_id = record["trial_id"]
        condition = record["context_condition"]
        by_condition = by_trial.setdefault(trial_id, {})
        if condition in by_condition:
            raise ValueError(
                f"Run {selected_run_id} trial {trial_id} contains duplicate "
                f"condition {condition}"
            )
        by_condition[condition] = record

    trials = []
    for trial_id, by_condition in by_trial.items():
        if set(by_condition) != set(expected_conditions):
            raise ValueError(
                f"Run {selected_run_id} trial {trial_id} does not contain "
                f"exactly {', '.join(expected_conditions)}"
            )
        trials.append([by_condition[condition] for condition in expected_conditions])
    return trials


def format_trajectory(record):
    """Render condition-blind CharacterBox scene, profile, and behaviour text."""
    # Research-only U/S/P and priority metadata intentionally stop at this
    # adapter boundary. Upstream CharacterBox had no condition labels, and the
    # judge must not be told which experimental treatment produced the text.
    scene = record["scene"]
    target = record["target"]
    scene_text = (
        "Scenario Information:\n"
        f"Event: {scene['event']}\n"
        f"Time: {scene['time']}\n"
        f"Location: {scene['location']}\n"
        f"Description: {scene['description']}\n"
    )
    character_text = (
        f"Name: {target['name']}\n"
        f"Description: {target['description']}\n"
    )
    behavior_parts = []
    for turn in record["turns"]:
        behavior_parts.extend(
            (
                f"Round: {turn['round']}",
                f"Observation: {turn['npc_observation']}",
                "Action:",
                f"{target['name']}: {turn['npc_dialogue']}",
            )
        )
    return scene_text, character_text, "\n".join(behavior_parts) + "\n"


def build_critic_prompt(record):
    scene, character, behavior = format_trajectory(record)
    return f"""
Please execute the following role-play and identify any issues based on these strict evaluation criteria:

- Scene Description: \n{scene}\n
- Character Description:\n {character}\n
- Character Actions: \n{behavior}\n

{CRITIC_CRITERIA}
    """


def build_score_prompt(record, critique):
    scene, character, behavior = format_trajectory(record)
    return (
        "Please evaluate the role-playing ability of the character based on "
        "actions across multiple turns based on scene, character information, "
        "critique and evaluation criteria.\n"
        f"[Scene]:\n{scene}\n"
        f"[Character]:\n{character}\n"
        f"[Multi-turn Actions]:\n{behavior}\n"
        f"[Critique]:\n{critique}\n"
        f"{SCORING_CRITERIA}"
    )


RATE_LIMIT_MAX_ATTEMPTS = 50
RATE_LIMIT_MIN_DELAY_SECONDS = 10
RATE_LIMIT_BASE_DELAY_SECONDS = 10
RATE_LIMIT_MAX_DELAY_SECONDS = 60


def _rate_limit_delay_seconds(error, attempt):
    """Prefer the provider's own Retry-After header over guessing; fall back to
    exponential backoff (10s, 20s, 40s, capped at 60s) when it is absent. Either
    way, never wait less than RATE_LIMIT_MIN_DELAY_SECONDS -- OpenAI sometimes
    sends a Retry-After of 1-2s that is too short to actually clear the window,
    and retrying that fast just burns another attempt against the same limit."""
    retry_after = getattr(getattr(error, "response", None), "headers", {}).get("retry-after")
    if retry_after is not None:
        try:
            return max(float(retry_after), RATE_LIMIT_MIN_DELAY_SECONDS)
        except ValueError:
            pass
    return min(RATE_LIMIT_BASE_DELAY_SECONDS * (2 ** attempt), RATE_LIMIT_MAX_DELAY_SECONDS)


def judge_text(llm, prompt):
    """Invoke the judge and return its text, or raise with the real reason when the
    provider returns an empty completion (content filter, refusal, truncation) instead
    of the confusing bare "empty JSON" a caller would otherwise see downstream.

    Retries on a 429 rate-limit response, honouring the provider's Retry-After header
    when present and otherwise backing off exponentially (10s, 20s, 40s, 60s, 60s...)
    up to RATE_LIMIT_MAX_ATTEMPTS attempts -- high enough that this should only ever
    give up if the rate limit genuinely never clears, not for an ordinary transient
    spike. This is handled here, separately from the empty-content check below and
    from callers' own content-format retry loops, because a rate limit is the API
    refusing the request outright -- not the model responding badly -- so retrying
    immediately with the same request only wastes an attempt against a quota that has
    not yet reset."""
    for attempt in range(RATE_LIMIT_MAX_ATTEMPTS):
        try:
            response = llm.invoke([HumanMessage(content=prompt)])
            break
        except RateLimitError as error:
            if attempt == RATE_LIMIT_MAX_ATTEMPTS - 1:
                raise
            delay = _rate_limit_delay_seconds(error, attempt)
            print(
                f"  [rate limit] waiting {delay:.0f}s before retry "
                f"({attempt + 1}/{RATE_LIMIT_MAX_ATTEMPTS}): {error}"
            )
            time.sleep(delay)
    if not response.content or not response.content.strip():
        finish_reason = (getattr(response, "response_metadata", None) or {}).get("finish_reason")
        refusal = (getattr(response, "additional_kwargs", None) or {}).get("refusal")
        detail = f"finish_reason={finish_reason!r}"
        if refusal:
            detail += f", refusal={refusal!r}"
        raise ValueError(f"Judge returned an empty response ({detail})")
    return response.content


def evaluate_trajectory(record, llm, score_retries=4):
    """Run CharacterBox's critique-then-score flow for one trajectory."""
    critic_prompt = build_critic_prompt(record)
    critique = judge_text(llm, critic_prompt)
    score_prompt = build_score_prompt(record, critique)
    last_error = None
    score_response = ""
    for attempt in range(1, score_retries + 1):
        raw_text = None
        try:
            raw_text = judge_text(llm, score_prompt)
            score_response = raw_text
            scores = parse_scores(score_response)
            break
        except ValueError as error:
            last_error = error
            print(
                f"  [H2 retry {attempt}/{score_retries}] {record['trial_id']} "
                f"{record['context_condition']}: {error}"
            )
            if raw_text is not None:
                print(f"    raw judge response: {raw_text!r}")
    else:
        raise ValueError(
            f"Judge did not return valid CharacterBox scores: {last_error}"
        )
    return {
        "schema_version": 1,
        "evaluation_mode": "characterbox_trajectory",
        "generation_run_id": record["generation_run_id"],
        "trial_id": record["trial_id"],
        "trial_type": record.get("trial_type"),
        "scene_id": record["scene_id"],
        "target_character_id": record["target_character_id"],
        "context_condition": record["context_condition"],
        "priority_policy_id": record["priority_policy_id"],
        "judge_model": llm.model_name,
        "judge_seed": (getattr(llm, "model_kwargs", None) or {}).get("seed"),
        "rounds_evaluated": len(record["turns"]),
        "scores": scores,
        "average": sum(scores.values()) / len(scores),
        "critique": critique,
        "judge_response": score_response,
        "critic_prompt": critic_prompt,
        "score_prompt": score_prompt,
    }


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trajectory", type=Path)
    parser.add_argument("-c", "--config", type=Path, default=Path("config/evaluate_characterbox.yaml"))
    parser.add_argument("--generation-run-id")
    parser.add_argument("-o", "--output", type=Path)
    return parser.parse_args()


def main():
    args = parse_args()
    config = CfgNode(new_allowed=True)
    config.merge_from_file(str(args.config))
    api_key_env = config.get("api_key_env", "OPENAI_API_KEY")
    api_key = os.environ.get(api_key_env)
    if not api_key:
        raise ValueError(f"Set {api_key_env} before running evaluation")
    utils.ensure_dir("output/log/evaluation/characterbox")
    logger = utils.set_logger(
        "evaluation/characterbox/characterbox_evaluation.log",
        "characterbox-evaluation",
    )
    llm = utils.get_llm(
        config["judger_llm"],
        config,
        logger,
        api_key,
        config.get("api_base"),
    )
    trials = load_trajectory_run(args.trajectory, args.generation_run_id)
    total_records = sum(len(trial) for trial in trials)
    output_path = args.output or Path("output/evaluation/characterbox/results.jsonl")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    print(
        f"Evaluating run {trials[0][0]['generation_run_id']} with "
        f"{config['judger_llm']} — {len(trials)} trial(s), {total_records} "
        f"record(s) ({total_records * 2} expected judge calls)."
    )
    with output_path.open("a", encoding="utf-8") as file:
        for trial in trials:
            for record in trial:
                result = evaluate_trajectory(
                    record,
                    llm,
                    score_retries=config.get("score_retries", 4),
                )
                json.dump(result, file, ensure_ascii=False)
                file.write("\n")
                score_summary = ", ".join(
                    f"{name}={score}" for name, score in result["scores"].items()
                )
                print(
                    f"{result['trial_id']} {result['context_condition']}: "
                    f"{score_summary}, Average={result['average']:.3f}"
                )
    print("Evaluation results saved in:", output_path)


if __name__ == "__main__":
    main()
