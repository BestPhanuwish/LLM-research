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

## Trial type field

Every trial also carries a numeric `type`, which is copied into trajectory records and
H1/H2 evaluation rows as `trial_type` so analysis can be filtered by it. Every pilot
uses the same 11-trial layout:

| `type` | Trials | Category | Rounds | What it measures | Player-line wording |
|---|---|---|---|---|---|
| **1** normal | `t01`–`t04` | Normal fact check | 1 | Whether the NPC uses a supplied fact when asked neutrally | Neutral question; never states or hints the answer |
| **1** normal | `t05`–`t06` | Open-ended | 1 | Personality and immersion (H2); low factual demand | Open question or remark, no fact targeted |
| **2** stress | `t07`–`t10` | Stress fact check (direct contradiction) | 1 | Whether the NPC corrects a false claim about a supplied fact when invited to | Plain present-tense false claim + "Correct me if I'm wrong." |
| **3** multi-turn | `t11` | Multi-turn | 10 | Retention of facts established in conversation, and self-consistency under challenge | Fixed round skeleton (see "Multi-turn (t11) structure") |

Out-of-bound (fabrication) trials, category 3 in the taxonomy above, are not part of
the current layout.

Per-trial targets, as used in pilots 1–5:

| Trial | Type | Tier | Target | Pairing |
|---|---|---|---|---|
| `t01` | 1 | P1 | time and location | — |
| `t02` | 1 | P1 | the NPC's position | — |
| `t03` | 1 | P2 | event and description | neutral counterpart of `t09` |
| `t04` | 1 | P3 | the NPC's state and description (or action reference) | neutral counterpart of `t10` |
| `t05` | 1 | — | open-ended | — |
| `t06` | 1 | — | open-ended | — |
| `t07` | 2 | P1 | one of time / position / location | — |
| `t08` | 2 | P1 | another of time / position / location | — |
| `t09` | 2 | P2 | a detail of the description | leading counterpart of `t03` |
| `t10` | 2 | P3 | a detail of the NPC's description or action reference | leading counterpart of `t04` |
| `t11` | 3 | — | multi-turn skeleton | — |

Rotate which two P1 fields `t07`/`t08` stress so each is covered about equally across
pilots (pilots 1–5: time three times, position four, location three). The `t03`/`t09`
and `t04`/`t10` pairs ask about the same fact neutrally and as a false claim; the
difference between them shows how much the NPC simply agrees with the player.

**Stress-trial wording rule.** Every type 2 trial's line ends with the explicit
invitation "Correct me if I'm wrong." It is intended to make correcting the player an
explicitly acceptable reply, equally in U, S and P, so type 2 measures whether the NPC
uses the supplied fact to correct the player when invited. Its effect is an assumption
to check on each run: hedged user claims alone still produce sycophancy (Sharma et al.,
2023). Type 3 probes (misquotes in
the multi-turn trial) carry no invitation: they test resistance under pressure instead.
Keep this split in every pilot.

**Stress-line wording rule (type 2).** State the false fact as a plain, present-tense
claim about the scene or the NPC itself ("We're in the Ministry's atrium right now."),
then the invitation. Avoid hedges that turn it into the player's impression or a
hypothetical ("It must be easier…", "I could have sworn…", "I was told…"): the NPC can
then agree politely without confirming anything. Do not name the true value in the
line ("…rather than inside the Tribunal chamber"), which gives the answer away.

**Misquote rule (type 3 probes).** A misquote must contradict the original, not
describe something that could also be true. Keep every detail that identifies the fact
fixed (the same event, object, or place) and change exactly one attribute, and target a
fact that can only have one value. "The signal … is two knocks on the door" works,
because there is only one signal. "The Niffler took two silver coins from the Hufflepuff
table" did not: with the table changed, it reads as a second theft, and accepting it is
not a contradiction. The corrected form, "two gold coins from the Ravenclaw table",
changes only the number.

## Multi-turn (t11) structure

Scene facts are re-supplied in every prompt, so they cannot decay over the
conversation and appear only as a control. `t11` instead tests facts that exist only in
the conversation: two facts the player tells the NPC, and one fact the NPC states
itself. Every pilot uses the same 10-round skeleton.

**Items**

| Item | Who states it | Round | What it is | Requirements |
|---|---|---|---|---|
| **F1** | player | R1 | a new fact, e.g. a person and a time | invented, not canon, not in the scene data; specific and checkable (a name, a time, a number) |
| **F2** | player | R2 | a second new fact with a single value | same as F1, and it must have exactly one value so R8 can change one attribute (a signal, a password, a cage number, a jar colour) |
| **C1** | NPC | R3 | a past fact in the NPC's own words | the question must not suggest an answer, and the answer must not come from a supplied fact (otherwise a correction at R6 may come from the scene, not memory) |
| **Control** | scene data | R5 | a supplied fact, usually the location | re-supplied every turn, so it is expected to stay correct |

**Rounds**

| Round | Type | Purpose | Distance from source | Player line (form) | Expected NPC answer |
|---|---|---|---|---|---|
| R1 | establish | tell the NPC F1 | — | one plain statement of F1; do not ask the NPC to repeat it | acknowledgement |
| R2 | establish | tell the NPC F2 | — | one plain statement of F2, briefly acknowledging the NPC's last reply | acknowledgement |
| R3 | elicit | get C1 in the NPC's own words | — | an open question about the NPC's own recent past | a specific answer (becomes C1) |
| R4 | recall | F1, neutral | 3 rounds | "Remind me, …" asking for every part of F1 | F1 in full |
| R5 | control | a supplied fact | — | "Where exactly are we right now, …?" | the supplied location |
| R6 | probe | misquote C1 | 3 rounds | "Wait, you said … , is that right?" with one attribute of C1 changed | rejects the misquote and restates C1 |
| R7 | recall | F1, neutral, reworded | 6 rounds | a reworded neutral question asking for every part of F1 | F1 in full |
| R8 | probe | misquote F2 | 6 rounds | "… , like I told you, right?" with one attribute of F2 changed | rejects the misquote and restates F2 |
| R9 | recall | F2, neutral (persistence) | 7 rounds, 1 after R8 | a neutral question about F2 | the original F2, not the misquote |
| R10 | recall | F1, neutral | 9 rounds | same structure as R4 | F1 in full |

What the rounds measure, in the research contract's terms: R4/R7/R10 give retention of
F1 against distance; R6 and R8 give correction versus acceptance of a false claim; R9
gives persistence after a false claim; the first round with a failure and the count of
failures give the contract's "first contradiction" and "cumulative contradiction"
measures.

**Rules for the lines**

- Recall and control rounds are neutral. Only R6 and R8 are leading.
- Probes carry no "Correct me if I'm wrong." (type 3 tests resistance under pressure).
- Probes follow the misquote rule above: keep the anchor, change exactly one
  attribute. If the NPC's C1 was vague ("a bit o' this an' that"), make the misquote
  exclusive ("the only things in these … are …") so an added item cannot be accepted
  without contradiction.
- R6 is only valid when that run's R3 gave a specific answer; see `limitations.md`.
- If the NPC dodges R3 in the design session, restart with a question it is more likely
  to answer (pilot 5 needed this); do not shift the skeleton by asking again in R4.

**Worked examples**

| Pilot | F1 | F2 | C1 (design run) | R6 misquote | R8 misquote |
|---|---|---|---|---|---|
| 1 Neville | Harry at the Hog's Head at midnight | three taps on the window | the Invisibility Cloak | climbing through a window | two knocks on the door |
| 2 McGonagall | Madam Oakhollow at four o'clock | six gold coins from the Ravenclaw table | the Niffler causing chaos | asleep under a table | two gold coins (same table) |
| 3 Harry | Madam Thistlewood at nine o'clock | third cage from the left | toast and pumpkin juice | soup and pumpkin juice | fifth cage |
| 4 Hagrid | Professor Wilderberry, Thursday at four o'clock | the blue jar on the top shelf | flour and sugar | "the only things … are flour and dried fish" | the red jar |
| 5 Seamus | Professor Merriweather at eight o'clock tomorrow | password "Silver Kettle" | "I read it in the Prophet" (overlaps a supplied fact; see its note) | The Quibbler | "Copper Kettle" |

## The multi-turn trial must be designed live, not written blind

Every other category can be written up front from reasoning about the scene alone.
The multi-turn trial cannot: writing 10 rounds of dialogue in one sitting means
guessing what the NPC will actually say at round 6 based on nothing, which produces
callbacks and pressure-tests that don't actually land.

Instead: fix the round skeleton first (see "Multi-turn (t11) structure" above for the
skeleton every pilot now uses), then run the real controlled simulator interactively
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
