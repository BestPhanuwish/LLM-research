# Main Research implementation roadmap

## Purpose

This project tests whether context structure and explicit priority affect the consistency and realism of LLM-generated NPC dialogue.

CharacterBox is the sole implementation foundation. Its character-response path and structured English dialogue prompt will be preserved as closely as practical. New code will be limited to the controls required for the `U/S/P` experiment, rather than recreating CharacterBox or integrating other role-playing systems.

Every reused component and modification will be recorded in [docs/characterbox-provenance.md](docs/characterbox-provenance.md). Every current folder-, file-, and symbol-level implementation difference from CharacterBox will be recorded in [docs/characterbox-change-record.md](docs/characterbox-change-record.md) in the same implementation step.

## Central experimental rule

One canonical scenario is rendered under three conditions:

- **U — Unstructured:** the context values appear in a flat block without CharacterBox headings or priority markers;
- **S — Structured:** the original CharacterBox structured dialogue context;
- **P — Prioritised structured:** the same CharacterBox structure and values, with explicit priority tiers and ordering.

For a paired trial, the conditions share the same scenario facts, character, player input/observation, action reference, beliefs, selected memories, model, settings, context limit, and output budget. Only the intended context representation differs.

The primary comparison is `P versus S`. `S versus U` measures structure, while `P versus U` measures the complete representational change.

## Meaning of “close to CharacterBox”

For identical inputs, the S condition must produce the same formatted dialogue prompt and use the same response-generation path as CharacterBox. A compatibility test will protect this baseline before U or P is added.

CharacterBox's complete autonomous simulator is not the baseline for the primary experiment. It independently generates self-beliefs, environment beliefs, synopses, actions, narrator decisions, reactions, state updates, and retrieved memories. Running those operations separately for U, S, and P could give the conditions different semantic inputs. Instead, any such inputs used in a paired trial are generated or selected once and then frozen across all three conditions.

## CharacterBox reuse boundary

### Preserve closely

- `utils/character.py` character and scene models;
- `dataloader/data.py` scene loader;
- the CharacterBox scene/character/action JSON schema;
- the English structured context in `agents/character.py` as S;
- the `generate_dialogue()` instruction and output cleaning;
- the character model-call path, with security/configuration corrections;
- useful output-record fields;
- relevant evaluation concepts from `evaluate.py`.

The S prompt retains CharacterBox's fields: Event, Time, Location, Description, Character Profile, Name, Character Description, Position, Current State, Self Belief, Environment Belief, Recent Memory, Observation, and Action Reference.

### Add only for the experiment

- U and P context renderers around the unchanged S baseline;
- small sidecars containing trial selection and evaluation references;
- a reusable global configuration grouping all 13 CharacterBox context fields by priority;
- information-equivalence checks;
- a paired U/S/P runner with frozen inputs;
- blinded, targeted evaluation records.

### Do not copy into the minimum viable study

- the full narrator-driven autonomous simulator;
- narrator-generated truth or independently generated state changes per condition;
- alternative structured-context architectures or label/order ablations;
- a general game engine or general automatic fact-extraction system;
- graphical interfaces and book-extraction tooling;
- incomplete local-model paths;
- SimsConv adapters or Character-LLM training/evaluation integration.

SimsConv and Character-LLM remain related work and may inform discussion or question design. They are not implementation dependencies or study datasets.

## Build sequence

### Step 1 — Research contract and provenance policy — COMPLETE

**Question answered:** What are we testing, and how will reused code be disclosed?

Created `README.md`, `docs/research-contract.md`, `docs/characterbox-provenance.md`, and this roadmap. The provenance policy fixes CharacterBox commit `5c19141ec04197bcdb2e7c7f7e235a5657952977` and requires file-level modification records.

**Checkpoint:** Proposed work can be checked against the research scope, and CharacterBox reuse has an auditable process.

### Step 2 — CharacterBox records, loader, and development data — COMPLETE

**Question answered:** Can the original CharacterBox data interface be reproduced before adding an intervention?

Copied CharacterBox's character/scene models and loader with only formatting changes. Imported 50 generated Harry Potter scenes as a local compatibility fixture and mechanically removed every source-book `chunk` field. No research-specific runtime classes were added.

The upstream JSON includes `gender`, but the original CharacterBox model does not declare it and Pydantic ignores it. This behavior is intentionally preserved.

The final evaluation uses two sources: a documented, manually verified subset of sanitised CharacterBox-generated scenes and scenarios from the researcher's original fictional setting. CharacterBox-derived data should not be redistributed as original research data or treated as canonical franchise ground truth.

**Checkpoint:** The sanitised fixture reproduces CharacterBox's scene, character, and action loading behavior.

### Step 3 — Faithful CharacterBox structured response baseline — COMPLETE

**Question answered:** Can one dialogue response be generated through a prompt-equivalent CharacterBox path before U or P exists?

Show and then copy the smallest relevant portion of `agents/character.py` and its required model-call support. Preserve:

- the English structured prompt as S;
- `generate_dialogue()`'s instruction;
- the same prompt inputs and names;
- the same first-line/character-prefix response cleaning.

Use one fixed observation, action reference, belief state, and memory input. A compatibility test must prove that identical inputs produce the same fully formatted S prompt as CharacterBox.

CharacterBox's credential-bearing configuration will not be copied. Credentials will be read from environment variables and excluded from logs. This is a necessary security correction, not a research intervention.

**Checkpoint:** One controlled S response can be generated, and its prompt-equivalence test passes. No U or P renderer exists yet.

Implemented an English-only adaptation of `agents/character.py`, removing language branches while retaining CharacterBox's English prompt strings and generation behavior. `tests/test_characterbox_character.py` executes `_generate_reaction()` and `generate_dialogue()` with deterministic fake LLM, chain, and memory collaborators. It verifies the complete formatted S prompt, token-budget input, raw and processed response, action reference, observation, and memory-save payload without an API call. Six tests passed when Step 3 was completed; seven now pass after the later real-scene flow compatibility test. No U/P, narrator, human-player agent, autonomous simulator, or real provider was added.

### Step 4 — Dual-source study data and minimal sidecars

**Question answered:** Can the controlled research material use CharacterBox's existing schema without replacing its runtime models?

Select a small, manually verified subset of sanitised CharacterBox-generated scenes and hand-author a small set of original-story scenarios using CharacterBox's unchanged `scene`, `characters`, `actions`, and `plot` structure.

Keep trial selectors in separate sidecars for both sources rather than modifying CharacterBox records or classes. Initially include only:

- a stable trial, scene, distinct player/target-character, target action, and memory selection;
- one fixed, non-empty player dialogue; controlled interaction actions are excluded;
- an evaluation question;
- the supporting source references for that question;
- an NPC-knowledge label only when needed to test information leakage.

The sidecar validator checks dataset source, duplicate IDs, source references, distinct player/target selection, target-action ownership, player inputs, and memory-action existence. World values are resolved from the source dataset and are not copied into the sidecar. CharacterBox scene facts selected for evaluation are manually checked against the supplied record. The validator does not introduce a general authority, action, or game-state framework.

**Checkpoint:** Selected records from both sources load through the unchanged CharacterBox loader; CharacterBox scene facts are manually checked; both sidecars retain dataset provenance and validate with understandable errors for broken references.

Step 4 is in progress. `data/research_annotations/characterbox_pilot.json`
defines one schema-v3 simulator-compatible two-character pilot for scene 19, with Luna as the
human-controlled role and Neville as the sole target NPC. It stores U/S/P conditions,
controlled mode, a priority-policy selector, and an ordered scripted-turn list in addition
to source/evaluation selectors. `dataloader/research_sidecar.py` verifies its source
dataset, scene, distinct roles, sequential non-empty dialogue turns, target-owned Action Reference,
selected memory actions, conditions, and evaluation source references. `config/context_priorities.json` separately declares one reusable
four-level policy, and `dataloader/context_priorities.py` proves that all 13
CharacterBox fields are assigned exactly once. The original-story dataset and
sidecar have not yet been added, so the full Step 4 checkpoint is not complete.

### Step 5 — U and P around the unchanged S baseline

**Question answered:** Can context representation change without changing semantic information or the character response logic?

- Keep S equal to CharacterBox's original structured prompt.
- Render U from the same values without CharacterBox category headings or priority instructions.
- Render P from the same values, grouping all 13 fields under the declared priority levels, instructions, and ordering.

All renderers return the formatted context and a machine-readable field/value trace. Assertions enforce:

```text
fields-and-values(U) = fields-and-values(S) = fields-and-values(P)
```

Priority labels, instructions, grouping, and ordering are treated as one prioritisation mechanism. The initial study uses only `primary_four_level`. Policies with more levels or one field per level, label-only/order-only variants, filtering, and retrieval remain possible later ablations and are excluded from the initial implementation.

**Later ablation candidate — state/action-reference authority vs. Observation:** `primary_four_level` keeps `states` and `action_reference` subordinate to Observation (both are frozen scene-start snapshots controlled interaction never regenerates, while Observation is live ground truth). Discussed 2026-08-30: the opposite ordering — promoting `states`/`action_reference` above Observation — is a genuine alternative worth testing separately, since it trades naturalness (risk of rigid, repetitive dialogue that ignores what was just said) for a sharper test of whether explicit prioritisation can override the model's default recency bias toward the most recent context. Not part of the primary policy; a candidate second policy for a future ablation study, requiring the same approval and dated-revision process as any other config change.

**Checkpoint:** U/S/P contain equal fact/value sets, S still passes the CharacterBox prompt-equivalence test, and the intended differences are inspectable.

Step 5 is in progress. `Character._build_reaction_prompt()` now selects a flat
U prompt, the exact protected CharacterBox S prompt, or a P prompt generated
from one validated field-group policy. `generate_dialogue()` remains the single
response, cleaning, and memory-save path. Deterministic tests verify all three
branches and reject unknown conditions. The CharacterBox pilot now loads through
the unchanged data loader and renders the same source-selected values under U/S/P
in a deterministic integration test. The machine-readable field/value equivalence
trace is not implemented, so the full Step 5 checkpoint is not complete.

### Step 6 — Paired three-condition runner

**Question answered:** Can all three conditions be called fairly through the same CharacterBox-derived response path?

Use one model provider and identical settings for U/S/P. For each trial, freeze the question/observation, action reference, beliefs, memory, facts, and output budget. Save immutable records containing:

- condition and blinded presentation identifier;
- prompt and response;
- fact trace and prompt hash;
- model/settings and token counts;
- scenario, character, and question identifiers.

Use a deterministic fake model only for automated tests, then connect one real OpenAI-compatible provider. Do not log credentials.

**Checkpoint:** One command produces a complete paired U/S/P record using the same response path and fixed inputs.

Step 6 is in progress. The adapted `simulator.py` treats the validated pilot manifest
as a non-secret override layer over `play.yaml`, derives its round count from scripted
turns, and runs U, S, and P with a fresh Simulator/Character/memory instance for each
condition. Controlled turns bypass terminal input and still call only the selected NPC's
existing `generate_dialogue()` path. Existing CharacterBox JSONL categories contain
condition and pilot metadata. A consolidated immutable paired-result record, field trace,
prompt hash, and token-count snapshot remain to complete the checkpoint.

### Step 7 — Focused evaluation

**Question answered:** Does prioritisation improve grounded and believable character responses?

Adapt, rather than copy unchanged, CharacterBox's relevant evaluation dimensions:

- knowledge accuracy;
- personality traits;
- immersion;
- adaptability;
- behavioural coherence.

Add targeted judgments for fact consistency, contradiction, required-fact use, and knowledge leakage when supported by the sidecar. Use simple deterministic checks where an answer is exact and a blinded human or LLM rubric where interpretation is required. The evaluator sees neutral canonical evidence, not the U/S/P label or priority formatting.

Do not build a general semantic fact extractor or treat the LLM judge as unquestioned ground truth.

**Checkpoint:** Known-good and deliberately inconsistent sample responses receive the expected targeted results, and condition labels remain hidden from evaluators.

### Step 8 — Pilot and final study

**Question answered:** Is the focused design reliable enough to run at study scale?

Run a small pilot using both selected CharacterBox-generated scenes and original-story scenarios. Inspect information equivalence, question answerability, judge behavior, prompt length, response variance, and costs before scaling. Record dataset source for every trial and report results separately by source before any combined summary.

The minimum viable study is the controlled single-turn U/S/P comparison. If time and proposal requirements permit, add a short scripted multi-turn extension in which identical dialogue history and fixed state are supplied to all conditions. Do not make the full autonomous narrator/memory simulator part of the critical path.

Complete configuration, raw-output, licence/provenance, analysis, and reproduction documentation only for the implemented study.

**Checkpoint:** A fresh environment can reproduce the pilot trial and its evaluation, and the final study contains no unplanned dataset or architecture integration.

## Expected project growth

```text
main-research/
├── README.md
├── ROADMAP.md
├── simulator.py
├── docs/
├── config/
├── data/
│   ├── generated_data/
│   └── research_annotations/
├── agents/
├── experiments/
├── evaluation/
├── tests/
├── results/
└── third_party/
```

This is a destination, not a structure to create at once. A folder appears only when its approved step needs it.

## Approval and teaching workflow

For every step:

1. Explain the goal and new terminology.
2. Show the relevant CharacterBox source before reuse.
3. List the exact destination files and planned modifications.
4. Wait for approval.
5. Implement only that step.
6. Update the provenance ledger in the same step.
7. Update the change record for every added, removed, or modified file, import, dependency, class field, parameter, function, branch, data transformation, or runtime behavior compared with CharacterBox.
8. Demonstrate and test the result.
9. Summarise and stop before continuing.

No later step is implemented automatically. An implementation step is not complete until the change record matches the current repository.
