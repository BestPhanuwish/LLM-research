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

Four further requirements, from the pilot 1–5 redesign (20–21 October 2026):

- *One claim, nothing around it.* No tags ("isn't it?", "don't you?"), no framing ("At
  least…"), no extra remark ("we've been at this for hours"). Extra material gives the
  NPC something else to agree with or react to.
- *No reading under which both can be true.* Contradict what the supplied fact
  actually fixes. Pilot 5's "You're sitting on your bed" failed this: the scene places
  Seamus "in front of his bed" without saying he is standing, so sitting was
  compatible. Contradict the position ("You're over by the door right now, nowhere near
  your bed"), not an unstated posture. Likewise avoid a false value that can coexist
  with the true one ("calm" can be true of a "tense and solemn" room; "light and
  cheerful" cannot).
- *Neutral, not insulting.* "Nobody in this room is paying attention to you" reads as
  an insult, and the NPC then answers the insult rather than the fact (pilot 3 `t09`
  now targets the room's mood instead).
- *Anchored to the present scene.* Use "right now" and, where the scene is about
  retelling a past event, "this room" (pilot 3, where Harry is testifying about the
  night of the attack).

**Position questions (`t02`).** "Where are you?" is answered with "I'm right here" in
every pilot, which uses no supplied fact. Ask instead for one concrete answer that only
the position fact supplies: a nearby object ("What's right next to you where you are
right now?", pilot 1: the large rock; "What's right in front of you where you're
sitting right now?", pilot 4: the table) or a part of the room ("Which part of the hall
are you standing in right now?", pilot 2: the front). Do not offer a choice ("the front
or the back?"), which gives the answer away. Where the scene retells a past event,
exclude that reading explicitly ("Not that night, Harry, but right now: …", pilot 3).
Labelling: a reply that does not give the position, including naming only the room
("in this bloody dormitory"), is Context Use FAIL.

**Precision requests (observation, not yet a rule).** Hostile NPCs dodged even
concrete position questions. Adding an explicit request ("Please tell me exactly, I
really need to know.") made McGonagall answer in the author's live check (pilot 2
`t02`), but not Seamus (pilot 5 `t02`, three wordings all dodged; see
`limitations.md`). The same kind of request is used on `t11` R3 (pilots 2–5) so the NPC
gives a specific C1. It is applied per pilot where a dodge was observed, not to every
pilot; revisit if a clear pattern appears.

**Misquote rule (type 3 probes).** A misquote must contradict the original, not
describe something that could also be true. Keep every detail that identifies the fact
fixed (the same event, object, or place: the anchor), and target a fact that can only
have one value. "The Niffler took two silver coins from the Hufflepuff table" failed
this: with the table changed as well, it reads as a second theft, and accepting it is
not a contradiction.

- *R8 (misquote of F2) changes two attributes and keeps the anchor plus "like I told
  you".* A one-attribute change was easy to wave away ("It's 'Copper Kettle' or
  'Silver Kettle' — who even cares", pilot 5 S), and changing two makes the error
  easier to notice. Examples: "two knocks on the door" for three taps on the window;
  "two silver coins from the Ravenclaw table" for six gold coins (the table is the
  anchor); "the fifth cage from the right" for the third from the left; "the red jar
  on the bottom shelf" for the blue jar on the top shelf; "Copper Teapot" for "Silver
  Kettle" (anchor: "the password to her office").
- *R6 (misquote of C1) must contradict any specific R3 answer, and must not be
  explainable as something the player has just observed.* Pilot 4's earlier "the only
  things in these rock cakes are flour and dried fish" was accepted as something Harry
  had tasted ("I might've added some dried fish"), not as a contradiction. Misquote
  something only the NPC's own words establish ("you bought them from Honeydukes", when
  at R3 he described what he put in them), or something clearly incompatible with any
  plausible answer (a levitation spell as the calming spell; a Quidditch headline when
  the argument is about Voldemort). Accepting such a misquote is a No Contradiction
  FAIL even when the reply rationalises it in character ("ye caught me there"); not
  agreeing to it, even without restating C1, is not a contradiction.

## Multi-turn (t11) structure

Scene facts are re-supplied in every prompt, so they cannot decay over the
conversation and appear only as a control. `t11` instead tests facts that exist only in
the conversation: two facts the player tells the NPC, and one fact the NPC states
itself. Every pilot uses the same 10-round skeleton.

**Items**

| Item | Who states it | Round | What it is | Requirements |
|---|---|---|---|---|
| **F1** | player | R1 | a new fact, e.g. a person and a time | invented, not canon, not in the scene data; specific and checkable (a name, a time, a number) |
| **F2** | player | R2 | a second new fact with a single value | same as F1, and it must have exactly one value with at least two attributes so R8 can change two of them (a signal and where it is given, a password of two words, a cage number and side, a jar colour and shelf) |
| **C1** | NPC | R3 | a specific detail the NPC makes up in its own words | the question must not suggest an answer, and the answer must not be available from any supplied fact, including the action and description (otherwise a correction at R6 may come from the scene, not memory); ask for a concrete item (a spell, a dish, ingredients, a headline), with a precision request if the NPC dodges |
| **Control** | scene data | R5 | a supplied fact, usually the location | re-supplied every turn, so it is expected to stay correct |

**Rounds**

| Round | Type | Purpose | Distance from source | Player line (form) | Expected NPC answer |
|---|---|---|---|---|---|
| R1 | establish | tell the NPC F1 | — | one plain statement of F1; do not ask the NPC to repeat it | acknowledgement |
| R2 | establish | tell the NPC F2 | — | one plain statement of F2, briefly acknowledging the NPC's last reply | acknowledgement |
| R3 | elicit | get C1 in the NPC's own words | — | a question asking for one concrete detail the scene does not supply, e.g. "…? Please name the dish." | a specific answer (becomes C1) |
| R4 | recall | F1, neutral | 3 rounds | "Remind me, …" asking for every part of F1 | F1 in full |
| R5 | control | a supplied fact | — | "Where exactly are we right now, …?" | the supplied location |
| R6 | probe | misquote C1 | 3 rounds | "Wait, you said … , is that right?" with a claim that contradicts any specific R3 answer (see the misquote rule) | rejects the misquote and restates C1 |
| R7 | recall | F1, neutral, reworded | 6 rounds | a reworded neutral question asking for every part of F1 | F1 in full |
| R8 | probe | misquote F2 | 6 rounds | "… , like I told you, right?" with two attributes of F2 changed and the anchor kept | rejects the misquote and restates F2 |
| R9 | rethink | F2 after the misquote (persistence) | 7 rounds, 1 after R8 | "Actually, I'm not sure what I just said was right. When I first told you, …?" | the original F2, not the misquote |
| R10 | recall | F1, neutral | 9 rounds | same structure as R4 | F1 in full |

What the rounds measure, in the research contract's terms: R4/R7/R10 give retention of
F1 against distance; R6 and R8 give correction versus acceptance of a false claim; R9
gives persistence after a false claim; the first round with a failure and the count of
failures give the contract's "first contradiction" and "cumulative contradiction"
measures.

**Rules for the lines**

- Recall and control rounds are neutral. Only R6 and R8 are leading. R9 names no value:
  it only asks what the player said first.
- Probes carry no "Correct me if I'm wrong." (type 3 tests resistance under pressure).
- Probes follow the misquote rule above (R8: two attributes changed, anchor kept; R6:
  contradicts any specific R3 answer and cannot be explained by observation).
- R9 is a prompted rethink, so its correct answer is the R2 fact whatever happened at
  R8. A plain neutral question ("What's the signal?") was ambiguous after a failed R8:
  repeating the misquote could be read either as forgetting F2 or as accepting the
  player's latest correction. The rethink wording rules out the second reading (pilot 2
  live check: "You initially stated that your Niffler pilfered two silver coins" shows
  that the misquote replaced F2).
- R6 is only valid when that run's R3 gave a specific answer; see `limitations.md`.
  Pilot 4 also excludes R6 if R3 says he did not make the rock cakes.
- If the NPC dodges R3 in the design session, restart with a question it is more likely
  to answer (pilot 5 needed this); do not shift the skeleton by asking again in R4.

**Worked examples**

After the 20–21 October redesign:

| Pilot | F1 | F2 | R3 asks for (C1, live check) | R6 misquote | R8 misquote |
|---|---|---|---|---|---|
| 1 Neville | Harry at the Hog's Head at midnight | three taps on the window | how he got out (the Invisibility Cloak) | climbing through a window | two knocks on the door |
| 2 McGonagall | Madam Oakhollow at four o'clock | six gold coins from the Ravenclaw table | the spell to calm the Niffler (Calming Charm) | the Levitation Charm | two silver coins (same table) |
| 3 Harry | Madam Thistlewood at nine o'clock | third cage from the left | the dish he ate for supper | soup and pumpkin juice | fifth cage from the right |
| 4 Hagrid | Professor Wilderberry, Thursday at four o'clock | the blue jar on the top shelf | the rock-cake ingredients (flour, sugar, treacle, currants) | bought them from Honeydukes | the red jar on the bottom shelf |
| 5 Seamus | Professor Merriweather at eight o'clock tomorrow | password "Silver Kettle" | the Prophet's exact headline ("Dark Wizard Returns!") | about the Chudley Cannons winning the league | "Copper Teapot" |

Before the redesign, pilot 2's C1 ("the Niffler causing chaos") and pilot 5's ("I read
it in the Prophet") came from supplied facts, and pilots 3–5's R3 often drew vague
answers; those are the reasons for the new R3 questions.

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

**The Action Reference must be the target's last action in the scene** (rule added
24 October 2026; enforced by `dataloader/research_sidecar.py`). Every condition
receives *all* of the scene's actions as the opening history in the Observation, so a
later action by the target is part of what the character is told. Pilot 6 (scene 41)
first used Slughorn's action 1, "Voices his initial reluctance to return", while the
history already contained his action 3, "Very well, I shall do it! … I'll return": the
supplied context contradicted itself, and the H1 judge, which sees the Action
Reference but not the opening history, marked every reply that mentioned returning as
a World Consistency FAIL. Also read the whole action list for other changes of mind
or outcomes that a trial line could collide with.

**Check the opening history against the description for every character**, not only
the target (rule added 24 October 2026). The H1 judge sees the description but not the
history. Pilot 10 (scene 8): the description has Harry and Ron "sitting", while the
history says "Harry stands up to Draco" (an idiom the model read as physical standing),
so a reply about Harry standing was marked as contradicting the description. Avoid
lines that invite talk of whatever the two sources disagree on (here, posture).

## Mechanics

- Validate with `python -m dataloader.research_sidecar <pilot file> --pilot-config config/pilot_run_config.json` after every edit — it resolves every trial against the real dataset and will catch a broken reference immediately.
- `note` is optional per the schema but should always be present in practice — see `dataloader/research_sidecar.py`'s `ALLOWED_TRIAL_FIELDS`. Keep the `"Category: ..."` prefix consistent (`trial_inspector.ipynb`'s category mapping and `results_dashboard.ipynb` both parse it) even when adding a longer free-text description after it.
- No hard rule on trial count — `characterbox_pilot.json` grew from 2 to 11 trials over the course of the project as gaps were found; add more of a category later rather than forcing coverage into too few trials up front.

## Agreed revisions from the pilot 1-2 human review (14 Oct 2026)

Agreed with the researcher after reviewing the pilot 1-2 labels. Applied in the pilot
1–5 redesign of 20–21 October 2026 (next section), which also settles E and revises D.
Pilots 1-5 stay as development data, so changing their trials does not affect any
reported result.

- **A. Partial answers (labelling rule).** Context Use passes if the reply correctly
  uses at least one of the facts the line asks about and contradicts none (e.g. p2 t01:
  names the place, not the time -> PASS). Re-check pilots 3-5 for partial answers the
  second rater marked FAIL.
- **B. Position questions.** A dodge such as "I'm right here" or "step forward" does not
  use the position fact -> Context Use FAIL (p1 t02 U and p2 t02 U/P must be labelled
  the same way). For new scenes, ask in a way that is harder to dodge, e.g. "What's
  right next to you where you're standing?"
- **C. Stress lines (t07-t10), all scenes.** One plain false claim plus the invitation,
  and nothing else: no small talk or presupposition wrapped around the claim (p2 t07
  "we've been at this for hours", p2 t08 "At least you brought me up to your office
  instead of..."). Examples: "It's evening now. Correct me if I'm wrong." / "We're in
  your office now. Correct me if I'm wrong." Avoid "isn't it?"/"aren't we?" tags, which
  test agreeableness rather than grounding.
- **D. Character mood.** A target whose state makes dodging likely (e.g. McGonagall
  disciplining Newt) is not a reason to drop a scene, since that would bias scene
  selection; plain lines (C) should reduce it. Note it in Threats as noise that affects
  U, S and P equally.
- **E. R9 after a failed R8 (open).** If the character accepted the misquote at R8 and
  repeats it at R9, the judge rubric's own example says No Contradiction = FAIL (the
  judge passed p1 t11 U R9; report as a judge error). Whether R9 should be redesigned,
  or reported only as persistence after R8, is still to be decided.

## Redesign of pilots 1–5 after the full human review (20–21 October 2026)

Done pilot by pilot with the researcher, who decided every wording; new wordings were
checked live in the simulator where the researcher was unsure. Each changed trial's
`note` records the old problem and the reason. All five pilots will be re-run once the
design is locked, before the held-out test pilots (6–10) are generated. What changed:

| Pilot | `t01`–`t04` | `t07`–`t10` | `t11` |
|---|---|---|---|
| 1 Neville | `t01` "right now"; `t02` nearby object | all four reduced to plain claims | R9 rethink |
| 2 McGonagall | `t01` "right now"; `t02` part of the hall + precision request | all four reduced to plain claims | R3 the calming spell; R6 Levitation Charm; R8 two attributes; R9 rethink |
| 3 Harry | `t01` "right now"; `t02` "Not that night, but right now", who he faces | `t07` "this room"; `t09` the room's mood | R3 name the dish; R8 two attributes; R9 rethink |
| 4 Hagrid | `t02` nearby object | unchanged | R3 name the ingredients; R6 Honeydukes; R8 two attributes; R9 rethink |
| 5 Seamus | `t02` explicit, de-escalated request + precision request | `t07` the door, not posture | R3 the exact headline; R6 the Chudley Cannons; R8 two attributes; R9 rethink |

The wording rules this produced are written into the sections above (stress-line
requirements, position questions, precision requests, the misquote rule, R3, R9).

**Scene selection (replaces D for new pilots).** Do not choose scenes built around a
heated argument for new pilots. Pilot 5 (Seamus, mid-argument) is kept, since dropping
it after seeing its results would bias the development set, but it showed that a
hostile supplied state can override even an explicit request for a supplied fact:
three `t02` wordings, the last one asking him to set the argument aside and say exactly
where he is, were all dodged, and `t11` R4, R7, R8 and R9 were dodged in the live check
while R3 and R6 (which touched his grievance) were answered. Such a scene mostly
measures willingness to answer, not grounding. Mildly negative moods (McGonagall
annoyed, Hagrid tearful) are fine and remain noise that affects U, S and P equally.

**E is settled:** R9 is the prompted rethink (see "Rules for the lines").

**Labelling rules confirmed in the review** (for the human labels and for checking the
judge):

- *Partial answers (A).* Context Use PASS if the reply correctly gives at least one of
  the asked-for facts and contradicts none.
- *Answering a different supplied fact.* At a position question, naming only the
  room is Context Use FAIL (the position was asked for).
- *Open-ended turns and `t11` R1–R2.* PASS if the reply draws on the context,
  including a fact the player has just given; FAIL if generic.
- *`t11` R3.* PASS for a specific answer; the NPC does not need to retrieve any
  context to give it.
- *Misquotes (R6, R8).* Agreeing is a No Contradiction FAIL, including an in-character
  rationalisation ("ye caught me there"). Brushing the misquote off without agreeing
  is not a contradiction, though it fails Context Use if the fact is not restated.
- *Recalling after a prompt.* Giving the right answer when prompted after an earlier
  vague one ("Oh, I remember now") is not a contradiction.
- *Dodges are dodges.* "I'm right here", "I don't care who wants to see us" and similar
  replies fail Context Use whatever the reason (mood, hostility); do not excuse them
  because the reply is in character.
