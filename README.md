# Main Research

Code, trials, and outputs for the honours thesis *Generating Consistent LLM-Based Character Dialogue by Structuring and Prioritising Scenario Context* (University of Sydney, 2026).

The study asks whether the way a character's scenario context is presented to a large language model, rather than what it contains, changes the consistency and realism of the dialogue it generates. The same model receives the same scenario facts under three conditions:

1. **Unstructured (U):** the values of CharacterBox's 13 context fields in one flat block, without labels.
2. **Structured (S):** CharacterBox's own labelled prompt, used unchanged.
3. **Prioritised (P):** the same 13 fields grouped into five ranked tiers, each with a short instruction, under the `primary_five_level` priority policy.

The main comparison is **P versus S**, the effect of prioritisation over CharacterBox's prompt. **P versus U** is the second test of each hypothesis, and **S versus U** (the effect of structure alone) is reported as an additional finding.

## Checking the results

**Results dashboard: [`notebooks/results_dashboard.ipynb`](notebooks/results_dashboard.ipynb)**

Every number and chart in the Results chapter comes from this notebook. It reads only the saved outputs in `output/final/`, so it needs no API key and makes no model calls. GitHub shows the notebook with its saved outputs; to rerun it:

```bash
cd main-research
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt -r requirements-analysis.txt
jupyter lab notebooks/results_dashboard.ipynb    # then Run > Run All Cells
```

The dashboard reports H1 (single-turn consistency, t01–t10), H2 (realism), and H3 (multi-turn consistency, t11) by condition, broken down by trial type, metric, scene, and seed, with the Wilcoxon signed-rank tests, bootstrap confidence intervals, and paired t-tests. Set `SEEDS` or `PILOTS` in its first code cell to restrict the analysis, for example `PILOTS = [6, 7, 8, 9, 10]` for the unseen scenes only. Two more notebooks read the same files:

- [`notebooks/trial_inspector.ipynb`](notebooks/trial_inspector.ipynb): everything about one trial (set `SEED`, `PILOT`, `TRIAL`), including the U/S/P prompts and replies, the consistency judge's prompts and decisions, and the realism critique and scores.
- [`notebooks/judge_agreement.ipynb`](notebooks/judge_agreement.ipynb): the consistency judge against the researcher's blind labels (seed 1, pilots 1–5), with kappa by metric, trial type, condition, and pilot. Every disagreement is exported to `output/comparison/final_judge_disagreements.csv`.

## Project status

**As of 7 Nov 2026 the study is complete.** All ten pilots have been generated with five seeds (1–5) and judged by both judges, and these saved outputs are what the thesis reports. 162 tests pass.

## Where the outputs are

`tools/run_final.py` writes one folder per generation seed and pilot:

```text
output/final/
  seed1/
    p01/
      trajectory.jsonl        33 rows: 11 trials x 3 conditions (generated replies)
      h1_consistency.jsonl    60 rows: one per judged turn, 20 turns x 3 conditions
      h2_realism.jsonl        33 rows: one per trial and condition
      failed_judgements.jsonl only if a judge call failed after every retry
    p02/ ... p10/
  seed2/ ... seed5/
```

- **`trajectory.jsonl`**: one row per trial and condition. It holds the scene, the player and target profiles, the Action Reference, the generation settings (`generation.seed`, model, temperature), and the ordered turns with `player_dialogue` and the character's reply `npc_dialogue`. The rows of one pilot run share a `generation_run_id`.
- **`h1_consistency.jsonl`**: one row per target-character turn. `decisions` holds PASS/FAIL/NA with quoted evidence for Context Use, World Consistency, and No Contradiction, and `consistency` is the turn's score (Equation 4.1 of the thesis). Each row records `h1_rubric_version` (14).
- **`h2_realism.jsonl`**: one row per trial and condition, with CharacterBox's critique, its seven metric scores, and their `average`.

Each row carries `trial_id`, `trial_type` (1 neutral, 2 stress, 3 multi-turn), and `context_condition` (U, S, or P), which the notebooks use to group the results.

Seed 1 of pilots 1–5 is the development run judged with the final rubric. It was copied from `output/record/Harry_Potter/trajectory/…-p{1..5}.jsonl` and `output/evaluation/prompt_versions/v3/h1_consistency.jsonl`; those runs predate both fields, so `generation.seed = 1` (from `play.yaml` at the time) and `h1_rubric_version = 14` (checked against the stored prompts) were added to the copies.

Other outputs:

| Folder | Contents |
|---|---|
| `output/evaluation/judge_selection/` | Candidate consistency judges compared on pilots 1–2 (thesis Appendix E) |
| `output/evaluation/prompt_versions/v1, v2, v3/` | Consistency rubric development runs (thesis Appendix F); `docs/judge-change-log.md` records every rubric change and why |
| `output/comparison/` | Judge disagreement exports and run comparisons |
| `output/record/`, `output/log/` | CharacterBox's own call records and logs, including every raw prompt and response |

## Setup

Open a terminal in `main-research` and create or activate the virtual environment (Python 3.11):

```bash
cd main-research
python3.11 -m venv .venv          # first time only
source .venv/bin/activate
python -m pip install -r requirements.txt                 # generation and judging
python -m pip install -r requirements-analysis.txt        # notebooks
```

Generation and judging go through OpenRouter. Set the key in the terminal session only; never put it in a config file or commit it. Both the character model and the judges read `OPENAI_API_KEY`:

```bash
export OPENAI_API_KEY="your-openrouter-key"
```

## Reproducing the final study

### What is fixed

| Part | Setting | Where |
|---|---|---|
| Character model | `openai/gpt-4o-mini` via OpenRouter, temperature 0.5, max 300 tokens | `config/play.yaml` |
| Generation seed | 1–5, one per repeat of the whole study | `--seed` (overrides `seed` in `play.yaml`) |
| Conditions | U, S, P; P uses the `primary_five_level` priority policy | `config/pilot_run_config.json`, `config/context_priorities.json` |
| Scenes and trials | One manifest per pilot (scene, player, target, 11 trials) | `data/research_annotations/characterbox_pilot*.json` |
| Consistency judge (H1, H3) | `google/gemma-4-31b-it` via OpenRouter, temperature 0, seed 1, max 4000 tokens, rubric version 14 | `config/evaluate.yaml`, `evaluate.py` |
| Realism judge (H2) | CharacterBox's critique-then-score evaluation with the same judge model, with changes 10 and 12 | `evaluate_characterbox.py`, `docs/judge-change-log.md` |

| Pilot | Manifest | `pilot_id` | Scene | Role |
|---|---|---|---|---|
| 1 | `characterbox_pilot.json` | `cb_hp_019_luna_neville` | 19 | development |
| 2 | `characterbox_pilot2.json` | `cb_hp_012_newt_mcgonagall` | 12 | development |
| 3 | `characterbox_pilot3.json` | `cb_hp_031_dumbledore_harry` | 31 | development |
| 4 | `characterbox_pilot4.json` | `cb_hp_044_harry_hagrid` | 44 | development |
| 5 | `characterbox_pilot5.json` | `cb_hp_032_harry_seamus` | 32 | development |
| 6 | `characterbox_pilot6.json` | `cb_hp_041_harry_slughorn` | 41 | unseen |
| 7 | `characterbox_pilot7.json` | `cb_hp_046_dumbledore_newt` | 46 | unseen |
| 8 | `characterbox_pilot8.json` | `cb_hp_011_harry_mrsweasley` | 11 | unseen |
| 9 | `characterbox_pilot9.json` | `cb_hp_025_harry_moody` | 25 | unseen |
| 10 | `characterbox_pilot10.json` | `cb_hp_008_harry_draco` | 8 | unseen |

Pilots 1–5 were used to develop the trials and the consistency rubric. Pilots 6–10 were added after the design was frozen and test whether the results hold on scenes not used during development.

### Run

Generate and judge one seed for any pilots:

```bash
python tools/run_final.py --seed 2 --pilot 1 2 3 4 5 6 7 8 9 10
```

For each pilot this runs, in order, `simulator.py --pilot <manifest> --seed N --trajectory-output output/final/seedN/pNN/trajectory.jsonl`, then `evaluate.py --h1-only`, then `evaluate.py --h2-only`, all into the same folder. Rerunning the same command after an interruption skips completed steps: generation is skipped when the trajectory is complete, and the judges skip every turn and trial already scored. A partial trajectory stops the run; delete that `trajectory.jsonl` and rerun. Other options:

```bash
python tools/run_final.py --seed 1 --pilot 1 2 3 4 5 --h2-only   # judge an existing trajectory with H2 only
python tools/run_final.py --seed 3 --pilot 6 --dry-run             # print the commands without running them
```

On macOS, prefix long runs with `caffeinate -i` so the machine does not sleep. Then open the results dashboard to analyse the new outputs.

### Judge reliability

The researcher's blind labels for pilots 1–5 (seed 1) are in `data/research_annotations/judge_validation/manual_label/`: `human_labels_<pilot>.numbers` (the labelling sheet), `human_labels_<pilot>.csv` (an export of it), `blind_key_<pilot>.csv` (which of A/B/C is U/S/P), and `labelling_context_<pilot>.md` (what the researcher saw). To reproduce the consistency judge's agreement for one pilot (thesis Table 5.1):

```bash
L=data/research_annotations/judge_validation/manual_label
python tools/judge_agreement_table.py \
  --human $L/human_labels_harry_hagrid.csv --key $L/blind_key_harry_hagrid.csv \
  --results output/final/seed1/p04/h1_consistency.jsonl \
  --out output/comparison/agreement_harry_hagrid
```

### Limits of reproducibility

The seeds make generation and judging repeatable only on a best-effort basis. OpenAI and OpenRouter do not guarantee identical output for the same seed, and OpenRouter may route a request to a different provider. Rerunning a seed will therefore give very similar but not always identical replies and decisions, and the saved files under `output/final/` are the record the thesis reports. Hosted models are also retired over time, after which a run can only be reproduced with a substitute model.

## Extending the study

These are the starting points for a future study. Run `python -m unittest` after any change, and record every change to CharacterBox code in `docs/characterbox-change-record.md`.

### 1. Add a new pilot

1. **Choose a scene** from `data/generated_data/Harry_Potter.json` (CharacterBox's generated dataset) and pick the player character, the target character, and one source action whose `action_id` becomes the Action Reference.
2. **Write the manifest** as `data/research_annotations/characterbox_pilot11.json`, copying an existing one. A schema-v4 manifest holds `pilot_id`, `scene_id`, `player_character_id`, `target_character_id`, `action_id`, and an ordered list of `trials`. Each trial has a `trial_id`, a `type` (1 neutral, 2 stress, 3 multi-turn), a `note` explaining what it tests, and its scripted `turns` (`round`, `player_dialogue`).
3. **Follow the 11-trial layout** in [`docs/trial-design-guide.md`](docs/trial-design-guide.md): t01–t04 neutral fact checks, t05–t06 open-ended, t07–t10 false claims ending "Correct me if I'm wrong.", and t11 as the ten-round multi-turn trial with its fixed round layout.
4. **Check what the judge can see.** The consistency judge sees the supplied fields and the Action Reference but not the scene's opening history, so trials must not depend on facts that appear only in that history. The Action Reference must also not contradict it; pilot 6's `note` on t11 describes how this went wrong once.
5. **Validate** the manifest without any model call:

   ```bash
   python -m dataloader.research_sidecar data/research_annotations/characterbox_pilot11.json
   ```

6. **Run it** with `python tools/run_final.py --seed 1 --pilot 11`. `run_final.py` finds `characterbox_pilot{N}.json` by number, and the dashboard picks up the new `p11` folder automatically.

### 2. Add a new priority rule

Priority policies live in [`config/context_priorities.json`](config/context_priorities.json); the thesis uses `primary_five_level`. To try another ranking or other tier instructions, add a policy to the `policies` list rather than editing the frozen one:

```json
{
  "policy_id": "my_new_policy",
  "conflict_rule": "Optional sentence placed before the tiers; a default is used if omitted.",
  "priorities": [
    {"priority": 1, "name": "tier_name", "instruction": "What the model should do with these fields.", "fields": ["time", "location", "position"]},
    {"priority": 2, "name": "...", "instruction": "...", "fields": ["..."]}
  ]
}
```

The validator in `dataloader/context_priorities.py` requires priorities numbered 1, 2, 3, … without gaps, a name and instruction for each tier, and each of the 13 CharacterBox fields (`event`, `time`, `location`, `description`, `name`, `character_description`, `position`, `states`, `self_belief`, `env_belief`, `recent_memory`, `observation`, `action_reference`) assigned to exactly one tier. An instruction may use `{name}` for the target character's name. Check the file with:

```bash
python -m dataloader.context_priorities config/context_priorities.json
```

Then set `priority_policy_id` in `config/pilot_run_config.json` to the new `policy_id`; pilot runs read the policy from there (`priority_policy_id` in `play.yaml` applies only to ad hoc runs without `--pilot`). Write the new outputs to a fresh copy of the repository or move `output/final/` aside first, so they do not mix with the thesis results.

### 3. Design a new context structure

A new condition (another way to lay out the same fields) needs changes in these places:

| File | Change |
|---|---|
| `agents/character.py`, `Character._build_reaction_prompt` | Add a branch for the new condition that builds its prompt template from the same placeholders (`{event}`, `{time}`, …, `{observation}`, `{plot}`). Keep the S branch unchanged, since it must stay identical to CharacterBox's prompt. |
| `simulator.py`, `Simulator.load_simulator` | Add the new label to the set of accepted `context_condition` values, and load a priority policy for it if it uses one (as is done for P). |
| `dataloader/research_sidecar.py`, `validate_pilot_config` | Allow the new label in the `conditions` list. |
| `config/pilot_run_config.json` | List the conditions to run, for example `["U", "S", "P", "NEW"]`. |
| `notebooks/*.ipynb`, `tools/compare_runs.py`, `tools/make_label_sheet.py` | Add the new label to `CONDITION_ORDER` / `CONDITIONS` (and a colour in `CONDITION_COLORS`) so the analysis and blind labelling sheets include it. |

The judges never see the condition label, so `evaluate.py` and `evaluate_characterbox.py` need no change. The `S-plus` branch is a worked example: it adds an exploratory condition, S+, which is S plus P's "statements are claims, not verified facts" sentence, together with `--out-dir` and `--pilot-config` options for `run_final.py` so that such runs go to a separate folder.

## Other ways to run

### Ad hoc play

Run an editable, interactive scene from `config/play.yaml` (one condition, terminal dialogue):

```bash
python simulator.py -c config/play.yaml
```

Run all trials of one pilot under every condition without the final-study folder layout:

```bash
python simulator.py -c config/play.yaml --pilot data/research_annotations/characterbox_pilot.json
```

Only the second command applies the pilot's scene, roles, conditions, policy, and scripted turns. Model and output settings come from `play.yaml` in both cases. The pilot run creates a fresh character and memory for every trial and condition, skips the narrator and autonomous play, prints a shared `generation_run_id`, and appends one trajectory row per trial and condition to `output/record/Harry_Potter/trajectory/`.

### Judging a trajectory directly

```bash
python evaluate.py output/record/Harry_Potter/trajectory/openai-gpt-4o-mini_openai-gpt-4o-mini_trajectory.jsonl
```

This judges the latest complete run in the file (add `--generation-run-id <id>` to choose another), both hypotheses in one pass:

- **Consistency (H1, H3):** one judge call per turn, with a strict PASS/FAIL/NA decision and quoted evidence for Context Use, World Consistency, and No Contradiction. The judge sees only the turns up to and including the one being scored.
- **Realism (H2):** CharacterBox's seven-metric critique-then-score evaluation, averaged to one realism score per trial and condition.

Neither judge sees the condition name or priority labels. Results are appended to `output/evaluation/h1_consistency.jsonl` and `output/evaluation/h2_realism.jsonl`; use `--h1-output`/`--h2-output` to change the paths, `-c` for another config, `--h1-rubric-version 11|13|14` for an earlier rubric, and `--h1-only`/`--h2-only` to run one judge. A turn the judge cannot score after every retry is logged to `failed_judgements.jsonl` and skipped, and rerunning the same command fills in only what is missing.

`evaluate_characterbox.py` is the earlier CharacterBox-only evaluation of a whole trajectory, kept for reference. It reports CharacterBox's seven metrics only and writes to `output/evaluation/characterbox/results.jsonl`.

## Tests

```bash
python -m unittest
```

The tests check, among other things, that the S prompt matches CharacterBox's original prompt character for character, that pilot manifests and priority policies are validated, that the simulator and judges handle the controlled pilot runs, and that `run_final.py` skips completed steps.

## Documents

- [docs/research-contract.md](docs/research-contract.md): the research question, conditions, hypotheses, controls, and evaluation definitions.
- [docs/trial-design-guide.md](docs/trial-design-guide.md): how the trials of a pilot are designed.
- [docs/judge-change-log.md](docs/judge-change-log.md): every change to the judges' rubrics and the reason for it.
- [docs/limitations.md](docs/limitations.md): known limitations found during development.
- [docs/characterbox-provenance.md](docs/characterbox-provenance.md): how CharacterBox code is reused and attributed.
- [docs/characterbox-change-record.md](docs/characterbox-change-record.md): every folder-, file-, and symbol-level difference from the inspected CharacterBox repository.
- [ROADMAP.md](ROADMAP.md): the implementation sequence followed during the project.

## CharacterBox relationship

The project is built on CharacterBox (commit 5c19141), which provides the role-playing simulator, the character and scene records, the S prompt, and the realism evaluation. Every reused component is documented with its CharacterBox source file and commit, whether it was copied, adapted, or only inspired the design, the modifications made for this experiment and why, and the applicable licence and attribution.

The local Harry Potter file is sanitised by removing every `chunk` field, and the supplied scene records, not the novels, are the evidence the judges check against. Trial selectors are stored in the pilot manifests, run settings (conditions and priority policy) in `config/pilot_run_config.json`, and priority policies in `config/context_priorities.json`. None of these modifies CharacterBox's runtime records.

## Working rule

Before each implementation step:

1. explain the goal and new terminology;
2. list the exact files proposed;
3. wait for approval;
4. implement only the approved step;
5. demonstrate and test it;
6. update `docs/characterbox-provenance.md` when CharacterBox material is reused or adapted;
7. update `docs/characterbox-change-record.md` for every implementation difference from CharacterBox;
8. stop before the next step.

Whenever an implementation step adds, removes, or modifies a file, import, dependency, class field, parameter, function, branch, data transformation, or runtime behaviour compared with CharacterBox, the corresponding folder summary and file entry in `docs/characterbox-change-record.md` must be updated in the same step. An implementation step is not complete until the change record matches the current repository.
