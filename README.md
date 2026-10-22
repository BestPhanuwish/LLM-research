# Main Research

This repository will investigate whether the way game context is presented to a large language model changes the consistency and realism of generated NPC dialogue.

The same model will receive the same scenario information under three experimental conditions:

1. **Unstructured (U):** all context facts are concatenated into one flat block.
2. **Structured (S):** the same facts are grouped into named categories, with no explicit importance.
3. **Prioritised structured (P):** the same 13 CharacterBox context fields are grouped under an explicit, ordered priority policy.

The principal comparison is **P versus S**, because it isolates the additional effect of prioritisation. **S versus U** measures the effect of structure, and **P versus U** measures the total change from the baseline.

## Project status

**As of 22 Oct 2026:** generation (U/S/P), the H1 consistency judge (final rubric, validated against the researcher's labels on five pilots), and the H2 realism judge are complete. The final study runs pilots 1–10 over several generation seeds; seed 1 of pilots 1–5 is in place (H1 only), and pilots 6–10 are being designed. 161 tests pass. See [Reproducing the final study](#reproducing-the-final-study).

The project currently copies CharacterBox's original character/scene records and single-scene loader with targeted documented adaptations. A schema-v4 pilot manifest selects one scene, player, target, and source Action Reference shared by an ordered list of independent trials, each with its own scripted dialogue-only turns, without modifying CharacterBox runtime records. Conditions and priority-policy ID live separately in the reusable `config/pilot_run_config.json`, auto-loaded whenever `--pilot` selects a manifest. The manifest is used only when explicitly selected with `--pilot`; ordinary `simulator.py -c config/play.yaml` execution reads editable play selectors from YAML, runs once, and requests terminal dialogue. Explicit pilot execution retains model/provider/output settings from YAML, applies the fixed experiment selectors, creates a fresh Character and memory for every (trial, condition) pair, skips Narrator/autonomous generation, and saves condition-labelled CharacterBox records. The machine-readable field-equivalence trace, consolidated paired-result format, original-story dataset, and evaluation pipeline remain unimplemented.

## Activate the virtual environment

Open a terminal in the `main-research` directory and activate the existing virtual environment:

```bash
cd main-research
source .venv/bin/activate
```

When it is active, the terminal prompt normally begins with `(.venv)`. You can confirm that Python is coming from this project with:

```bash
which python
python --version
```

If `.venv` does not exist yet, create it and install the dependencies first:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

To leave the environment later, run `deactivate`.

## Reproducing the final study

Everything the thesis reports is produced by the commands in this section, from files in this repository.

### What is fixed

| Part | Setting | Where |
|---|---|---|
| Character model | `openai/gpt-4o-mini` via OpenRouter, temperature 0.5, max 300 tokens | `config/play.yaml` |
| Generation seed | 1, 2, 3, … — one per repeat of the whole study | `--seed` (overrides `seed` in `play.yaml`) |
| Conditions | U, S, P; P uses the `primary_five_level` priority policy | `config/pilot_run_config.json`, `config/context_priorities.json` |
| Scenes and trials | One manifest per pilot (scene, player, target, 11 trials) | `data/research_annotations/characterbox_pilot*.json` |
| H1 consistency judge | `google/gemma-4-31b-it` via OpenRouter, temperature 0, seed 1, max 4000 tokens, rubric version 14 | `config/evaluate.yaml`, `evaluate.py` |
| H2 realism judge | CharacterBox's critique-then-score evaluation, same judge model, with changes 10 and 12 | `evaluate_characterbox.py`, `docs/judge-change-log.md` |

| Pilot | Manifest | `pilot_id` | Scene |
|---|---|---|---|
| 1 | `characterbox_pilot.json` | `cb_hp_019_luna_neville` | 19 |
| 2 | `characterbox_pilot2.json` | `cb_hp_012_newt_mcgonagall` | 12 |
| 3 | `characterbox_pilot3.json` | `cb_hp_031_dumbledore_harry` | 31 |
| 4 | `characterbox_pilot4.json` | `cb_hp_044_harry_hagrid` | 44 |
| 5 | `characterbox_pilot5.json` | `cb_hp_032_harry_seamus` | 32 |
| 6–10 | `characterbox_pilot6.json` … `characterbox_pilot10.json` | to be added | |

Pilots 1–5 were also used to develop the trials and the H1 rubric; the rubric's agreement with the researcher's labels is measured on them (below).

### Layout

One folder per generation seed and pilot:

```text
output/final/
  seed1/
    p01/
      trajectory.jsonl        33 rows: 11 trials x 3 conditions (simulator.py)
      h1_consistency.jsonl    60 rows: one per target-character turn (evaluate.py --h1-only)
      h2_realism.jsonl        33 rows: one per trial and condition (evaluate.py --h2-only)
      failed_judgements.jsonl only if a judge call failed after every retry
    p02/ ...
  seed2/ ...
```

Every trajectory row records its seed (`generation.seed`), and every H1 row its rubric version (`h1_rubric_version`). Seed 1 of pilots 1–5 is the development run judged with the final rubric, copied from `output/record/Harry_Potter/trajectory/…-p{1..5}.jsonl` and `output/evaluation/prompt_versions/v3/h1_consistency.jsonl`; those runs predate both fields, so `generation.seed = 1` (from `play.yaml` at the time) and `h1_rubric_version = 14` (checked against the stored prompts) were added to the copies.

### Run

Set the OpenRouter key in the terminal session only (both the character model and the judges read `OPENAI_API_KEY`):

```bash
export OPENAI_API_KEY="your-openrouter-key"
```

Generate and judge one seed for any pilots:

```bash
python tools/run_final.py --seed 2 --pilot 1 2 3 4 5 6 7 8 9 10
```

For each pilot this runs, in order: `simulator.py --pilot <manifest> --seed N --trajectory-output output/final/seedN/pNN/trajectory.jsonl`, then `evaluate.py --h1-only`, then `evaluate.py --h2-only` into the same folder. Rerunning the same command after an interruption skips completed steps: generation is skipped when the trajectory is complete, and the judges skip every turn and trial already scored. A partial trajectory stops the run; delete that `trajectory.jsonl` and rerun. Other options:

```bash
python tools/run_final.py --seed 1 --pilot 1 2 3 4 5 --h2-only   # judge an existing trajectory with H2 only
python tools/run_final.py --seed 3 --pilot 6 --dry-run             # print the commands without running them
```

On macOS, prefix long runs with `caffeinate -i` so the machine does not sleep.

### Analyse

Open `notebooks/results_dashboard.ipynb` and run all cells. It reads every `output/final/seed*/p*/` folder, shows which runs are complete (`runs_df`), and reports H1, H2, and H3 by condition, pooled and broken down by trial type, pilot, and seed. Set `SEEDS` or `PILOTS` in its first code cell to restrict the analysis, for example `PILOTS = [6, 7, 8, 9, 10]` to exclude the scenes used for development.

Two more notebooks read the same layout:

- `notebooks/trial_inspector.ipynb`: everything about one trial (set `SEED`, `PILOT`, `TRIAL`): the scene, the U/S/P generation prompts and replies, the H1 judge prompts and decisions, and the H2 critique and scores.
- `notebooks/judge_agreement.ipynb`: the final H1 judge against the researcher's blind labels (seed 1, pilots 1–5), with kappa by metric, trial type, condition, and pilot, and every disagreement exported to `output/comparison/final_judge_disagreements.csv`.

### Judge reliability

The researcher's blind labels for pilots 1–5 (seed 1) are in `data/research_annotations/judge_validation/manual_label/`: `human_labels_<pilot>.numbers` (the labelling sheet), `human_labels_<pilot>.csv` (an export of it), `blind_key_<pilot>.csv` (which of A/B/C is U/S/P), and `labelling_context_<pilot>.md` (what the researcher saw). To reproduce the agreement of the H1 judge for one pilot (Table "Agreement of the consistency judge" in the thesis):

```bash
L=data/research_annotations/judge_validation/manual_label
python tools/judge_agreement_table.py \
  --human $L/human_labels_harry_hagrid.csv --key $L/blind_key_harry_hagrid.csv \
  --results output/final/seed1/p04/h1_consistency.jsonl \
  --out output/comparison/agreement_harry_hagrid
```

The judge selection and rubric development runs behind Appendices C and D of the thesis are kept in `output/evaluation/judge_selection/` and `output/evaluation/prompt_versions/v1|v2|v3/`; `docs/judge-change-log.md` records every rubric change and the reason for it.

### Limits of reproducibility

The seeds make generation and judging repeatable only on a best-effort basis: OpenAI and OpenRouter do not guarantee identical output for the same seed, and OpenRouter may route a request to a different provider. Rerunning a seed will therefore give very similar but not always identical replies and decisions; the saved files under `output/final/` are the record the thesis reports. Hosted models are also retired over time, after which a run can only be reproduced with a substitute model.

## Run the project

Set the provider credential in the current terminal session. Do not place it in `play.yaml` or commit it:

```bash
export OPENAI_API_KEY="your-key-here"
```

Run editable YAML-only controlled play with:

```bash
python simulator.py -c config/play.yaml
```

Run the complete fixed scripted U/S/P pilot explicitly with:

```bash
python simulator.py -c config/play.yaml \
  --pilot data/research_annotations/characterbox_pilot.json
```

Only the second command applies pilot scene, role, condition, policy, mode, round, and fixed-turn selectors. Provider/model and output settings remain in `play.yaml` for both commands.

### Evaluation-ready trajectory output

An explicit pilot run writes one canonical dialogue-trajectory JSONL row for each declared condition to:

```text
output/record/Harry_Potter/trajectory/
  gpt-4o-mini_gpt-4o-mini_trajectory.jsonl
```

The U, S, and P rows from one invocation share a `generation_run_id`. Each row contains the trial and condition identifiers, priority-policy ID, generation settings, canonical scene, player and target profiles, unchanged Action Reference, selected recent memory, ordered player/NPC dialogue turns, target observations, and future objective-evaluation references. The displayed/cleaned NPC dialogue is stored as `npc_dialogue`; the existing model-call record retains the raw response and prompt for auditing.

The simulator prints the shared `generation_run_id` at the beginning and end of the paired pilot. Keep this ID with demo or experiment notes so that the exact run can be selected later.

This trajectory file is the stable input boundary for both evaluation modes:

1. `evaluate.py` — the primary evaluator, producing H1 (per-turn consistency) and H2 (per-trial realism) results from one command;
2. `evaluate_characterbox.py` — a preliminary CharacterBox-compatible supervisor demo.

Existing CharacterBox plot, character, round, narrator, and all-call records continue to be written separately.

### Primary evaluation: H1 consistency + H2 realism

After the pilot has produced its U/S/P trajectory rows, expose the OpenAI credential only in the current terminal session:

```bash
export OPENAI_API_KEY="your-key-here"
```

Then run the primary evaluator:

```bash
python evaluate.py \
  output/record/Harry_Potter/trajectory/openai-gpt-4o-mini_openai-gpt-4o-mini_trajectory.jsonl
```

Like `evaluate_characterbox.py` below, it defaults to the latest complete run in the file (add `--generation-run-id <printed-id>` to select an older one explicitly). It evaluates every trial in that run, both hypotheses, in one pass:

- **H1 (per-turn consistency)**: one judge call per turn, asking for a strict PASS/FAIL/N/A decision plus quoted evidence on three metrics — Context Use, World Consistency, No Contradiction. The judge only ever sees turns up to and including the one being scored, never a later turn.
- **H2 (per-trial realism)**: CharacterBox's seven-metric critique-then-score evaluation (unchanged from `evaluate_characterbox.py`), averaged to one realism score per condition record.

Both omit condition names and priority labels from judge prompts. Results are appended to two separate files:

```text
output/evaluation/h1_consistency.jsonl
output/evaluation/h2_realism.jsonl
```

Pass `--h1-output`/`--h2-output` to change either path, and `-c`/`--config` to use a config other than the default `config/evaluate.yaml`. Use `--h1-rubric-version 11|13|14` to judge with an earlier version of the H1 rubric (default: `h1_rubric_version` in the config, currently 14; see `docs/judge-change-log.md`). Add `--h1-only` or `--h2-only` to run one hypothesis alone; the other lane's output file is then not created or appended to. A turn or record the judge cannot score after every retry is logged to `failed_judgements.jsonl` next to the output and skipped, so one bad answer does not stop the run; re-running the same command skips everything already scored by that judge and retries only what is missing.

### CharacterBox-compatible supervisor demo

This is a preliminary, CharacterBox-only demo mode kept separate from the primary evaluator above; it does not report H1/H2, only CharacterBox's own seven metrics for a whole trajectory. Run the critique-first CharacterBox-compatible evaluator:

```bash
python evaluate_characterbox.py \
  output/record/Harry_Potter/trajectory/openai-gpt-4o-mini_openai-gpt-4o-mini_trajectory.jsonl
```

By default, it reads the final non-empty JSONL row, takes that row's `generation_run_id`, collects only rows with the same ID, and then requires that selected run to contain exactly its declared U/S/P conditions. It does not evaluate every row in the file. If the last run is incomplete, it stops instead of silently selecting an older run. To select a known run explicitly, add `--generation-run-id <printed-id>`. The evaluator omits condition names and priority labels from judge prompts and makes two judge calls per condition: one critique and one seven-metric scoring call. Results are appended to:

```text
output/evaluation/characterbox/results.jsonl
```

The result retains separate Knowledge Accuracy, Emotional Expression, Personality Traits, Behavioral Accuracy, Immersion, Adaptability, and Behavioral Coherence scores, their unweighted average, the critique, judge output, and reproducibility metadata. This is a CharacterBox-compatible preliminary evaluation for demonstration; it does not replace the planned objective or turn-depth analysis.

The final study will use two CharacterBox-compatible data sources: selected sanitised scenes from CharacterBox's generated datasets and scenarios adapted from the researcher's original fictional story. CharacterBox scenes provide direct compatibility testing, while the original setting reduces the risk that pretrained franchise knowledge masks context-grounding failures.

## Step 2 quick check

After creating a virtual environment and installing `requirements.txt`, run:

```bash
python -m unittest -v
```

The tests confirm that the sanitised dataset loads through the original interface, prompt-facing strings remain compatible, actions remain dictionaries, the original model ignores the extra `gender` JSON field, and all 50 development scenes are free of source-book `chunk` fields.

## Inspect the pilot trial

Validate the sidecar against the unchanged CharacterBox dataset and print the
resolved scene, character, action, memory selection, and evaluation evidence:

```bash
python -m dataloader.research_sidecar data/research_annotations/characterbox_pilot.json
```

This command performs no model or network call.

Inspect and validate the reusable four-level priority policy:

```bash
python -m dataloader.context_priorities config/context_priorities.json
```

## Documents

- [AI_HANDOFF.md](AI_HANDOFF.md): a current-state memory, hard-rule checklist, unresolved evaluation decisions, and ready-to-copy prompt for continuing the project with another AI collaborator.
- [ROADMAP.md](ROADMAP.md): the complete implementation sequence and checkpoints.
- [docs/research-contract.md](docs/research-contract.md): the research question, conditions, hypotheses, controls, scope, and evaluation definitions.
- [docs/characterbox-provenance.md](docs/characterbox-provenance.md): how CharacterBox code will be reused and how every adaptation will be recorded.
- [docs/characterbox-change-record.md](docs/characterbox-change-record.md): the current folder-, file-, and symbol-level differences from the inspected CharacterBox repository.

## CharacterBox relationship

CharacterBox is the primary implementation reference because it provides a comparatively complete role-playing simulation codebase. Useful components will be copied or adapted selectively rather than recreating equivalent infrastructure without reason.

Every reused component will be documented with:

- the CharacterBox source file and inspected commit;
- whether code was copied, adapted, or only inspired the design;
- the modifications made for this experiment;
- the reason for each modification;
- the applicable licence and attribution.

CharacterBox's simulator is retained as the implementation foundation with every controlled/dynamic adaptation recorded in the change record. The local Harry Potter file is sanitised by removing every `chunk` field. Only a documented, manually verified subset may be used in final trials, and its supplied scene records—not external franchise canon—will serve as experimental evidence. Trial execution selectors are stored in the schema-v4 dialogue-only pilot manifest; run behavior (conditions, priority-policy ID) is stored separately in `config/pilot_run_config.json`; reusable field-group priority policies remain in `config/context_priorities.json`. None of the three modifies CharacterBox runtime records.

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

Whenever an implementation step adds, removes, or modifies a file, import, dependency, class field, parameter, function, branch, data transformation, or runtime behavior compared with CharacterBox, the corresponding folder summary and file entry in `docs/characterbox-change-record.md` must be updated in the same step. An implementation step is not complete until the change record matches the current repository.
