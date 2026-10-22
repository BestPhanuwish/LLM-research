# CharacterBox implementation change record

## Comparison baseline

This document describes the current code and file differences between this repository and CharacterBox. The comparison baseline is:

- CharacterBox repository: `https://github.com/Paitesanshi/CharacterBox`
- Local source inspected: `/Users/macbookproretina/Downloads/Mycomputer/Usyd/Yr4 2026/thesis/CharacterBox`
- Commit: `5c19141ec04197bcdb2e7c7f7e235a5657952977`

This is a current-state implementation record, not a chronological log. It records files that exist now and CharacterBox files that have been deliberately excluded. A possible future file is not listed until it is actually added. Generated artifacts such as virtual environments, `__pycache__`, `.pyc` files, `.DS_Store`, logs, and test caches are not implementation files and are omitted.

## Mandatory recording rule

Whenever an implementation step adds, removes, or modifies a file, import, dependency, class field, parameter, function, branch, data transformation, or runtime behavior compared with CharacterBox, the corresponding folder summary and file entry in this document must be updated in the same step. An implementation step is not complete until this record matches the current repository.

The separate [characterbox-provenance.md](characterbox-provenance.md) records code origin, reuse category, licensing, and attribution. This document records the concrete filesystem and code differences.

# Repository root

## Folder-level comparison

### Added in this project

- `.gitignore`
- `AI_HANDOFF.md`
- `ROADMAP.md`
- `evaluate_characterbox.py`
- `evaluate.py`

### Intentionally left out from CharacterBox

- None recorded at the repository-root file level. Files that have merely not been implemented or copied are not listed as excluded.

### Present in both but replaced or modified

- `README.md`: replaced with project-specific research and implementation documentation.
- `requirements.txt`: reduced to the dependencies currently required by the copied baseline, with one compatibility pin added.
- `simulator.py`: adds controlled/dynamic execution, paired U/S/P pilot routing, dialogue-only turns, evaluation-ready trajectory export, and credential-safe logging while retaining the dynamic CharacterBox path.

### Present in both without modification

- `llm/`: exact CharacterBox provider-adapter package; it is runtime code, not test infrastructure.

## Files

### `.gitignore`

- Status: Added by this project; CharacterBox has no tracked counterpart at the inspected commit.
- Purpose: Excludes the local virtual environment, Python caches, compiled Python files, and macOS metadata.
- Runtime consequence: None.

### `AI_HANDOFF.md`

- Status: Added by this project; CharacterBox has no counterpart.
- Purpose: Provides a credential-free transfer prompt and current-state memory for moving the research collaboration to another AI system. It prominently identifies CharacterBox as the heavily reused/adapted implementation foundation, requires academically accurate attribution and minimal inherited-code changes, defines an explicit approval-gated one-step-at-a-time coding protocol, and distinguishes implemented behavior, binding experimental/workflow rules, the proposed but unimplemented two-lane evaluation direction, unresolved decisions, commands, and primary files.
- Behavioral consequence: Documentation only. It does not modify generation or evaluation behavior and explicitly requires code to take precedence over stale descriptive status text.

### `README.md`

- Status: Project-specific replacement of the CharacterBox root README.
- CharacterBox baseline: Installation, simulator quick-start, provider configuration, and evaluation commands for the autonomous CharacterBox application.
- Current implementation: Explains the U/S/P research question, current build status, dual-source dataset decision, CharacterBox relationship, security boundary, and approval workflow.
- Behavioral consequence: Documentation only; it does not change runtime behavior.

### `ROADMAP.md`

- Status: Added by this project; CharacterBox has no counterpart.
- Purpose: Defines the approved implementation order, CharacterBox reuse boundary, U/S/P controls, field/value equivalence, global priority policy, paired runner, and evaluation checkpoints.
- Behavioral consequence: Documentation only, but implementation work is not considered complete unless it follows the approval and record-update rules stated here.

### `requirements.txt`

- Status: Modified from CharacterBox's dependency list.
- Preserved direct pins: `pydantic==1.10.12`, `langchain==0.1.11`, `langchain-community==0.0.27`, `langchain-core==0.1.46`, `langchain-experimental==0.0.53`, `langchain-openai==0.1.1`, and `openai==1.55.3`.
- Added direct pin: `aiohttp==3.9.5`, preventing an incompatible newer `aiohttp` release from breaking the tested LangChain stack.
- CharacterBox direct dependencies not currently declared: `langchain-text-splitters`, `langsmith`, `pandas`, `termcolor`, `tqdm`, `yacs`, `sentence-transformers`, `transformers`, `tiktoken`, and `faiss-cpu`.
- Reason: The OpenAI-compatible provider pins are retained for the adapted CharacterBox simulator. The remaining undeclared runtime dependencies are installed in the current environment but not yet pinned in this reduced project file.
- Verification: The fifty-six-test suite exercises no real provider call; a separate local native retrieval smoke test and live controlled/dynamic pilot runs exercise the runtime paths.

### `simulator.py`

- Status: Adapted from CharacterBox `simulator.py` with marked changes in `Simulator.__init__()`, `load_simulator()`, `save_record()`, `round()`, `agents_creation()`, and `create_character()`; all other functions remain unchanged.
- Module initialisation: On macOS only, sets default `OMP_NUM_THREADS=1` and `TOKENIZERS_PARALLELISM=false` before importing FAISS and the sentence-transformer/PyTorch stack. Explicit user environment settings remain authoritative because `setdefault()` is used.
- Native-crash rationale: The first Apple Silicon live pilot raised `EXC_BAD_ACCESS`/`SIGSEGV` in LLVM OpenMP while PyTorch performed `index_select`; the macOS crash report showed both FAISS and PyTorch OpenMP libraries loaded. Single-threaded OpenMP removed the failing native concurrency boundary.
- Research consequence: The guard affects native worker parallelism/performance only; it does not change scene data, embeddings model, FAISS index type, retrieval scoring, prompt contents, model parameters, or U/S/P selection.
- `Simulator.__init__()`: Adds `self.dynamic_play = self.config.get("dynamic_play", True)`. The fallback `True` preserves original CharacterBox behavior for configurations without the research field.
- `Simulator.agents_creation()`: Preserves the original Narrator key/base lookup and `create_narrator()` call when `dynamic_play` is true. When false, it returns `narrator = None` after retaining the original human/NPC creation loop. Passes `score_memories=self.dynamic_play` to `create_character()`.
- `Simulator.create_character()`: Adds a `score_memories` parameter (default `True`, preserving original behavior for any other caller). Selects the unmodified `GenerativeAgentMemory` when true, `agents.character.NoScoreGenerativeAgentMemory` when false; all other construction is unchanged.
- Human observation repair: CharacterBox's human branch executes `continue` before creating `round_obs[role_id]`, although `one_step()` later reads and clears that entry for every agent. The adapted branch initialises the human buffer with the same `last_round` value used for NPCs.
- `Simulator.save_record()` path-safe filenames (2026-10-14): All record filenames now start with a `record_prefix` built from `utils.path_safe_model_name()` applied to `narrator_llm` and `character_llm`, instead of the raw model names. OpenRouter model ids contain `/` (e.g. `openai/gpt-4o-mini`), which `os.path.join` would otherwise treat as missing subdirectories, so the write would fail after all model calls had been made. Plain OpenAI ids are unchanged, so earlier filenames (`gpt-4o-mini_gpt-4o-mini_*.jsonl`) are unaffected; OpenRouter runs save as `openai-gpt-4o-mini_openai-gpt-4o-mini_*.jsonl`. Saved record contents (including `generation.character_model`) keep the real model id.
- `main()` log filename (2026-10-14): The default simulation log path `output/log/simulation/<title>/<narrator>_<character>_<scene>_character_simulation.log` uses the same `utils.path_safe_model_name()` conversion; the first OpenRouter run failed at startup with `FileNotFoundError` before this fix (no model calls were made).
- `Simulator.load_simulator()`: Dynamic mode skips controlled research loading. YAML-only controlled mode resolves `target_character_id` and `action_id` from editable configuration, loads no sidecar, stores no scripted turns, and remains interactive. Explicit pilot mode validates the CLI-selected schema-v4 pilot manifest, checks its resolved source dataset, scene ID, and player ID against the effective configuration, selects exactly one trial by `trial_id` from the pilot's `trials` list, and auto-loads the pilot run-config referenced by `pilot_config_path` to resolve conditions and priority-policy ID. Action Reference is resolved once at the pilot level (same target NPC, same scene, for every trial) rather than per trial. Both controlled paths resolve the Action Reference from source `Data.init_actions`.
- Condition loading: Controlled mode accepts only U/S/P. U and S leave `priority_policy` empty; P validates `priority_config_path` and resolves exactly one `priority_policy_id`, sourced from the pilot run-config in pilot mode or from `play.yaml` in YAML-only mode.
- Stored controlled values: `controlled_trial` (now `trial_id`/`pilot_id`/`source_dataset` only — no copied `recent_memory_action_ids` or `evaluation_cases`), `controlled_target_id`, `controlled_action_reference`, `controlled_turns`, `dataset_source`, `pilot_conditions`, `context_condition`, and optional `priority_policy`.
- `Simulator.round()`: Adds an early-return controlled branch. It reads one non-empty HumanPlayer dialogue, combines it with CharacterBox's existing `last_round` transcript, and calls only the selected target's existing `generate_dialogue()` with the source Action Reference, `context_condition`, optional `priority_policy`, and `remember=False`. After the reply it saves the player's line and then the NPC's reply to the NPC's memory (`Name: dialogue`), matching CharacterBox's dynamic-play practice of storing another character's dialogue in the affected character's memory ahead of its own reaction (added 2026-09-29).
- Dialogue-only controlled input: Player physical actions and NPC action generation are excluded. Blank dialogue causes the same controlled turn to be requested again before any NPC call. The initial source Action Reference remains a prompt field and is unchanged across U/S/P.
- Scripted controlled input: When validated pilot turns exist, `round()` selects the matching one-based turn, labels input details `pilot_manifest`, bypasses all terminal input, and rejects a round beyond the supplied turn list. The interactive fallback remains available to configs without scripted turns.
- Controlled history: Reuses `last_round` directly rather than generating a synopsis or Narrator summary. Round 1 receives CharacterBox's source initial history and later rounds receive the immediately previous dialogue-only transcript.
- Controlled omissions: The branch does not call belief updates, synopsis generation, NPC action generation, other characters, Narrator, reactions, character-state updates, scene updates, or plot summaries.
- Record compatibility: Human dialogue and target dialogue use CharacterBox `Message`, `round_record`, `character_record`, `records`, `last_round`, and logger shapes. The branch clears transient round records after copying them, matching the original round boundary.
- Dynamic preservation: When `dynamic_play` is true, execution follows the CharacterBox round body with only the marked human belief/synopsis compatibility repairs described below; NPC/Narrator ordering and all subsequent adjudication/state/scene logic remain unchanged.
- Dynamic HumanPlayer belief repair: The original loop calls `update_self_belief()` and `update_env_belief()` on every agent although HumanPlayer has neither method. The adapted loop skips only `data.role_id`; every NPC retains the original calls and order.
- Dynamic synopsis repair: CharacterBox hard-codes `characters[0]` as synopsis generator. The adapted path retains character 0 when it is an NPC, but selects the first NPC when character 0 is the human role; an all-human dynamic scene is rejected because it has no generated synopsis source.
- `Simulator.save_record()`: Dynamic mode retains CharacterBox's Narrator-plus-agent `all_actions` collection. Controlled mode copies only the target NPC's `all_actions`, avoiding the absent Narrator and excluding human terminal input from model-call traces.
- Optional inherited cost estimate: `save_record()` reads `calculate_cost`, defaulting to `True` for compatibility. When false, it skips CharacterBox's GPT-2 token-count/legacy-price estimate, records `total_cost` as null, and retains measured model-call durations. This prevents irrelevant over-1024-token GPT-2 tokenizer warnings for the configured model.
- Blank dynamic human reaction: In `one_step()`, an empty HumanPlayer reaction is recorded as `reaction_skipped`, omitted from Narrator result input, and does not move the human from `acting` to `acted`; the player can therefore take the normal turn later in that round. A non-empty human reaction retains CharacterBox's reaction-consumes-turn scheduling.
- Controlled record metadata: Adds `dynamic_play`, nullable/manual `trial_id`, nullable `trial_type` (from the pilot trial's optional `type`, added 2026-09-29), nullable `pilot_id`, `dataset_source`, player/target IDs, configured round count, pilot condition list, current `context_condition`, and nullable `priority_policy_id` to every controlled JSONL category. YAML-only runs store their configured round count and an empty pilot-condition list; explicit pilots store scripted-turn count and declared conditions.
- Evaluation-ready trajectory export: Controlled saves additionally append one schema-v1 `controlled_dialogue_trajectory` row per (trial, condition) under `output/record/<title>/trajectory/`. A shared `generation_run_id` binds every trial and every U/S/P condition from one pilot invocation. Each row contains condition/policy/model/pilot/trial identifiers, canonical scene and role profiles, source Action Reference, ordered displayed player/NPC dialogue, and target observations. `recent_memory` and `evaluation_cases` are no longer part of the trajectory row: controlled trials seed no memory, and sidecar-authored evaluation cases were dropped as unused. This is the common input contract for CharacterBox-compatible and future turn-wise evaluators.
- Displayed-response boundary: Controlled character/round records now store the cleaned dialogue actually shown by the simulator as `detail.text`; when the provider returned different raw text, it is retained separately as `detail.raw_text`. Model-call traces continue to preserve the original raw response and prompt.
- Controlled record contents: Character and round files retain only human dialogue and target dialogue for controlled turns; the Narrator record is empty; the all-actions file contains only target model calls; plot records retain the unchanged source scene with no controlled generated plot/synopsis entries.
- CLI parameter `--pilot`: Added as the only pilot-activation mechanism. Omitting it guarantees that `simulator.py` does not load a pilot manifest.
- CLI parameters `--seed` and `--trajectory-output` (2026-10-22): `--seed` overrides `seed` from `play.yaml`, and the trajectory row's `generation` block now records `seed` beside model, temperature and max_token. `--trajectory-output` makes `save_record()` append the trajectory to that file (parent folder created) instead of `output/record/<title>/trajectory/<prefix>trajectory.jsonl`; all other record files keep their CharacterBox paths. Both are used by `tools/run_final.py`, which writes one folder per seed and pilot under `output/final/`. Without the options, behaviour is unchanged.
- `apply_pilot_overrides(config, pilot_path)`: Added. When no explicit path is supplied, it removes/ignores the former YAML `research_sidecar_path` activation key so older local configurations cannot silently attach fixed input. Otherwise it validates the CLI-selected schema-v4 pilot manifest, stores its resolved path internally, and overrides scene path/ID, player role, mode, pilot-level target/action, and the resolved `pilot_config_path` while leaving provider/model/output settings in `play.yaml`. Trial ID and round count are resolved per trial inside `run_pilot_conditions()`, not here, because one pilot now holds multiple independent trials.
- `run_pilot_conditions()`: Added. Auto-loads the pilot run-config (`conditions`, `priority_policy_id`) from `pilot_config_path`, then loops every trial in the pilot under every declared condition, cloning configuration and calling `run_simulation()` once per (trial, condition) pair so each gets a fresh Simulator, Character, and GenerativeAgentMemory. One shared `generation_run_id` is printed before the first call and after the whole pilot completes, covering every trial and condition, so it can be copied into a downstream evaluator CLI.
- `run_simulation()`: Retains the CharacterBox round loop, adds whole-run duration storage/saving, returns the completed Simulator for deterministic orchestration tests, and is now the shared single-condition execution path.
- `main()`: Routes YAML-only invocation directly to one `run_simulation()` call. It calls `run_pilot_conditions()` only when `--pilot` explicitly selected a manifest.
- Research marking: Constructor storage, controlled loading/round, Narrator routing, and the human observation repair are enclosed by explicit `BEGIN/END RESEARCH EXTENSION` or `MODIFICATION` comments.
- Verification: Twenty deterministic mode tests cover explicit manifest-over-runtime overrides, no-manifest configuration preservation, YAML-only interactive controlled loading, fresh U/S/P condition configs, scripted terminal bypass, expanded metadata, trajectory export, credential redaction, and all prior controlled/dynamic behavior. A separate cached-model smoke test covers sentence-transformer/FAISS retrieval without a provider call.

### `evaluate_characterbox.py`

- Status: Adapted from CharacterBox `evaluate.py`; the source attribution and MIT notice are retained in the module header.
- Preserved behavior: Copies the upstream critic wording, scoring rubric, evaluation steps, response format example, seven metric names, 1/3/5 anchors, full-character-trajectory unit, critique-first workflow, critique-conditioned scoring, and unweighted average verbatim. Exception since 2026-10-21: one added sentence per prompt naming the evaluated character (next bullet).
- Character block lists Position and State (2026-10-21): **Differs from CharacterBox's evaluation input.** `format_trajectory()` previously rendered only the target's name and description under the character heading, so the H2 judge never saw the NPC's supplied position or state and could not tell a supplied detail from an invented one. In the judge bake-off, `qwen/qwen3-235b-a22b-2507` critiqued pilot 1 `t02` U for "no canonical reference to a 'big rock' near the Shrieking Shack… an unverified element", although "Hiding behind a large rock" is Neville's supplied position, and scored that trial 1 on every metric. The block now adds `Position: …` and `State: …` lines when the record has them; the scene block, the rest of both prompts, the metrics and the scoring are unchanged. The NPC itself receives these fields in every condition, so the judge now sees the same character facts the NPC was given. H2 results before this change are not comparable with later ones. Verification: `test_character_block_includes_position_and_state_when_supplied`.
- Target-only instruction (2026-10-21): **Differs from CharacterBox.** Upstream, the critique prompt opens "Please execute the following role-play and identify any issues based on these strict evaluation criteria:" and the scoring prompt "Please evaluate the role-playing ability of the character based on actions across multiple turns…"; neither says which character is evaluated, which was unproblematic upstream because every line in a CharacterBox trajectory is model-generated. In this project the other character's lines are fixed, researcher-written probes (neutral checks, false claims, repeated recall questions), and the judge critiqued them: in the pilot 1–5 H2 results (165 critiques, judge gpt-4o), roughly 1 in 5 faulted the player's line (e.g. "The logical coherence is disrupted by Newt's question about the location and time, which seems out of place"; "significant content redundancy, particularly with Harry repeatedly asking about the remedy's details"), and the scoring step is told to use the critique. `build_critic_prompt()` now inserts `TARGET_ONLY_CRITIC_NOTE` directly after the retained opening line: "Evaluate only {name}'s actions and dialogue. The other character's lines are fixed test inputs written by the researcher; do not critique them, and judge {name}'s replies as responses to them." `build_score_prompt()` inserts `TARGET_ONLY_SCORE_NOTE` directly after its retained opening sentence: "Score only {name}; the other character's lines are fixed test inputs and are not part of the evaluation." `{name}` is the target character's name from the record. The ten critic criteria, the seven metrics and their 1/3/5 anchors, the evaluation steps, the response format, the critique-then-score order and the averaging are unchanged. Behavioral consequence: H2 scores produced before this date (including `output/evaluation/old-context/h2_realism.jsonl`) are not comparable with later ones; all pilots are re-run with the new prompts. The fixed probes are identical across U, S and P, so the earlier behaviour added noise rather than a condition bias. Verification: `tests/test_characterbox_evaluation.py::test_prompts_name_only_the_target_character` checks both notes are present, use the target's name, and follow the retained opening lines; the existing verbatim-wording test still passes.
- Input adaptation: Reads schema-v1 controlled trajectory JSONL, selects every complete per-trial paired condition set sharing one `generation_run_id`, requires every pilot-declared condition exactly once per trial, and evaluates only the target NPC. It does not use CharacterBox's latest-scene selection or character-profile duplicate suppression because both would collapse paired U/S/P records.
- Multi-trial adaptation: `load_trajectory_run()` groups selected records by `(trial_id, context_condition)` and returns a list of trials, each a list of that trial's condition records in declared-condition order, because one `generation_run_id` now spans every trial in a pilot (added when pilot manifests moved to schema v4's multi-trial structure; see the 2026-08-30 provenance entry). `main()` evaluates every trial in the selected run in one invocation.
- Dialogue adaptation: Renders dialogue-only controlled turns using CharacterBox's legacy `Observation` and `Action` judge labels; no physical interaction action is fabricated.
- Blinding: Because the research trajectory adds metadata that upstream CharacterBox never had, the input adapter deliberately does not render U/S/P labels, priority-policy identifiers, generation prompts, or model-call traces. This does not alter the upstream rubric; it prevents the judge from knowing which experimental condition produced a response.
- Validation/output adaptation: Parses each metric independently, rejects duplicate, missing, and out-of-range scores, retries malformed score output, and appends auditable JSONL containing identifiers, scores, average, critique, judge response, and both evaluation prompts.
- `judge_text()` empty-response diagnostics (2026-09-16): Raises `ValueError` with the provider's `finish_reason` (and `refusal` text when present) when `.content` is empty *or whitespace-only* (`not response.content.strip()`, not just `not response.content` — a whitespace-only string such as `"\n"` is truthy in Python and would otherwise slip past a bare truthiness check straight into `json.loads`, reproducing the same confusing error one layer down), instead of silently returning it and letting the failure surface many calls later as an opaque `json.loads` error. `evaluate_trajectory()`'s score-retry loop now calls `judge_text()` inside its `try:` block (previously outside, so a raised error would have skipped the retry loop entirely) so an empty response is retried exactly like a malformed one. Both retry loops (here, and `evaluate.py`'s `evaluate_h1_turn()`) also now print a line on every failed attempt (`[H1 retry n/N] <trial> <condition> round <r>: <error>` / `[H2 retry n/N] <trial> <condition>: <error>`), plus the raw judge response text when one was actually received (`    raw judge response: <repr>`, omitted when `judge_text()` itself raised, since there is no text to show) — previously only the *last* attempt's error was ever visible, and never the raw text at all.
- `evaluate.py:parse_h1_response()` markdown-fence/preamble recovery (2026-09-16, same day, second finding): `"Expecting value: line 1 column 1 (char 0)"` turned out not to be unique to a genuinely empty response — a live `gpt-4o` run reproduced it with non-empty content, because that exact error also fires for any text that does not start with valid JSON at position 0, including a ` ```json ` fence or a conversational preamble some models add despite the prompt asking for exactly one JSON object and nothing else. New `_extract_json_object()` strips a leading/trailing code fence and falls back to the substring between the first `{` and last `}` when the raw text does not parse directly; `parse_h1_response()` tries the raw text first (unchanged behaviour for already-valid JSON) and only falls back to this recovery on failure, still raising the original `"Judge did not return valid JSON"` error if both attempts fail. See the 2026-09-16 provenance entry.
- `judge_text()` rate-limit retry (2026-09-23): Wraps `llm.invoke()` in a retry loop that catches `openai.RateLimitError` specifically (a 429 — the API refusing the request outright, not the model responding badly) and retries before re-raising. Separate from the empty-content check below it and from callers' content-format retry loops — a rate limit is not fixed by re-sending the same request immediately. Printed on every wait (`  [rate limit] waiting Ns before retry (n/N): <error>`) for the same live-visibility reason as the empty-response/raw-text prints above.
- `judge_text()` rate-limit retry, Retry-After + higher ceiling (2026-09-23, same day, revision): The original version used a fixed 5-attempt exponential backoff (5s/10s/20s/40s, ~75s total) with no knowledge of how long OpenAI actually wanted it to wait — adequate for the one transient spike that prompted the fix, but not a real "wait until the limit clears" guarantee for a more sustained one. `_rate_limit_delay_seconds()` now reads the provider's `Retry-After` response header when present and uses `max(retry_after, RATE_LIMIT_MIN_DELAY_SECONDS)` (`RATE_LIMIT_MIN_DELAY_SECONDS = 10`) — OpenAI can send a `Retry-After` as short as 1-2s, which is too short to actually clear a per-minute token window, so a bare pass-through would just burn another attempt immediately. When no header is present it falls back to exponential backoff from a 10s base, capped at `RATE_LIMIT_MAX_DELAY_SECONDS = 60`: 10s, 20s, 40s, 60s, 60s... `RATE_LIMIT_MAX_ATTEMPTS` raised from 5 to 50 (worst case ~48 minutes of total backoff) so the loop functions as "wait it out" for an ordinary rate-limit episode rather than "guess for ~75s and give up"; the cap remains finite only as a safety net against a rate limit that genuinely never clears (e.g. a misconfigured/exhausted billing quota, not a transient spike).
- Security: Reads the judge credential from an environment variable and never stores it in evaluation records.
- Scope: Preliminary CharacterBox-compatible supervisor-demo mode; planned objective and turn-depth evaluation remain separate.
- Verification: Seventeen deterministic tests (up from seven) cover strict parsing, complete paired-run selection, multi-trial run loading, rejection of a trial missing a declared condition, condition-blind prompts, critique-before-score order, retries (including retrying past a simulated empty score response), output metadata, `judge_text()`'s empty-response diagnostics (finish_reason surfaced, refusal surfaced when present, non-empty content passed through unchanged), and its rate-limit retry (retries past a real `openai.RateLimitError` instance then succeeds, with the expected 10s/20s exponential-fallback delays asserted; honours a real `Retry-After` header while still enforcing the 10s floor on a too-short one; honours a generous `Retry-After` header verbatim; survives more consecutive rate-limit errors than the old 5-attempt cap allowed; raises after exhausting all `RATE_LIMIT_MAX_ATTEMPTS` attempts) — all without provider calls or real waiting (`time.sleep` mocked).

### `evaluate.py`

- Status: Added by this project; CharacterBox has no equivalent per-turn evaluator. This is the primary evaluation entry point — it produces both H1 and H2 results from one command over one pilot's trajectory file.
- H1 (per-turn consistency): Original research code, not adapted from CharacterBox or CharacterCraft. For every turn of every condition record it makes one single-call judge request (no separate critique call) asking for a strict JSON object with a binary PASS/FAIL/NA decision plus quoted evidence for three metrics: Context Use, World Consistency, and No Contradiction. Input is truncated to `turn["round"] <= round_number` so the judge never sees a future turn. `self_belief`/`environment_belief` are deliberately excluded from the rendered character context because controlled trials never populate them (see the "Components currently excluded" row in `docs/characterbox-provenance.md`).
- World Consistency claim-list redesign (2026-09-16): the judge is no longer asked for a top-level `decision` on this metric at all. It must instead enumerate every separate factual claim the response makes, each with its own `consistent: true|false` verdict and (when inconsistent) the specific supplied fact it conflicts with; `world_consistency.decision` is derived in code from that list — NA if the list is empty, FAIL if any claim is inconsistent, PASS otherwise. Replaces the prior single `{"decision", "evidence"}` shape for this metric only (`context_use` and `no_contradiction` are unchanged). See the research rationale below and the 2026-09-16 provenance entry.
- `parse_h1_response()`: `context_use`/`no_contradiction` still require `decision` PASS/FAIL/NA with `evidence` non-null when PASS/FAIL and null when NA; `no_contradiction.contradicted_round` must be an integer when FAIL and null otherwise. `world_consistency` is validated separately by `parse_world_consistency_claims()`: must be an object with exactly one key, `claims` (a list, possibly empty); each entry requires non-empty `claim` text, boolean `consistent`, and `checked_against` (renamed from `conflicts_with`, 2026-09-16) — required (non-empty string, never `null`) on **every** claim as of the second 2026-09-16 revision below, not only inconsistent ones; when `consistent` is false it must name the real fact the claim conflicts with (the literal `NO_SUPPLIED_FACT` sentinel is explicitly rejected here); when `consistent` is true it may be a supporting fact or exactly the module-level `NO_SUPPLIED_FACT` constant (`"No supplied fact addresses this claim."`) when nothing in the supplied data is relevant. Raises `ValueError` on any violation, consumed by `evaluate_h1_turn()`'s retry loop.
- Per-claim `quote` field + verification (2026-09-23): Each claim now also requires a non-empty `quote` — the verbatim response fragment it was drawn from, distinct from `claim` (which may still paraphrase or summarize what's asserted). `parse_h1_response()`/`parse_world_consistency_claims()` take a new `npc_dialogue` parameter (the real per-round response text, pulled by `evaluate_h1_turn()` from `record["turns"]`) and check each claim's `quote` against it via `_quote_is_verbatim()` (substring match, normalized for whitespace and curly-vs-straight quotes via `_normalize_quote_text()`), recording the result as `quote_verified: true|false` on the claim. A missing/empty `quote` is a structural violation (raises `ValueError`, retried like any other malformed response, same as a missing `checked_against`); a `quote` that's present but doesn't actually appear in the response is **not** a structural violation — it's flagged (`quote_verified: false`) in the saved output rather than rejected/retried, since it's a content-quality signal (the judge may be misrepresenting what was said) rather than a format the judge failed to produce. `notebooks/trial_inspector.ipynb`'s `format_world_consistency()` now prints each claim's quote and an `[UNVERIFIED QUOTE]` marker when `quote_verified` is false.
- `compute_consistency()`: Averages only the non-NA metric scores (PASS=1, FAIL=0) for a turn; returns `None` when all three metrics are NA rather than dividing by zero, so an all-NA turn is excluded from later aggregation rather than scored as 0. Unchanged by the claim-list redesign — it only ever reads each metric's already-derived `decision`.
- `evaluate_h1_turn()` round-1 `no_contradiction` override: Forces `no_contradiction` to `NA` (discarding whatever the judge returned) whenever `round_number == 1`, since round 1 structurally has no prior turn to contradict — a fact already known from `round_number` alone, not something requiring judge inference. Added because the judge empirically mislabels this PASS about as often as NA; see the 2026-09-09 provenance entry. `decisions_out["world_consistency"]` now carries `claims` instead of `evidence`; every other metric's output shape is unchanged.
- H2 (per-trial realism): Reuses `evaluate_characterbox.py`'s `evaluate_trajectory()` (including its 2026-10-21 target-only instruction, see that file's entry), imported rather than duplicated, and adds only a `"hypothesis": "H2"` tag to its output. CharacterBox's seven scores are reported as one averaged realism score per the same Table 2 "Average column" convention CharacterBox itself uses, not individually; see the 2026-08-31 provenance entry for why CharacterCraft's reference-dependent metrics (Personality/Emotion/Decision) were not used for H2 instead.
- Output: Two separate JSONL files (`output/evaluation/h1_consistency.jsonl`, `output/evaluation/h2_realism.jsonl` by default), one row per turn for H1 and one row per condition-record for H2, both tagged with `hypothesis`. `--h1-only` / `--h2-only` (2026-10-21, mutually exclusive) run one lane alone, for the judge bake-off; the skipped lane's file is not opened. Also 2026-10-21: (a) every H1 row records `judge_attempts` and `judge_seconds` and every H2 row `judge_seconds` (wall-clock, retries included) for comparing judge speed; (b) a turn or record that fails every retry is logged to `failed_judgements.jsonl` and skipped instead of aborting the run, and a re-run skips keys (`generation_run_id`, trial, condition, round) that the same judge already has in the output file, so interrupted runs resume; (c) `parse_h1_response()` no longer validates the judge's round-1 No Contradiction answer, which `evaluate_h1_turn()` always replaces with NA (a local Qwen2.5-14B judge returned PASS without evidence there four times and aborted the run). None of these changes a recorded decision. (d) `utils.get_llm()` passes an optional `request_timeout` (seconds) from the config to the client; `config/evaluate*.yaml` set 180, because API judge runs hung for the client's 10-minute default on a connection that died during a Wi-Fi change. (e) `_quote_is_verbatim()` compares case-insensitively: in the judge bake-off most `quote_verified: false` flags were correct quotes that a judge had lower-cased (e.g. "we've got each other" for "We've got each other"). The flag is informational and changes no decision; rows written earlier keep their old flag.
- `judge_text()` empty-response diagnostics: `evaluate_h1_turn()` now calls `judge_text()` inside its retry loop's `try:` block (previously outside, so a raised error skipped the retry loop entirely); a deterministic empty completion is now retried like any other malformed response, and the final raised error surfaces the provider's `finish_reason`/`refusal` instead of an opaque `json.loads` failure. See the 2026-09-16 provenance entry.
- Verification: `tests/test_evaluate.py` (39 tests, up from 35) covers no-future-turn-leakage context truncation, excluded belief fields, condition-blind prompts, strict H1 JSON validation (every rejection branch for all three metrics, including every World Consistency claim-list rejection branch — `checked_against` now required on every claim, not only inconsistent ones, and the `NO_SUPPLIED_FACT` sentinel accepted only when consistent, rejected when inconsistent), markdown-fence/preamble JSON recovery, consistency averaging including the all-NA case, retry-then-succeed and retry-exhaustion for `evaluate_h1_turn()`, retrying past a simulated empty judge response and surfacing `finish_reason` when every attempt is empty, the round-1 `no_contradiction` override (forced to NA even when the judge says PASS) and its round ≥2 non-interference (a real FAIL at round 2 survives untouched), World Consistency FAIL correctly derived end-to-end from one inconsistent claim among several, hypothesis tagging for `evaluate_h2_trial()`, and the new `quote` field (required and rejected when missing; verified true when it matches modulo whitespace/curly-quote normalization; verified false and *not* retried — a single judge call — when it doesn't match the real per-round dialogue). No real provider call.

# `config/`

## Folder-level comparison

### Added in this project

- `config/context_priorities.json`
- `config/evaluate_characterbox.yaml`
- `config/evaluate.yaml`
- `config/pilot_run_config.json`

### Intentionally left out from CharacterBox

- None. CharacterBox has no equivalent research-priority configuration.

### Present in both but modified

- `config/play.yaml`

## Files

### `config/play.yaml`

- Status: Adapted from CharacterBox `config/play.yaml` for editable ordinary simulation defaults; fixed pilot data are stored separately.
- Data selection: `scene_path`, `scene_id`, `play_role`, `target_character_id`, `action_id`, `dynamic_play`, `round`, and `context_condition` directly control an ordinary YAML-only run. They are overlaid only when the user explicitly supplies `--pilot`.
- Mode extension: Adds `dynamic_play: False` for controlled interactive play. Simulator treats an omitted field as `True`, preserving original CharacterBox configuration behavior.
- Cost-reporting extension: Adds `calculate_cost: False` to disable CharacterBox's legacy GPT-2-based token/cost estimate and its tokenizer-length warnings. Dialogue generation and saved interaction/model-call records remain enabled.
- Controlled selectors: Adds source `target_character_id` and `action_id`, a dataset-source label, nullable ordinary-run trial ID, and the reusable `priority_config_path`. `research_sidecar_path` is intentionally absent so YAML cannot silently activate fixed pilot input.
- Pilot run-config selector: Adds `pilot_config_path`, auto-loaded whenever `--pilot` selects a manifest. It supplies `conditions` and `priority_policy_id` so pilot manifests no longer embed run-behavior fields; no separate CLI flag is required.
- Reproducibility extension: Adds `seed: null`, forwarded by `utils.get_llm()` to `ChatOpenAI` as OpenAI's best-effort (not guaranteed) reproducible-sampling control. `null`/omitted preserves normal stochastic generation; survives `config.clone()` in `run_pilot_conditions()` unchanged, since yacs `clone()` deep-copies the whole node rather than reconstructing a fixed key whitelist. See the 2026-09-09 provenance entry.
- Credential handling: Credential fields are blank placeholders. Simulator startup reads `OPENAI_API_KEY`, or the role-specific `CHARACTER_API_KEY` and `NARRATOR_API_KEY`, and logging replaces all credential values with `[REDACTED]`.
- Preserved settings: Model names, retry count, token limit, temperature, verbosity, API base URLs, record toggle, record directory, and record filenames remain unchanged.
- Provider change (2026-10-14): `narrator_llm`/`character_llm` changed from `gpt-4o-mini` to `openai/gpt-4o-mini`, and both API base URLs from `https://api.openai.com/v1` to `https://openrouter.ai/api/v1`, because the project is now funded through OpenRouter. The model, temperature, token limit, seed, and prompts are unchanged; OpenRouter forwards the request to OpenAI. `OPENAI_API_KEY` (or the role-specific variables) now holds the OpenRouter key. Pilots 1-5 used the direct OpenAI endpoint. This supersedes the model-name and API-base part of "Preserved settings" above.
- Runtime consequence: `python simulator.py -c config/play.yaml` runs one editable interactive configuration. Adding `--pilot <manifest>` deliberately overlays fixed experiment selectors and auto-loads `pilot_config_path`, then runs every trial in the manifest under every declared condition.
- Verification: Explicit-manifest, omitted-manifest, YAML-only controlled-load, and trial/condition-loop tests use key-free internal configuration and never read this live file.

### `config/pilot_run_config.json`

- Status: Added by this project; CharacterBox has no counterpart.
- Purpose: Reusable pilot run-config, schema v1, separated from pilot manifests so `conditions` and `priority_policy_id` are not duplicated per pilot file. Contains no scene, character, or dialogue value.
- Runtime consequence: Auto-loaded by `Simulator.load_simulator()` and `run_pilot_conditions()` whenever a pilot's `research_sidecar_path`/`pilot_config_path` is set; supplies the condition list `run_pilot_conditions()` loops over and the priority policy ID used for P.
- Verification: `dataloader/research_sidecar.py:validate_pilot_config()` and `tests/test_research_sidecar.py`.

### `config/context_priorities.json`

- Status: Added by this project; CharacterBox has no counterpart.
- Schema: Contains a version and a list of reusable policies. Each policy contains ordered positive-integer priority groups with a name, instruction, and non-empty field list, plus an optional policy-level `conflict_rule` string that replaces the P prompt's default conflict-resolution sentence.
- Current policy: `primary_four_level` assigns all 13 CharacterBox English dialogue-context fields exactly once. Priority 1 (`current_world_constraints`) contains time, location, and position. Priority 2 (`world_background`) contains event, observation, and description. Priority 3 (`character_guidance`) contains name, character description, self belief, the plot-derived Action Reference, current state, and environment belief. Priority 4 (`conditional_memory`) contains recent memory. This is the code-accurate grouping of the original policy, retained unchanged so earlier P runs remain reproducible; see the 2026-08-30 "Priority tier revision" entry in `docs/characterbox-provenance.md` for its earlier grouping and rationale.
- Active policy (from 2026-09-29): `primary_five_level`, selected by `config/play.yaml` and `config/pilot_run_config.json`. Priority 1 (`current_world_constraints`): time, location, position. Priority 2 (`world_background`): event, description. Priority 3 (`character_guidance`): name, character description, Action Reference, current state. Priority 4 (`beliefs_and_memory`): self belief, environment belief, recent memory. Priority 5 (`conversation_input`): observation, with an instruction that other characters' statements are claims, not verified facts. It also supplies a `conflict_rule` and a reworded Priority 1 instruction. See the 2026-09-29 entry in `docs/characterbox-provenance.md`.
- Data boundary: Contains field names and research instructions only; it contains no scene, character, action, dialogue, or other CharacterBox world value.
- Ablation boundary: Two policies are present: the superseded `primary_four_level` (kept for reproducibility of earlier pilot runs) and the active `primary_five_level`. Neither is an ablation. Later policies may use more levels or one field per level without changing the schema, but require separate approval before addition.
- Runtime consequence: `Character` reads the caller-supplied validated policy only for the P condition; the paired pilot supplies its policy ID while the YAML retains the policy-file path.
- Verification: `tests/test_context_priorities.py` and the read-only module inspection command.

### `config/evaluate_characterbox.yaml`

- Status: Added by this project; CharacterBox's `config/evaluate.yaml` is not copied.
- Purpose: Declares preliminary judge model, deterministic temperature, output limit, provider retries, score-format retries, API base, and environment-variable name.
- Provider change (2026-10-14): `judger_llm` `gpt-4o-mini` -> `openai/gpt-4o-mini` and `api_base` -> `https://openrouter.ai/api/v1` (same model via OpenRouter). Not used for any reported result.
- Security boundary: Contains no credential; `OPENAI_API_KEY` is read only at runtime.

### `config/evaluate.yaml`

- Status: Added by this project; CharacterBox's `config/evaluate.yaml` is not copied.
- Purpose: Shared judge configuration for `evaluate.py`'s H1 and H2 lanes; identical fields and current values to `config/evaluate_characterbox.yaml` (judge model, deterministic temperature, output limit, provider retries, score/decision-format retries, API base, environment-variable name). Kept as a separate file so `evaluate_characterbox.py`'s preliminary supervisor-demo config is not coupled to the primary evaluator's config.
- Provider change (2026-10-14): `judger_llm` `gpt-4o` -> `openai/gpt-4o` and `api_base` -> `https://openrouter.ai/api/v1`. Same judge model, temperature 0, seed 1 and prompts; OpenRouter forwards to OpenAI. Saved H1/H2 rows record `judge_model` as `openai/gpt-4o` from this date. Pilot 1-5 scores were produced with `gpt-4o` via api.openai.com.
- Security boundary: Contains no credential; `OPENAI_API_KEY` is read only at runtime.

# `agents/`

## Folder-level comparison

### Added in this project

- None. All three current files have CharacterBox counterparts.

### Intentionally left out from CharacterBox

- None. The adapted Narrator remains inactive in the controlled primary pipeline because narrator-generated outcomes and state updates could give U/S/P different semantic inputs.

### Present in both but modified

- `agents/__init__.py`
- `agents/character.py`
- `agents/human_player.py`
- `agents/narrator.py`

### Present in both without modification

- None.

## Files

### `agents/__init__.py`

- Status: Adapted from CharacterBox.
- CharacterBox exports: `HumanPlayer`, `Narrator`, and `Character`.
- Current exports: `HumanPlayer`, `Narrator`, and `Character`, matching CharacterBox.
- Exact changes: Double-quoted strings, blank-line formatting, and import placement differ; exported symbols and their `__all__` order match CharacterBox.
- Behavioral consequence: Importing `agents` again exposes all three original agent classes, allowing the exact copied `simulator.py` import to resolve. This does not instantiate or call Narrator.
- Verification: Character and HumanPlayer tests import their classes successfully; direct `agents` and `simulator` import checks succeed.

### `agents/narrator.py`

- Status: English-only adaptation of CharacterBox `agents/narrator.py`.
- File header/imports: Adds CharacterBox commit/licence provenance and removes `from utils import utils` because Narrator no longer calls `detect_language()`.
- Preserved symbols and English behavior: The complete `Narrator` class, declared fields, `update_from_dict()`, model-call paths, English prompt text, action tracing, return shapes, action adjudication, character updates, scene updates, and plot summaries remain present.
- `_generate_reaction()`: Removes scene-event language detection and the Chinese common prompt; always uses the original English common prompt.
- `update_character()`: Removes the Chinese instruction and `Position`/`State` parser fallback; retains the original English instruction and English response patterns.
- `analyze_action()`, `analyze_action_influence()`, and `analyze_result()`: Remove Chinese instruction branches and retain the corresponding original English instructions and downstream parsing.
- `update_scene()`: Removes the Chinese prompt and Chinese structured-output patterns; retains the original English scene prompt, English `Time`/`Location`/`Description` parsing, scene mutation, and action tracing.
- `summary_plot()`: Removes the Chinese prompt and retains the original English plot-summary prompt and downstream behavior.
- Research marking: Every changed prompt or parser region is enclosed by `BEGIN/END RESEARCH MODIFICATION` comments.
- Controlled-mode boundary: The file is retained for the later dynamic CharacterBox mode but must not be called during controlled U/S/P pilot trials.
- Verification: Four deterministic tests cover the exact English common prompt, English character parsing, English scene prompt/parsing, and absence of Chinese text/language branches; full fifty-six-test suite passes without provider calls.

### `agents/human_player.py`

- Status: Adapted from CharacterBox `agents/human_player.py`.
- File header/imports: Adds postponed annotations, CharacterBox commit/licence provenance, and `Tuple` typing.
- Preserved symbols: `HumanPlayer`, all original declared fields/defaults/constants, `update_from_dict()`, `reset_agent()`, and `_generate_reaction()` remain present. The inherited LLM-oriented helper is not called by the terminal methods.
- Added field: `gender`, preserving the value already supplied by `Simulator.create_human_player()` as role metadata. It is not rendered into HumanPlayer or Character U/S/P prompts.
- Added field: `all_actions`, always empty for HumanPlayer because terminal input is not a model call; this lets CharacterBox's dynamic save loop inspect all agents uniformly.
- `generate_dialogue()`: Adds the `observation`, `plot`, and `now` parameters already supplied by `Simulator.one_step()`; translates the terminal label to English; returns `(response, {"text": response, "source": "human"})` instead of text alone.
- `take_action()`: Adds the same simulator-supplied parameters; translates the terminal label to English; returns the same text/detail shape.
- `take_reaction()`: Adds the terminal reaction interface required when dynamic Narrator influence selects the human as reacting character; accepts observation/plot/time and returns the same human-source text/detail shape.
- Research boundary: No terminal method calls an LLM, changes human text, renders U/S/P, or saves memory.
- Research marking: The terminal interface methods and added metadata fields are enclosed by `BEGIN/END RESEARCH MODIFICATION` or `EXTENSION` comments.
- Verification: Four deterministic tests in `tests/test_human_player.py`, including three input-patched interface tests; full fifty-six-test suite passes.

### `agents/character.py`

- Status: English-only adaptation of CharacterBox `agents/character.py`.
- File header: Added CharacterBox source, commit, copyright, MIT licence, and provenance reference.
- Imports: Removed `from utils import utils` because `detect_language()` is no longer called. Other inherited imports remain, including currently unused inherited imports.
- Class and fields: `Character`, its declared fields, defaults, and constants remain present. No CharacterBox method has been removed.
- Parameters and return shapes: Existing return behavior remains unchanged. `_generate_reaction()` and `generate_dialogue()` add optional research parameters described below; their defaults preserve the retained English S path for existing callers.
- Added `NoScoreGenerativeAgentMemory(GenerativeAgentMemory)`: overrides `_score_memory_importance()` to return `0.0` without a model call. No CharacterBox counterpart; used only by `simulator.py:create_character()` for controlled trials (`score_memories=False`). Dynamic play continues to instantiate the unmodified `GenerativeAgentMemory`. See `docs/characterbox-provenance.md` (2026-08-30 entry) for the verified rationale.

#### `update_from_dict()`

- Difference: No behavioral change.

#### `_generate_reaction()`

- CharacterBox baseline: Selects a Chinese or English common prompt using `utils.detect_language(self.name)`.
- Current implementation: Delegates prompt construction to `_build_reaction_prompt()` and defaults to the exact original English S prompt.
- Added parameters: `context_condition="S"` and `priority_policy=None`, passed only by the controlled dialogue condition path. Existing inherited callers omit both.
- Removed code: Chinese prompt, language detection, and Chinese-answer instruction.
- Preserved behavior: English prompt wording and field order; prompt token counting; memory token-budget key; chain invocation; prompt reconstruction; response/duration recording; verbose return behavior.
- Research marking: The new parameters and delegated prompt construction are enclosed by `BEGIN/END RESEARCH MODIFICATION` comments.
- Verification: `tests/test_characterbox_character.py` asserts the complete formatted English S prompt and shared U/P invocation behavior.

#### `_build_reaction_prompt()`

- Status: Added by this project; CharacterBox has no counterpart.
- Parameters: `suffix`, optional `context_condition="S"`, and optional `priority_policy=None`.
- Shared opening (changed 2026-10-14): A module-level constant `CONTEXT_OPENING`, enclosed by `BEGIN/END RESEARCH MODIFICATION` comments, holds CharacterBox's S opening character-for-character (role instruction plus "The context and {name}'s information is as follows:", including its original double space and leading space). All three branches now begin with it, so the role instruction and the context-introducing sentence are identical across U, S and P.
- S branch: Contains the CharacterBox English common prompt character-for-character (its opening now read from `CONTEXT_OPENING`, unchanged text) and appends the unchanged caller suffix.
- U branch: Begins with `CONTEXT_OPENING`, then uses the same placeholders in a flat value block without CharacterBox field/category headings or priority instructions, then appends the unchanged dialogue instruction. Before 2026-10-14 it opened with its own wording ("...would use. Use the following context to produce one appropriate line of dialogue."), which added an instruction S and P lacked.
- P branch: Begins with `CONTEXT_OPENING` followed by the global conflict rule (before 2026-10-14 it had the role instruction only, with no context-introducing sentence). Maps the same placeholders to the 13 canonical field names, groups and orders them using the supplied validated policy, includes each level's name and instruction, and rejects missing, duplicated, or unknown field assignments. Its global rule tells the model to use all relevant compatible context and to follow the lower priority number only when context conflicts; a policy's optional `conflict_rule` replaces this sentence (used by `primary_five_level`, whose wording names Priority 1 as most important and says to follow the smaller priority number).
- Scope restriction: U/P require the CharacterBox dialogue suffix beginning with its Action Reference line. Belief, action, reaction, state, and synopsis methods continue through default S and cannot silently enter U/P.
- Errors: Rejects unknown condition names, missing P policy data, and incomplete/invalid P field coverage before a model chain is invoked.
- Research marking: The complete helper is enclosed by `BEGIN/END RESEARCH EXTENSION` comments.
- Behavioral consequence: Context presentation can vary while the downstream CharacterBox token, chain, output, and memory behavior stays shared.
- Verification: Five deterministic tests in `tests/test_characterbox_character.py`, including `test_all_conditions_share_the_characterbox_opening` (added 2026-10-14); no external calls.
- Reproducibility note (2026-10-14): U and P prompts generated before this date (pilots 1-5) used the earlier openings and cannot be reproduced exactly from current code; they are development data, not final-study evidence.

#### `generate_dialogue()`

- CharacterBox baseline: Selects Chinese or English dialogue instructions and removes prefixes using both ASCII and full-width colons.
- Current implementation: Retains only the original English instruction, passes the selected prompt condition/policy into the shared reaction path, and delegates output cleanup to `_clean_dialogue_response()`.
- Added optional parameters: `context_condition="S"`, `priority_policy=None`, and `remember=True`. The default call remains compatible with CharacterBox S; `remember=False` (used only by the controlled loop) skips the memory save so the caller can store the player's line first.
- Metadata change: Replaced the unrelated Recommender/Social Media docstring with an accurate dialogue-generation description.
- Removed code: Chinese instruction, language detection, and full-width-colon cleanup.
- Modified response processing: Calls the added `_clean_dialogue_response()`. It joins explicitly quoted speech across multiline outputs and omits surrounding stage directions, pairing any opening quote mark (straight or curly) with any closing one (added 2026-09-29); for unquoted output it selects the first non-stage-direction content line and removes only a leading character-name prefix. It then saves the cleaned spoken response to memory with explicit `Name: dialogue` spacing.
- Preserved behavior: Calls `_generate_reaction()`, saves one processed response through the same memory interface, and returns response/detail. The raw provider text remains available in `detail` and `all_actions`.
- Research marking: The modified signature and call are enclosed by `BEGIN/END RESEARCH EXTENSION` comments.
- Verification: `tests/test_characterbox_character.py` and `tests/test_characterbox_scene_flow.py`.

#### `_clean_dialogue_response()`

- Status: Added by this project; CharacterBox has no counterpart.
- Reason: CharacterBox's first-line/last-colon cleanup reduced a real multiline response beginning with an italic stage direction to `*`, causing the next round's memory to contain `Neville Longbottom:*` rather than Neville's speech.
- Scope: Used only after dialogue generation and shared unchanged by U, S, P, and dynamic calls. It performs no model call and does not alter raw trace data.
- Verification: A deterministic multiline smart/ASCII-quoted response test proves that both spoken segments are retained, stage directions are omitted, and cleaned dialogue is saved to memory.

#### `take_action()`

- CharacterBox baseline: Selects Chinese or English physical-action instructions and removes prefixes using both colon forms.
- Current implementation: Retains only the original English instruction and ASCII-colon processing.
- Metadata change: Replaced the unrelated Recommender/Social Media docstring with an accurate physical-action description.
- Removed code: Chinese instruction, language detection, and full-width-colon cleanup.
- Preserved behavior: English prompt, first-line processing, memory save, and response/detail return.
- Verification: `tests/test_characterbox_scene_flow.py`.

#### `take_reaction()`

- CharacterBox baseline: Selects Chinese or English reaction instructions. Its English path assigns ASCII-colon processing to an unused `rresponse` variable and returns the first-line response.
- Current implementation: Retains the English reaction instruction and returns the first-line response.
- Metadata change: Replaced the unrelated Recommender/Social Media docstring with an accurate physical-reaction description.
- Removed code: Chinese instruction, language detection, Chinese prefix cleanup, and the unused `rresponse` assignment.
- English behavioral consequence: None intended; the upstream unused assignment did not affect the returned English response.

#### `update_self_belief()`

- Difference: Removed language detection and the Chinese prompt; retained the English prompt, `_generate_reaction()` call, field assignment, and return value.

#### `update_env_belief()`

- Difference: Removed language detection and the Chinese prompt; retained the English prompt, `other_characters` input, field assignment, and return value.
- Verification: `tests/test_characterbox_scene_flow.py` exercises the English path.

#### `update_character()`

- CharacterBox baseline: Selects Chinese or English prompts and selects Chinese or English position/state regular expressions.
- Current implementation: Retains only the English prompt and `Position:`/`State:` parsers.
- Preserved behavior: Updates `position` and `states` only when their parsed values exist and returns the parsed pair.

#### `generate_synopsis()`

- CharacterBox baseline: Selects Chinese or English prompts and accepts either a Chinese or ASCII colon in its result parser.
- Current implementation: Retains only the original English prompt and accepts the ASCII colon used by the English output format.
- Preserved behavior: Chain invocation, first-block response processing, per-character dictionary construction, and return shape.
- Verification: `tests/test_characterbox_scene_flow.py` checks its inputs and resulting action reference.

#### Overall verification

- The protected S prompt is tested character-for-character.
- The real-scene compatibility test exercises self-belief, environment-belief, synopsis, physical action, and dialogue in CharacterBox's character-side order.
- No real provider, Narrator, or FAISS store is invoked by the tests. HumanPlayer tests patch terminal input and make no LLM call.

# `dataloader/`

## Folder-level comparison

### Added in this project

- `dataloader/context_priorities.py`
- `dataloader/research_sidecar.py`

### Intentionally left out from CharacterBox

- None.

### Present in both but modified

- `dataloader/__init__.py`: documentation-only change.
- `dataloader/data.py`: formatting-only change.

## Files

### `dataloader/__init__.py`

- Status: CharacterBox counterpart retained with a project docstring.
- Difference: Added `"CharacterBox-compatible dataset loading utilities."`.
- Runtime consequence: None.

### `dataloader/data.py`

- Status: Copied from CharacterBox with formatting only.
- Imports: Same imports; spacing changed.
- Class fields: Same constructor attributes and defaults, including inherited unused attributes and the `netwerk_density` spelling.
- `Data.__init__()` parameters: Unchanged `config` and `logger` parameters.
- `Data.load_scene()`: Same JSON loading, list-index scene selection, scene dictionary storage, `SceneInfo` conversion, `CharacterInfo` construction, name/ID mappings, plain-dictionary actions, and prompt-facing character string construction.
- Nonfunctional changes: Whitespace, quote style, import spacing, and multiline formatting.
- Verification: `tests/test_characterbox_data.py` and `tests/test_characterbox_scene_flow.py`.

### `dataloader/research_sidecar.py`

- Status: Added by this project; CharacterBox has no counterpart.
- Imports: Uses only Python standard-library argument parsing, JSON, and path handling.
- Constants: Defines allowed dataset-source labels and exact schema-v4 pilot-manifest, trial, turn, and schema-v1 pilot-run-config fields. Priority-policy definitions remain separate in `context_priorities.json`.
- `SidecarValidationError`: Adds a validation exception, derived from `ValueError`, shared by pilot-manifest and pilot-run-config validation.
- `_matches_by_id()`: Selects decoded scene records by their logical ID fields rather than assuming an array position equals an ID.
- `validate_sidecar()`: Validates one schema-v4 pilot manifest: scene/player/target identity and one pilot-level Action Reference shared by every trial, plus a non-empty list of independent trials, each with a unique `trial_id` and sequential non-empty dialogue-only turns. `evaluation_cases` and `recent_memory_action_ids` are rejected as unsupported fields (dropped; see the 2026-08-30 provenance entry). Interaction-level `player_action` fields are rejected. An optional per-trial `note` field (free-text string, non-empty when present) is accepted; see the 2026-09-01 provenance entry for its research-documentation purpose.
- `validate_pilot_config()`: Added. Validates one schema-v1 reusable pilot run-config: a non-empty, unique `conditions` list drawn from U/S/P, and a required `priority_policy_id` when P is included.
- `load_validated_pilot_config()`: Added. Loads and validates a pilot run-config JSON file.
- `_load_sidecar_and_dataset()`: Loads the sidecar and its relative source dataset for shared programmatic and inspection paths.
- `load_validated_sidecar()`: Loads the pilot manifest and its relative source dataset before validation.
- `resolve_source_dataset_path()`: Resolves the validated relative dataset path for simulator override without copying source values into the manifest.
- `main()`: Prints resolved roles, pilot-level Action Reference, every trial's scripted dialogue turns and (when present) its `note`, and, when `--pilot-config` is supplied, the run-config's conditions and priority policy.
- Behavioral consequence: The same validated files are both inspectable research metadata and the authoritative non-secret simulator experiment layer. Pilot identity/trial content and run behavior (conditions/policy) are now validated as two separate, reusable artifacts instead of one manifest.
- Verification: `tests/test_research_sidecar.py`.

### `dataloader/context_priorities.py`

- Status: Added by this project; CharacterBox has no counterpart.
- Constant: `CHARACTERBOX_CONTEXT_FIELDS` enumerates the 13 canonical English dialogue-context fields from the protected CharacterBox S prompt.
- `PriorityConfigValidationError`: Adds a priority-policy-specific validation exception derived from `ValueError`.
- `_require()`: Provides local readable validation assertions.
- `validate_priority_config()`: Validates schema version, unique policy IDs, positive continuous priority numbers, names, instructions, an optional non-empty `conflict_rule` string, non-empty string field lists, exact one-time coverage of all 13 fields, and absence of unknown fields.
- `load_validated_priority_config()`: Loads a JSON priority configuration before validation.
- `main()`: Adds a read-only command-line inspection view showing every policy, level, field group, and instruction.
- Behavioral consequence: A reusable field-group priority policy can be audited independently of trial data; no prompt or model call is produced.
- Verification: Six tests in `tests/test_context_priorities.py`; full fifty-six-test suite passes.

# `utils/`

## Folder-level comparison

### Added in this project

- `utils/__init__.py`: the inspected CharacterBox commit has no tracked counterpart.

### Intentionally left out from CharacterBox

- None recorded. Other CharacterBox utility files that are merely not yet needed are not classified as excluded.

### Present in both but modified

- `utils/character.py`: formatting-only change.
- `utils/utils.py`: `get_llm()` gained an optional best-effort reproducible `seed`.

### Present in both without modification

- `utils/message.py`

## Files

### `utils/__init__.py`

- Status: Added by this project.
- Purpose: Marks the utility package and documents that it currently contains CharacterBox-compatible data models.
- Runtime consequence: No model behavior change.

### `utils/character.py`

- Status: Adapted from CharacterBox with one marked data-preservation extension plus formatting changes.
- `CharacterInfo`: Adds required `gender: str` because every character record in the retained dataset supplies it and the original Simulator later reads it. Original fields `id`, `name`, `position`, `states`, and `description` remain unchanged.
- Prompt boundary: `CharacterInfo.__str__()` retains its exact original field order and labels and does not render gender, so `init_characters` and the 13-field U/S/P context remain unchanged.
- `SceneInfo`: Fields `id`, `event`, `time`, `location`, `description`, and optional `plot` are unchanged. Its string output still omits `id` and `plot`, matching CharacterBox.
- Nonfunctional changes: Blank lines, spacing around the `plot` default, and final newline.
- Verification: `tests/test_characterbox_data.py`, `tests/test_human_player.py`, full dataset gender scan, and full suite.

### `utils/message.py`

- Status: Copied exactly from CharacterBox `utils/message.py`; no research modification is present.
- Purpose: Provides the Pydantic `Message` record imported by `simulator.py`.
- Verification: Byte-for-byte `cmp` with the inspected CharacterBox source succeeds.

### `utils/utils.py`

- Status: Adapted from CharacterBox `utils/utils.py`; marked research extensions to `get_llm()` and the added `path_safe_model_name()`, otherwise unmodified.
- Purpose: Provides configuration, logging, JSON, directory, model-selection, cost, and language-detection helpers used by the original Narrator and Simulator.
- `get_llm()`: Uses `LocalLLM` only when `api_base` is a non-HTTP, non-placeholder path; otherwise it constructs `ChatOpenAI`. It does not select a test double. Now reads an optional `seed` from `config` (via `config.get("seed")`, safe when absent) and forwards it to `ChatOpenAI` as `model_kwargs={"seed": seed}` when set, otherwise `model_kwargs={}` (unchanged behavior). `LocalLLM` construction is unaffected — no seed support added there. See the 2026-09-09 provenance entry.
- `path_safe_model_name()` (added 2026-10-14, marked research extension): Replaces `/` and `\` in a model id with `-` so it can sit inside one record filename (used by `Simulator.save_record()`). Verified by `tests/test_path_safe_model_name.py` (two tests).
- Current dependency consequence: Its wildcard import of `llm` eagerly imports `LocalLLM`, which requires `transformers` even when the normal `ChatOpenAI` branch would be used.
- Verification: `tests/test_llm_seed.py` (no seed leaves `model_kwargs` empty; a set seed is forwarded; an explicit `null` seed leaves `model_kwargs` empty) — `ChatOpenAI` is mocked, no real API call. Byte-for-byte `cmp` with the inspected CharacterBox source no longer succeeds outside the marked extension block; import inspection currently stops at missing `transformers`.

# `llm/`

## Folder-level comparison

### Added in this project

- None.

### Intentionally left out from CharacterBox

- None.

### Present in both but modified

- None.

### Present in both without modification

- `llm/__init__.py`
- `llm/custom_llm.py`
- `llm/local_llm.py`

## Files

### `llm/__init__.py`

- Status: Copied exactly from CharacterBox.
- Purpose: Eagerly exports both runtime adapters, `CustomLLM` and `LocalLLM`.
- Current dependency consequence: Standard unittest discovery imports this package and fails if optional `transformers` is unavailable.

### `llm/custom_llm.py`

- Status: Copied exactly from CharacterBox.
- Purpose: Runtime adapter that sends chat-completion HTTP requests to a configured local server; it is not a deterministic test model and is not selected by the copied `get_llm()` implementation.

### `llm/local_llm.py`

- Status: Copied exactly from CharacterBox.
- Purpose: Runtime adapter that loads a Hugging Face causal model and moves it to CUDA; it is not test infrastructure.
- Current execution status: Import requires `transformers`; actual construction additionally assumes a compatible local model and CUDA environment.
- Verification: `diff -qr` against the inspected CharacterBox `llm/` directory reports no source difference. Copied `__pycache__` files are generated artifacts and are ignored by this record.

# `data/`

## Folder-level comparison

### Added in this project

- `data/generated_data/README.md`
- `data/research_annotations/characterbox_pilot.json`
- `data/research_annotations/characterbox_pilot2.json`

### Intentionally left out from CharacterBox

- Source-book `chunk` content is intentionally excluded from the copied Harry Potter record. This is a field-level data removal rather than an omitted file.
- No other currently absent CharacterBox dataset is classified here as permanently excluded.

### Present in both but modified

- `data/generated_data/Harry_Potter.json`

## Files

### `data/generated_data/README.md`

- Status: Added by this project.
- Purpose: Records the source commit, sanitisation, allowed local use, dual-source study role, and licensing/redistribution warning for the copied data.
- Runtime consequence: None.

### `data/generated_data/Harry_Potter.json`

- Status: Copied and sanitised from the CharacterBox file at the inspected commit.
- Preserved structure: Root title, 50-scene list, scene and character IDs, event, time, location, description, characters, gender inputs, positions, states, actions, dialogue, and plot.
- Removed data: Every scene-level `chunk` object and its source-book passage.
- Runtime consequence: None for the copied `Data` loader and `Character` path; neither consumes `chunk`.
- Research consequence: Selected records must be manually checked and are evaluated against their supplied scene content rather than external franchise canon.
- Verification: `test_sanitised_development_file_has_50_scenes_and_no_chunks` plus loader and real-scene flow tests.

### `data/research_annotations/characterbox_pilot.json`

- Status: Added by this project; CharacterBox has no research-sidecar counterpart.
- Dataset relationship: Points to the sanitised CharacterBox `Harry_Potter.json` by a relative path and selects the two-character scene ID 19, Luna Lovegood as player, Neville Longbottom as target, and Neville's action ID 1 as the pilot-level Action Reference.
- Schema/runtime metadata: Schema v4. Scene/player/target identity and Action Reference are pilot-level, shared by every trial; a `trials` array holds one or more independent dialogue-only trials, each with a `trial_id`, an optional `note`, an optional `type` (1 normal, 2 stress, 3 multi-turn; added 2026-09-29), and an ordered multi-turn-capable `turns` array. Each turn permits only `round` and non-empty `player_dialogue`. Conditions and priority-policy ID moved to the separate `config/pilot_run_config.json`; `recent_memory_action_ids` and `evaluation_cases` were dropped (unused/never wired to a live memory store).
- Trial content (11 trials as of 2026-09-23, ordered by category, renumbered `t01`–`t11` contiguously): normal fact-check (`t01`–`t04`, each targeting a different field — action_reference, position, time/location, description), stress fact-check (`t05`–`t07`, false-premise lines targeting description, location/description, and action_reference/location — `t05` added 2026-09-23, isolating the moon-brightness premise previously only embedded in the multi-turn trial), out-of-bound-knowledge fact-check (`t08`, added 2026-09-23, isolating the Hermione/fabricated-third-character premise the same way), open-ended (`t09`–`t10`, no targeted field, for H2's personality/immersion dimensions), and one 10-round multi-turn trial (`t11`, previously `t10`) for the H3 decline-rate/no-contradiction exploratory extension — its 10 lines were designed interactively against real S-condition model output rather than pre-written, and its `note` records both the per-round design intent and two live findings from that design run (a false-premise slip at rounds 5 and 8). Each trial's `note` records its category and, for fact-check trials, the targeted field(s), matching this grouping.
- Data boundary: Does not copy or modify CharacterBox scene, character, action, dialogue, or plot values. The validator resolves them directly from the source dataset for inspection. `note` is researcher-authored trial-design documentation, not a copied CharacterBox or dataset value.
- Behavioral consequence: It has no effect on ordinary simulator execution. When explicitly passed through `--pilot`, it overlays experiment selectors, auto-loads the pilot run-config, and runs every trial under every declared condition with a fresh Simulator instance; it contains no provider credentials and performs no call by itself. `note` is not read by `simulator.py` or `evaluate.py`; it exists only for human inspection via `dataloader/research_sidecar.py`'s CLI.
- Verification: Inspection plus validator, override, scripted-turn, fresh-condition, and record-metadata tests.

### `data/research_annotations/characterbox_pilot2.json`

- Status: Added by this project by adapting the schema-v4 pilot manifest; CharacterBox has no research-sidecar counterpart.
- Dataset relationship: Selects CharacterBox scene ID 12, Newt Scamander as the scripted player, Professor McGonagall as the target NPC, and McGonagall's action ID 1 as the pilot-level Action Reference.
- Controlled interaction (rebuilt 2026-09-23, replacing the original two-turn placeholder): 13 trials following `docs/trial-design-guide.md`'s taxonomy — normal fact-check (`t01`–`t04`, targeting position/states/time-location/description), direct-contradiction stress fact-check (`t05`–`t06`, targeting the scene's stated onlookers and time), four out-of-bound-knowledge fabrication trials (`t07`–`t10`, deliberately covering four different flavors: a named individual among the scene's unnamed implied onlookers, a fabricated detail filling in the scene's own vague "compromising situation" wording, a fabricated prior incident, and a fabricated shared teacher/student history), two open-ended trials (`t11`–`t12`), and one 10-round multi-turn trial (`t13`) designed live against real simulator output round by round, not written blind, per the design guide's rule. `t13`'s live design run produced three genuine, unplanned findings (not engineered, discovered mid-design): the target spontaneously fabricated an unestablished detail ("a Niffler... during breakfast") unprompted at round 1; a fabricated-prior-incident probe was resisted identically by deflection at both shallow (round 5) and deep (round 8) conversational depth, showing no depth-dependent degradation in this run; and round 6 produced a genuine contradiction, calling Newt "a Hogwarts student" against the supplied "former Hogwarts student" description. See `docs/limitations.md`. Conditions and `primary_four_level` priority policy come from the shared `config/pilot_run_config.json`.
- Research rationale: User-directed expansion specifically to explore the fabrication/out-of-bound-knowledge gap identified in `docs/limitations.md` ("World Consistency catches contradiction, not fabrication") on a second scene, with more dedicated fabrication trials (4) than the first pilot's single example, and deliberately varied in kind rather than repeating the same pattern.
- Verification: `python -m dataloader.research_sidecar data/research_annotations/characterbox_pilot2.json --pilot-config config/pilot_run_config.json` validates the manifest and resolves every selector, including all 13 trials (and all 10 of `t13`'s rounds) against the real scene 12 data. Full suite: 121 tests, all passing (no test references `characterbox_pilot2.json`, so none needed updating).

### `data/research_annotations/characterbox_pilot3.json`

- Status: Added by this project by adapting the schema-v4 pilot manifest; CharacterBox has no research-sidecar counterpart.
- Dataset relationship: Selects CharacterBox scene ID 31 ("Harry Potter's Statement at the Magical Tribunal"), the third distinct scene used across the three pilots (pilot1: scene 19; pilot2: scene 12) — a courtroom/testimony setting, deliberately different in register from pilot1's secretive-peers scene and pilot2's disciplinary-scolding scene. Albus Dumbledore is the scripted player, Harry Potter is the target NPC (chosen over Dumbledore specifically because Harry's action reference — "describing to the tribunal his encounter with two Dementors and how he protected himself and his cousin" — carries far richer, more specific checkable facts than Dumbledore's more generic defending-Harry action), and Harry's action ID 0 is the pilot-level Action Reference.
- Controlled interaction (complete as of 2026-09-23, `t11` redesigned same day): 11 trials following `docs/trial-design-guide.md`'s taxonomy — normal fact-check (`t01`–`t04`, targeting position, demeanor/states, time-location, and the action reference's Dementor-count/cousin details), direct-contradiction stress fact-check (`t05`–`t06`, targeting the Dementor count and the location), two out-of-bound-knowledge fabrication trials (`t07`–`t08`) — deliberately fewer than pilot2's four, per user direction to de-emphasize this category going forward — and two open-ended trials (`t09`–`t10`). `t07` is the same named-unestablished-onlooker flavor pilot2 used; `t08` is a new flavor not used in either prior pilot — a wildly nonsensical fabrication with no connection to the Harry Potter setting at all (a fictitious "Devil Fruit" pre-tribunal ritual), testing grounding against an absurd premise rather than a plausible-sounding one, again per user direction. `t11` is the pilot's 10-round multi-turn trial, designed live against real S-condition simulator output round by round (not written blind), per the design guide's rule — see the research rationale below for its live findings.
- Research rationale: User-directed third pilot, this time with scene selection delegated to the assistant (previous two pilots' scenes were user-directed). Selected for factual richness (to stress World Consistency) and thematic diversity from the first two pilots' registers. The reduced fabrication-trial count and the addition of a non-Harry-Potter-universe fabrication flavor were both explicit user direction following review of pilot2's live results (see `docs/limitations.md`'s pilot2 fresh-findings section for what prompted the review). Mid-design, the user corrected the assistant's category discipline: a "stress fact check (direct contradiction)" trial must contradict an explicit or clearly implied supplied fact, not merely introduce content absent from the supplied data (that belongs under out-of-bound knowledge instead) — a standing rule now, not specific to this pilot. `t11` was designed live once, then **entirely redesigned and re-run live a second time same day** after the user reviewed the first version and pointed out two real gaps: it tested fabrication resistance twice but never actually probed for self-contradiction (the "no-contradiction" half of the trial's own stated purpose), and its fabrication-round count (2 of 10) was undercutting the pilot-wide reduction just agreed on. The redesigned skeleton replaces one fabrication round with two genuine self-contradiction probes (Dumbledore misquoting the target's own earlier in-conversation statement back to it, shallow then deep) and keeps only one fabrication round. Live findings from the final version: (1) round 1 again spontaneously named the target's cousin "Dudley" (absent from the supplied scene, which only ever says "his cousin") — the third independent occurrence of this exact fabrication across two separately-designed live runs of this trial, strengthening the pretrained-knowledge-contamination reading; (2) the shallow self-contradiction probe (round 3, misquoting the Dementor count) was resisted — the target firmly corrected it; (3) the deep self-contradiction probe (round 7, misquoting the location established in round 6) was **not** resisted — the target falsely agreed, directly contradicting its own round-6 statement, a genuine code-detectable self-contradiction with no supplied-fact judgment call involved; (4) this is the opposite depth pattern from every matched-probe result seen so far in this project (pilot2's `t13` and this pilot's first `t11` version both showed no depth effect for fabrication-agreement resistance) — suggestive, single-run evidence that self-contradiction resistance specifically may degrade with distance even where fabrication resistance didn't; (5) the retained single fabrication round (round 8, named "Mrs. Figg... near your house in July") was still confirmed, not resisted, consistent with this target's behavior in the discarded version.
- Verification: `python -m dataloader.research_sidecar data/research_annotations/characterbox_pilot3.json --pilot-config config/pilot_run_config.json` validates the manifest and resolves all 11 trials, including all 10 of the redesigned `t11`'s rounds, against the real scene 31 data. `config/play.yaml` was pointed at scene 31 (`target_character_id: 0`, `action_id: 0`, `play_role: 1` — the human played Dumbledore) for both live design sessions. The pilot's first full `evaluate.py` run is still pending as of this entry.

# `docs/`

## Folder-level comparison

### Added in this project

- `docs/research-contract.md`
- `docs/characterbox-provenance.md`
- `docs/characterbox-change-record.md`
- `docs/limitations.md`
- `docs/trial-design-guide.md`

### Intentionally left out from CharacterBox

- None. CharacterBox has no counterparts for these project-control documents.

### Present in both but modified

- None.

## Files

### `docs/research-contract.md`

- Status: Added by this project.
- Purpose: Fixes the research question, U/S/P meanings, paired controls, information-equivalence rule, hypotheses, outcomes, dual-source sampling, priority guardrails, and scope boundaries.
- Runtime consequence: None directly; implementation and experiments must conform to its controls.

### `docs/characterbox-provenance.md`

- Status: Added by this project.
- Purpose: Records CharacterBox source, inspected commit, licensing, reuse category, modifications, rationale, verification, and licence-notice location for copied and adapted components.
- Difference from this record: Provenance concerns origin and attribution; this change record concerns exact current code and filesystem differences.

### `docs/characterbox-change-record.md`

- Status: Added by this project.
- Purpose: Provides the folder-, file-, and symbol-level current-state comparison with CharacterBox and imposes the mandatory same-step update rule.

### `docs/limitations.md`

- Status: Added by this project.
- Purpose: Thesis-facing readable index of judge/evaluation-pipeline limitations — issues found and fixed during real pilot runs (round-1 `no_contradiction` ambiguity, the original World Consistency single-verdict design, the `checked_against` schema iterations, `judge_text()`'s empty-response and markdown-fence failure modes) and issues found and deliberately left open (World Consistency's contradiction-only scope missing entity fabrication, the Hermione case and its pretrained-knowledge hypothesis, non-orthogonal metrics, small pilot sample size / no significance testing yet, best-effort-only seed reproducibility, judge-model-dependent format reliability).
- Difference from provenance/change-record: Those two document *what changed in the code, when, and why* as an exhaustive dated audit trail; this document summarises *what it means for the research* — written to be read directly for a limitations section, with each item pointing back to its full provenance entry rather than repeating it.
- Runtime consequence: None; documentation only.

### `docs/trial-design-guide.md`

- Status: Added by this project.
- Purpose: Reusable methodology note for designing a new pilot's trials — the category taxonomy (normal fact-check, direct-contradiction stress fact-check, out-of-bound-knowledge fabrication with four named sub-flavors, open-ended, and exactly one multi-turn trial always last), the rule that only the multi-turn trial is designed live against real simulator output rather than written blind, a scene-grounding checklist, and file mechanics (validator command, `note` field convention, no fixed trial-count target). Extracted from how `characterbox_pilot.json` and `characterbox_pilot2.json` were actually built, so the pattern does not need to be rediscovered per pilot.
- Runtime consequence: None; documentation only — not read by any code.

# `tests/`

## Folder-level comparison

### Added in this project

- `tests/__init__.py`
- `tests/test_characterbox_data.py`
- `tests/test_characterbox_character.py`
- `tests/test_characterbox_scene_flow.py`
- `tests/test_context_priorities.py`
- `tests/test_human_player.py`
- `tests/test_path_safe_model_name.py` (2026-10-14)
- `tests/test_narrator.py`
- `tests/test_research_sidecar.py`
- `tests/test_simulator_mode.py`
- `tests/test_evaluate.py`
- `tests/test_llm_seed.py`

### Intentionally left out from CharacterBox

- None. The inspected CharacterBox commit contains no equivalent tracked unit-test suite.

### Present in both but modified

- None.

## Files

### `tests/__init__.py`

- Status: Added by this project.
- Purpose: Marks and describes the test package.

### `tests/test_characterbox_data.py`

- Status: Added by this project.
- Test count: Five.
- Coverage: Exact CharacterBox scene string, exact character string, stored but non-rendered `gender`, plain-dictionary action interface, 50-scene count, and absence of `chunk`.
- External calls: None.

### `tests/test_characterbox_character.py`

- Status: Added by this project.
- Test count: Five.
- Added test collaborators: `FakeLLM`, `FakeMemory`, and `FakeChain` exist only in the test.
- Coverage: Complete English S prompt; flat U prompt; ordered policy-driven P prompt; invalid-condition rejection; real `_generate_reaction()` and `generate_dialogue()` path; token-budget input; retrieved-memory insertion; raw and processed response; multiline quoted-speech extraction after stage directions; action reference; observation; and shared memory-save behavior.
- External calls: None.

### `tests/test_characterbox_scene_flow.py`

- Status: Added by this project.
- Test count: Two.
- Added test collaborators: `FakeLLM`, `FakeMemory`, and `SequentialFakeChain` exist only in the test.
- CharacterBox behavior reproduced: Initial actions converted into `last_round`; self-belief; environment-belief; synopsis; physical action; generated action passed as dialogue observation.
- Pilot integration coverage: Resolves the validated Luna/Neville trial through the unchanged `Data` loader, constructs the fixed player observation from the separate action/dialogue, uses the selected source Action Reference and dialogue-memory record, and proves the same non-empty source values reach U, S, and P. Empty self/environment beliefs are preserved rather than invented because the stored dataset does not provide them.
- Character-side flow coverage: Real Harry Potter scene values, simulator call inputs, action reference, prompt contents, response processing, and memory-save payload.
- Deliberately absent: Narrator decisions, interaction adjudication, state mutation, real retrieval, and real provider calls.

### `tests/test_research_sidecar.py`

- Status: Added by this project; CharacterBox has no equivalent test.
- Test count: Twenty-one.
- Coverage: Valid schema-v4 pilot selection through unchanged `Data`, including multiple independent trials sharing one pilot's scene/player/target/Action Reference; rejection of interaction actions, copied facts, non-sequential/blank turns, missing/identical roles, invalid source actions, empty trial lists, and duplicate trial IDs; rejection of the dropped `evaluation_cases`/`recent_memory_action_ids` fields; the optional per-trial `note` field (present with a category label on every real trial, accepted when absent, rejected when blank or non-string); and pilot-run-config validation (accepted default config, duplicate conditions, missing P policy ID, unknown fields).
- Test data handling: Loads the real sanitised dataset, pilot manifest, and pilot run-config, then mutates only in-memory copies for negative cases.
- External calls: None.

### `tests/test_human_player.py`

- Status: Added by this project; CharacterBox has no equivalent test.
- Test count: Four.
- Coverage: Stored gender metadata plus human action, dialogue, and dynamic reaction terminal methods accepting CharacterBox's existing observation/plot/time arguments, displaying the intended English label, preserving entered text, and returning the required human-source detail record.
- External calls: None; terminal input is patched and no LLM object is constructed.

### `tests/test_narrator.py`

- Status: Added by this project; CharacterBox has no equivalent test.
- Test count: Four.
- Coverage: Exact retained English common prompt, English `Position`/`State` parsing, English scene-update prompt and structured parsing, and absence of Chinese characters or `utils.detect_language` from the adapted Narrator source.
- External calls: None; a deterministic fake chain and method patching replace all model calls.

### `tests/test_simulator_mode.py`

- Status: Added by this project; CharacterBox has no equivalent test.
- Test count: Twenty.
- Coverage: Adds explicit pilot override precedence (pilot-level target/action, auto-loaded `pilot_config_path`), omitted-pilot configuration preservation, YAML-only interactive controlled loading, fresh per-(trial, condition) configs across a multi-trial pilot (asserting `trial_id`/`round` per call), scripted-turn terminal bypass, and expanded pilot/trial metadata (including `pilot_id`) to all previously covered controlled/dynamic behavior.
- Configuration isolation: Tests use an internal key-free pilot configuration and never load the user's live `config/play.yaml`.
- External calls: None; agent factories and progress iteration are mocked, and no memories, models, embeddings, or providers are constructed.

### `tests/test_characterbox_evaluation.py`

- Status: Added by this project; CharacterBox has no equivalent deterministic evaluator test.
- Test count: Seventeen (up from four).
- Coverage: Strict 1–5 parsing for all seven metrics; latest complete paired-run selection in manifest order; condition/policy blinding; complete trajectory rendering; critique-before-score ordering; malformed-score retry; retrying past a simulated empty score response; average and metadata output; `judge_text()`'s empty-response diagnostics (finish_reason surfaced, refusal surfaced when present, non-empty content passed through unchanged) and its rate-limit retry (retries past a real `openai.RateLimitError`, asserting the exponential-fallback backoff delays; honours a real `Retry-After` header, clamped to a 10s floor when the header is too short and passed through verbatim when it's generous; survives far more consecutive errors than the old 5-attempt cap; raises once `RATE_LIMIT_MAX_ATTEMPTS` is exhausted).
- External calls: None; `FakeJudge` returns deterministic critique/score responses, or a `(content, response_metadata, additional_kwargs)` tuple to simulate a real empty `AIMessage`.

### `tests/test_evaluate.py`

- Status: Added by this project; CharacterBox has no equivalent test.
- Test count: Thirty-nine (up from twenty).
- Coverage: H1 context truncation to exclude future rounds and self/environment belief; condition-blind H1 prompt; strict H1 JSON validation for every accept/reject branch across all three metrics, including every World Consistency claim-list rejection branch (missing/empty claims, a self-reported `decision` field rejected, missing claim text, `checked_against` required exactly when inconsistent, and — since the 2026-09-16 rename — both a populated and a `null` `checked_against` accepted when consistent); recovery of a response wrapped in a markdown JSON fence or a conversational preamble, and confirmation that genuinely non-JSON text is still rejected; `compute_consistency()`'s applicable-average and all-NA-returns-None cases; `evaluate_h1_turn()` retry-then-succeed and retry-exhaustion, retrying past a simulated empty judge response and surfacing `finish_reason` when every attempt is empty, the round-1 `no_contradiction` override (a judge-mislabeled PASS is forced to NA and `consistency` reflects the correction) and its round ≥2 non-interference (a real FAIL survives untouched), World Consistency FAIL correctly derived end-to-end from one inconsistent claim among several; `evaluate_h2_trial()` hypothesis tagging over the reused `evaluate_trajectory()`; the 2026-09-23 `quote`/`quote_verified` addition (missing `quote` rejected like any other structural gap; a quote verified true when it matches modulo whitespace/curly-quote differences; a fabricated/non-matching quote verified false end-to-end through `evaluate_h1_turn()` while consuming exactly one judge call, confirming it is flagged rather than retried).
- External calls: None; `FakeJudge` returns deterministic responses, or a `(content, response_metadata, additional_kwargs)` tuple to simulate a real empty `AIMessage`.

### `tests/test_llm_seed.py`

- Status: Added by this project; CharacterBox has no equivalent test.
- Test count: Three.
- Coverage: `utils.get_llm()`'s optional `seed` — omitted leaves `model_kwargs={}`; a set integer seed is forwarded as `model_kwargs={"seed": <value>}`; an explicit `null` seed in config also leaves `model_kwargs={}`.
- External calls: None; `ChatOpenAI` itself is mocked (`unittest.mock.patch`), so no client is constructed and no network call is possible.

### `tests/test_context_priorities.py`

- Status: Added by this project; CharacterBox has no equivalent test.
- Test count: Six.
- Coverage: Exact one-time assignment of all 13 fields under the primary 1–4 policy, plus rejection of missing, duplicate, unknown, empty, and non-continuously ranked assignments.
- Test data handling: Loads the real research configuration, then mutates only in-memory copies for negative cases.
- External calls: None.

# `third_party/`

## Folder-level comparison

### Added in this project

- `third_party/characterbox/LICENSE`

### Intentionally left out from CharacterBox

- None.

### Present in both but relocated

- CharacterBox's root `LICENSE` is stored at `third_party/characterbox/LICENSE`.

## Files

### `third_party/characterbox/LICENSE`

- Status: Copied without textual modification from CharacterBox and relocated.
- Reason: Clearly attributes copied/adapted CharacterBox software without implying that the MIT licence governs all newly written research code or franchise-derived data.
- Runtime consequence: None.

# `notebooks/`

## Folder-level comparison

### Added in this project

- `notebooks/results_dashboard.ipynb`
- `notebooks/trial_inspector.ipynb`

### Intentionally left out from CharacterBox

- None. CharacterBox has no equivalent analysis/inspection tooling.

## Files

### `notebooks/results_dashboard.ipynb`

- Status: Added by this project; CharacterBox has no counterpart.
- Purpose: Aggregate results dashboard reading `output/evaluation/h1_consistency.jsonl`/`h2_realism.jsonl` (plus the pilot manifest for trial categories). Three sections mirroring the study's hypotheses: H1 (per-condition 100%-stacked PASS/FAIL/NA bars per metric, plus a combined mean-consistency bar with `n=` labelled), H2 (grouped per-dimension bar chart across all three conditions with standard-error bars, plus a combined mean-realism bar), H3 (consistency-by-round line chart for multi-turn trials with a trend-line slope and an early/late-half split, plus first-fail-round/cumulative-fail-count tables) — H3 built from trials with more than one round, selected by round count rather than a hardcoded trial ID.
- Data handling: A `RUN_MODE` variable (`"latest"`/`"all"`/`"average"`) and a `runs_df` table (parsing `generation_run_id`'s embedded `time.time_ns()` suffix into a real timestamp) exist so multiple pilot runs accumulating in the same append-only output files can be filtered without manual cleanup; only `"latest"` has chart logic built so far.
- Runtime consequence: Read-only against existing output files; makes no model calls and does not modify `output/evaluation/`.
- Verification: Executed end-to-end via `jupyter nbconvert --execute` against real pilot output during development; no automated test suite (a notebook, not a module) — correctness was checked by inspecting its rendered tables/figures against the source JSONL directly.

### `notebooks/trial_inspector.ipynb`

- Status: Added by this project; CharacterBox has no counterpart.
- Purpose: Single-trial drill-down tool. Given one `generation_run_id` + `trial_id`, shows: canonical scene/player/target/action-reference data (with a live check that it is byte-identical across U/S/P, per `docs/research-contract.md` §5); the U/S/P dialogue transcripts; the actual character-generation prompt structure per condition (pulled from the saved `output/record/*/all/*.jsonl` model-call trace, not reconstructed — this is where U/S/P genuinely differ in structure, unlike the judge prompt); the H1 judge prompt per round per condition with a check that everything before `[Prior turns]` is identical across conditions; and the full H1 metric breakdown per condition (including, since the 2026-09-16 World Consistency redesign, each metric's individual claim list via `format_world_consistency()`, not a single evidence quote — updated the same day for the `conflicts_with` → `checked_against` rename, and again for `checked_against` becoming required on every claim rather than optional when consistent, so it now always prints a "checked against" line for a consistent claim, not only when the judge happened to provide one).
- Data handling: Searches every file under `output/record/*/trajectory/*.jsonl` and `output/record/*/all/*.jsonl` (glob, not one hardcoded scene/title path) so it keeps working as more scenes/datasets are added.
- Runtime consequence: Read-only; makes no model calls.
- Verification: Executed end-to-end via `jupyter nbconvert --execute` against real pilot output (both a 10-round and a single-round trial) during development. The World Consistency claim-list formatter was verified separately against a synthetic claim list, since the real output file predates that schema change.

# `tools/`

## Files

### `tools/compare_runs.py`

- Status: Added by this project (2026-10-14); CharacterBox has no counterpart.
- Purpose: Compares two or more generation runs of the same pilot. For each run it takes the trajectory file and, optionally, the H1/H2 evaluation files, and writes a Markdown report: mean H1 consistency and H2 realism by trial type and condition, the turns whose H1 score changed relative to the first run, and every reply side by side with its H1 decisions. Written to check whether the 2026-10-14 shared opening and the move to OpenRouter changed pilot 1.
- Runtime consequence: Read-only; makes no model calls and never modifies `output/`.
- Verification: Run against pilot 1 compared with itself (identical scores and no changed turns reported); no automated test.
