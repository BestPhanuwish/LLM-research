# Main Research

This repository will investigate whether the way game context is presented to a large language model changes the consistency and realism of generated NPC dialogue.

The same model will receive the same scenario information under three experimental conditions:

1. **Unstructured (U):** all context facts are concatenated into one flat block.
2. **Structured (S):** the same facts are grouped into named categories, with no explicit importance.
3. **Prioritised structured (P):** the same 13 CharacterBox context fields are grouped under an explicit, ordered priority policy.

The principal comparison is **P versus S**, because it isolates the additional effect of prioritisation. **S versus U** measures the effect of structure, and **P versus U** measures the total change from the baseline.

## Project status

**Steps 1–3 are complete; Step 4 has one validated simulator-compatible CharacterBox pilot manifest and one validated four-level priority policy; Step 5 U/S/P prompt branches pass deterministic tests; and Step 6 can run the same scripted pilot turn through fresh U, S, and P Simulator instances. Ordinary YAML-controlled play and fixed pilot execution are separate commands. An Apple Silicon OpenMP guard prevents the observed PyTorch/FAISS retrieval crash. Fifty-six tests pass.**

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
  output/record/Harry_Potter/trajectory/gpt-4o-mini_gpt-4o-mini_trajectory.jsonl
```

Like `evaluate_characterbox.py` below, it defaults to the latest complete run in the file (add `--generation-run-id <printed-id>` to select an older one explicitly). It evaluates every trial in that run, both hypotheses, in one pass:

- **H1 (per-turn consistency)**: one judge call per turn, asking for a strict PASS/FAIL/N/A decision plus quoted evidence on three metrics — Context Use, World Consistency, No Contradiction. The judge only ever sees turns up to and including the one being scored, never a later turn.
- **H2 (per-trial realism)**: CharacterBox's seven-metric critique-then-score evaluation (unchanged from `evaluate_characterbox.py`), averaged to one realism score per condition record.

Both omit condition names and priority labels from judge prompts. Results are appended to two separate files:

```text
output/evaluation/h1_consistency.jsonl
output/evaluation/h2_realism.jsonl
```

Pass `--h1-output`/`--h2-output` to change either path, and `-c`/`--config` to use a config other than the default `config/evaluate.yaml`.

### CharacterBox-compatible supervisor demo

This is a preliminary, CharacterBox-only demo mode kept separate from the primary evaluator above; it does not report H1/H2, only CharacterBox's own seven metrics for a whole trajectory. Run the critique-first CharacterBox-compatible evaluator:

```bash
python evaluate_characterbox.py \
  output/record/Harry_Potter/trajectory/gpt-4o-mini_gpt-4o-mini_trajectory.jsonl
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
