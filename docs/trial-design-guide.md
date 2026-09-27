# Trial design guide

## Purpose

A reusable pattern for designing a new pilot's `player_dialogue` lines, extracted from
how `characterbox_pilot.json` (scene 19, Luna/Neville) and `characterbox_pilot2.json`
(scene 12, Newt/McGonagall) were actually built. Follow this rather than re-deriving
the pattern from scratch for each new pilot. See `docs/limitations.md` for what these
categories were built to catch, and why several of them exist at all.

## Category taxonomy

Every single-round trial belongs to exactly one category, recorded in its `note`
field. Categories found useful so far:

1. **Normal fact check** — the player's line elicits one specific supplied field
   (position, states, time/location, character description, action reference).
   Targets a *different* field per trial across the set, so no single field dominates.
   This is the baseline: does the response draw on and stay consistent with an
   ordinary, non-adversarial supplied fact?
2. **Stress fact check (direct contradiction)** — the player asserts something that
   directly contradicts a specific supplied fact (wrong time, wrong location, denies
   something the scene states plainly). The sharpest test of whether the response
   stays grounded rather than agreeing with a leading premise.
3. **Out of bound knowledge fact check (false premise)** — the player asserts
   something never established anywhere in the supplied data at all, as distinct from
   contradicting a stated fact. This is a different failure mode from category 2 (see
   `docs/limitations.md`, "World Consistency catches contradiction, not fabrication")
   and deserves multiple trials covering different flavors of fabrication, not just
   one:
   - a specific named person among vaguely-implied-but-unnamed others (e.g. naming one
     of a scene's unnamed "onlookers");
   - a fabricated specific detail filling in a scene's own deliberately vague wording;
   - a fabricated prior incident/precedent with no basis in the supplied data;
   - a fabricated shared history/relationship between the two characters.
   Design at least 2–4 of these per pilot if the scene supports it, since which
   flavors get caught and which don't is itself an interesting result — don't settle
   for one example and call the category covered.
4. **Open-ended** — no specific field targeted; low factual demand, gives room for
   personality/emotion (H2) rather than testing H1 metrics. Include 1–2 per pilot so
   the trial set doesn't read as pure interrogation, which would flatten Naturalness
   for every condition equally and mask the real U/S/P differences.
5. **Multi-turn** — always exactly one per pilot, always the **last** trial in the
   file. See below — this one is not designed the same way as the other four.

## The multi-turn trial must be designed live, not written blind

Every other category can be written up front from reasoning about the scene alone.
The multi-turn trial cannot: writing 10 rounds of dialogue in one sitting means
guessing what the NPC will actually say at round 6 based on nothing, which produces
callbacks and pressure-tests that don't actually land.

Instead: fix a round-type skeleton first (what each round is *for* — an anchor
commitment, a fact-recall check, a callback at increasing distance, a false-premise
probe, an open-ended beat), then run the real controlled simulator interactively
(`python simulator.py -c config/play.yaml`, one condition — `S` is the reasonable
default, since it avoids any appearance of tuning content toward the P condition
specifically — no `--pilot` flag), and write each round's line in response to what the
NPC actually said in the previous round. Only the *wording* is decided reactively; the
skeleton and its rationale are fixed before generation starts, and the same 10 lines
get used identically across U/S/P once finalised, so no condition is treated
differently.

This is not a violation of `docs/research-contract.md` §10's guardrail against
post-hoc tuning — that guardrail is specifically scoped to the P priority-tier policy
(the manipulated variable under test), not to trial/item design.

See `docs/characterbox-provenance.md`'s 2026-08-30/09-01 entries for the first time
this was done (`characterbox_pilot.json`'s `t11`, 10 rounds, Luna/Neville) for a worked
example, including the live findings that came out of designing it this way.

## Grounding checklist before writing any line

Pull the real scene record first (`data/generated_data/Harry_Potter.json` or
equivalent) — event, time, location, description, both characters' position/states/
description, and the action reference the pilot resolves. Every fact-check line should
target something actually present in that record, not something assumed to be there.
A scene's own description sometimes implies unnamed entities (e.g. "onlookers," "a
student") without establishing who they are — this is exactly the seam category 3's
named-entity variant is built to test, so read the scene description for these seams
specifically when designing that category.

## Mechanics

- Validate with `python -m dataloader.research_sidecar <pilot file> --pilot-config config/pilot_run_config.json` after every edit — it resolves every trial against the real dataset and will catch a broken reference immediately.
- `note` is optional per the schema but should always be present in practice — see `dataloader/research_sidecar.py`'s `ALLOWED_TRIAL_FIELDS`. Keep the `"Category: ..."` prefix consistent (`trial_inspector.ipynb`'s category mapping and `results_dashboard.ipynb` both parse it) even when adding a longer free-text description after it.
- No hard rule on trial count — `characterbox_pilot.json` grew from 2 to 11 trials over the course of the project as gaps were found; add more of a category later rather than forcing coverage into too few trials up front.
