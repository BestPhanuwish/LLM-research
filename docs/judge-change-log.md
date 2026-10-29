# Judge change log

What changed in the evaluation judge from 27 September 2026 onward, why, and the real
result that prompted each change. The detailed audit trail for each change is in
[characterbox-provenance.md](characterbox-provenance.md) (entries of the same date);
this file is the readable summary.

All examples are real judge outputs on pilot runs. "Before" means the rubric in force
before that change; results from different judge versions are not comparable, so each
pilot must be re-evaluated after a change.

## Current judge at a glance

| Setting | Value |
|---|---|
| Judge model | `google/gemma-4-31b-it` via OpenRouter (`config/evaluate.yaml`), selected 21 October from seven candidates; `gpt-4o` before that (see "Judge model selection" below) |
| H1 rubric version | 14 (`h1_rubric_version`), decided 22 October; see "Rubric version decision" |
| Temperature / seed | 0 / 1 |
| H1 metrics | Context Use, World Consistency (claim list), No Contradiction |
| H2 metrics | CharacterBox's seven-metric critique-then-score judge; one sentence per prompt limits it to the NPC (change 10); the character block includes position and state (change 12) |
| Extra fields per H1 row | `judge_seed`, `trial_type`; per claim: `quote_verified`, `checked_against_repaired`, `original_verdict` |

What each H1 metric covers now:

| Metric | Checks the response against | Main failure it catches |
|---|---|---|
| **Context Use** | the fact the player's turn asks or makes a claim about, whether supplied (scene, character, action) or established earlier in the conversation | dodging, going along with a false claim, stating a different fact |
| **World Consistency** | supplied scene, character, and action facts only | a claim that contradicts a supplied fact |
| **No Contradiction** | the character's own earlier turns and facts the player established earlier | accepting a misquote, or changing an established fact |

---

## 1. Judge seed recorded — 29 September

**Change.** `seed: 1` added to `config/evaluate.yaml`; every H1/H2 row stores
`judge_seed` next to `judge_model`.

**Why.** Temperature 0 alone still varies between runs. A fixed seed reduces that
(OpenAI treats it as best-effort, not a guarantee), and storing it lets every score be
traced to the settings that produced it.

**Note.** The seed later caused a problem with retries: see change 4.

## 2. Trial type carried into judge output — 29 September

**Change.** Each pilot trial has a `type` (1 normal, 2 stress, 3 multi-turn), copied
into every H1/H2 row as `trial_type`.

**Why.** To analyse one kind of trial at a time (for example, H1 on stress trials only)
without parsing free-text notes.

## 3. Dodging fails, claims come from the quote, playing along is a claim — 30 September

Four changes to the H1 prompt.

**3a. Context Use: dodging is a failure.** Before, a reply that ignored the player's
question could still PASS.

> **t07 U** (pilot 1). Luna: "Good thing we came out to meet this early in the morning.
> Correct me if I'm wrong." (supplied time: late evening)
> Neville: "I just hope they don't take too long... We need to be ready for anything."
>
> Before: Context Use **PASS**. After: **FAIL**, "does not address the false claim
> about the time being early in the morning."

**3b. Claims must be built from the quote.** Before, the prompt let the judge
"paraphrase" a claim, so it could write the *correct fact* as the claim and check it
against itself.

> **t08 U** (pilot 1). Luna: "Is that a tree you're hiding behind right now?"
> (supplied position: behind a large rock)
> Neville: "Well, if it is, it's the most nervous tree I've ever seen!"
>
> Before: claim "Neville is hiding behind a large rock", quote "…the most nervous tree
> I've ever seen!" → **consistent**. The claim did not match its own quote.
> After: claim "**Neville accepts that he is hiding behind a tree**" → **inconsistent**;
> Context Use **FAIL**. The JSON now lists `quote` before `claim`.

**3c. Playing along counts as a claim.** Accepting or joking along with the player's
premise is listed as a claim even when never stated outright (the t08 case above).

**3d. Examples no longer reuse the pilots.** The rubric's examples used the Shrieking
Shack and "Yeah, it's bright", which are pilot 1's scene and trial t09. They now use an
invented scene (Mira, a gatekeeper at Thornbury's east gate). A test fails if pilot
words (Luna, Neville, Niffler, …) return to the rubric.

## 4. Player lines are never evidence; No Contradiction checks every claim; retries explain the error — 30 September

**4a. The player's lines cannot support a claim.** The player may be mistaken or
deliberately lying; the probes are designed that way.

> **t11 U R8** (pilot 1). Luna: "The signal when we meet Harry is two knocks on the
> door, like I told you, right?" (she said "three taps on the window" in R2)
> Neville: "Um, yes, two knocks—just like we practiced."
>
> Before: claim "the signal is two knocks" → **consistent**, checked against
> "**Player's current turn**: 'The signal … is two knocks on the door.'" The false
> claim was verified against itself.

**4b. No Contradiction must check every claim, including accepting a misquote.**

> **t11 U R6** (pilot 1). Luna: "Wait, you said you got out of the castle by climbing
> through a window, is that right?" Neville (R3): "I just followed the secret passage
> from the Herbology shed." Neville (R6): "Yes, but shh! If anyone hears us, we'll be
> in serious trouble."
>
> Before: No Contradiction **PASS**; the judge compared only "if anyone hears us" with
> an earlier "be quiet" line. After: **FAIL**, contradicted round 3: "'Yes, but shh!'
> accepts the false claim about climbing through a window."

**4c. Retries state why the last answer was rejected.** With temperature 0 and a fixed
seed (change 1), resending the same prompt returns the same rejected answer, so
retries were useless. Each retry now adds a "[Correction]" note with the reason.

## 5. A consistent claim citing the player is repaired, not fatal — 30 September

**Change.** If a *consistent* claim cites the player, the code records "No supplied
fact addresses this claim." and flags the claim (`checked_against_repaired: true`)
instead of stopping the evaluation.

> **t11 S R9** (pilot 2). McGonagall: "The Niffler has pilfered no fewer than six gold
> coins from the Ravenclaw table." This answer is correct, but "six gold coins" exists
> only in the conversation, so the judge cited Newt's R2 line four times, ignored the
> correction, and **the evaluation stopped**. After the change, this answer parses as
> World Consistency PASS with the claim flagged.

## 6. No Contradiction covers facts the player established; World Consistency cannot cite the conversation — 30 September

**Change.** A fact the player states in an earlier turn is established for the rest of
the conversation, whether or not the character repeated it. If the player later states
a different version, the earlier one holds. World Consistency now covers supplied facts
only; citing a conversation round ("Round 2: …", "prior turn") is treated like citing
the player.

**Why.** In pilot 1 `t11`, Neville never repeated "three taps", so under the old
definition (the character's own words only) accepting "two knocks" could not fail. The
judge caught it only sometimes, by breaking its own rule:

| Turn | Neville | No Contradiction before |
|---|---|---|
| R8 U | "Um, yes, two knocks" | FAIL vs round 2 (by breaking the rule) |
| R8 S | "Um, yeah, two knocks, right." | PASS |
| R9 U | "The signal is two knocks" | PASS |
| R9 S | "It's two knocks, remember?" | PASS |

Separately, World Consistency "caught" R8 by citing "Round 2: Signal = three taps…",
which is Luna's line without the word "player": the judge was choosing on its own which
of Luna's two statements was true.

**Assumption to report.** Earlier player statements are treated as true. This holds
for these scripted trials (every `t11` has the same skeleton: R1 and R2 are the
player's true statements, later misquotes are false), but not necessarily in open play.

## 7. Conversation conflicts are reclassified, never fatal — 30 September

**Change.** Any claim citing the player or a conversation turn, consistent or not, is
recorded under World Consistency as "No supplied fact addresses this claim." The
judge's original verdict and citation are kept in `original_verdict`.

> **t11 U R8** (pilot 1), first run after change 6. The judge answered No
> Contradiction **FAIL, round 2** every time (correct), but also kept marking World
> Consistency inconsistent against "Round 2: …" and ignored the correction, so the
> evaluation stopped after four attempts. Now: No Contradiction FAIL; World Consistency
> PASS with `original_verdict: {consistent: false, checked_against: "Round 2: …"}`.

**Why this is correct.** Since change 6, conversation facts belong to No Contradiction.
Counting the same error in both metrics was a double count.

## 8. Evidence before decision; No Contradiction examples completed — 30 September

**Change (prompt only).** Context Use and No Contradiction now write `evidence`
**before** `decision`, in the format and every example, with the rule "choose the
decision that the evidence supports". The PASS step no longer tells the judge to quote
the most relevant earlier turn "even though they do not conflict". Two full example
answers were added: accepting a changed version of a player-established fact, and that
changed version persisting after a neutral question.

> **t11 S R8** (pilot 1, after change 7). Neville: "Um, yeah, two knocks, right."
> No Contradiction: **PASS**, with evidence "Round 2: 'the signal is three taps on the
> window.' This response: 'Um, yeah, two knocks, right.' **contradicts** the earlier
> established signal." The judge's reasoning was right; the label came first and was
> wrong.

**Why the prompt caused it.** The label was written before the reasoning; the PASS
instruction asked for the conflicting turn to be quoted under a PASS; and no full
example showed No Contradiction failing on a fact only the player stated, or on the
round-9 kind of case (a neutral question after the false version was accepted).

## 9. Repeating one's own earlier contradiction is still a contradiction — 30 September

**Change (prompt only).** No Contradiction: agreeing with the character's own earlier
statement does not excuse a contradiction; if that earlier statement already
contradicted an established fact, repeating it contradicts the same fact again. The
judge must compare against the round where the fact was first established.

> **t11 R9** (pilot 1, after change 8). Neville (R9): "Um, it's two knocks, remember?"
> No Contradiction: **PASS**, evidence "Round 8: 'Um, yeah, two knocks, right.' This
> response: 'Um, it's two knocks, remember?' **Both confirm** the signal is two knocks."
> The judge compared R9 with Neville's own R8 (which was already wrong) instead of
> Luna's R2, where the fact was established.

## 10. H2 judges only the NPC, not the scripted player lines — 21 October

**Change.** Both H2 prompts now name the character being evaluated. The critique
prompt adds, after CharacterBox's opening line: "Evaluate only {NPC}'s actions and
dialogue. The other character's lines are fixed test inputs written by the researcher;
do not critique them, and judge {NPC}'s replies as responses to them." The scoring
prompt adds: "Score only {NPC}; the other character's lines are fixed test inputs and
are not part of the evaluation." Nothing else in either prompt changed.

**Why.** CharacterBox's prompts never say whose performance is judged, which was fine
for its fully model-generated play. Here the player's lines are probes, and about 1 in
5 of the 165 pilot 1–5 critiques blamed them: "The logical coherence is disrupted by
Newt's question about the location and time, which seems out of place" (p2 `t01` P);
"Harry's question about who is present seems unnecessary" (p4 `t03`, all three
conditions); "significant content redundancy, particularly with Harry repeatedly asking
about the remedy's details" (p4 `t11` P). The scoring step uses the critique, so the
blame reached the NPC's score.

**Effect.** H2 results before this change are not comparable with later ones; all
pilots are re-run. To check: count critiques that still mention the player's lines
after the re-run. This is a departure from CharacterBox's verbatim prompts, recorded in
`characterbox-change-record.md`.

## 11. Context Use rubric states the adopted definition — 21 October

**Change.** The Context Use rubric in `evaluate.py` now says what the definition
decision below had only recorded: the context includes facts established earlier in
the conversation, which count exactly like supplied facts. The judge first decides
which of three kinds of turn the player's line is: (1) asks about or claims a specific
context fact, including "you said…"/"like I told you…" (PASS if addressed correctly,
one of several asked-for facts is enough; FAIL for a dodge, accepting a false claim or
misquote, or a different fact; naming only the room for a position question is a
dodge); (2) asks about something no context supplies, such as the character's own past
(PASS for a specific answer; do not substitute a supplied fact); (3) asks about no
specific fact (PASS if the reply draws on the context, including what the player just
said; FAIL if generic). NA is left only for a line not addressed to the character. Four
examples were added, and the three response-format examples that showed Context Use NA
on conversation-fact turns now show the decision the rule gives.

**Why.** The old wording ("a fact in the supplied scene, character, or action
information") was left in place on 30 September to avoid re-evaluating every pilot.
The judge bake-off showed the cost: `openai/gpt-6-luna` followed it literally and
labelled Context Use NA on every `t11` recall and misquote round and on open-ended
turns (27 of its 33 disagreements with the author's pilot 1 labels, Context Use κ
0.21), and Qwen3-235B did so on 3 turns and checked a substituted supplied fact on
others. gpt-4o had applied the wider definition without being told. A judge comparison
on the old wording therefore measured which model guessed the unstated definition.

**Effect.** All H1 results before this change used the old wording. The bake-off
judges (gpt-4o, gpt-6-luna, Qwen3-235B) are re-run on pilot 1 with the new rubric.

## 12. H2 judge sees the NPC's position and state — 21 October

**Change.** The H2 prompts' character block now lists the NPC's supplied Position and
State as well as its name and description. Nothing else changed.

**Why.** The H2 judge was checking "Factual Accuracy" without the character facts the
NPC had been given. Qwen3-235B marked Neville's supplied "large rock" down as "an
unverified element" (pilot 1 `t02` U, all seven scores 1). gpt-4o and gpt-6-luna did
not make this error on pilot 1, but nothing prevented it.

**Effect.** H2 results before this change are not comparable with later ones; H2 is
re-run with the bake-off judges.

## Judge model selection — 21 October

**Decision.** The judge model changed from `gpt-4o` to **Gemma 4 31B**
(`google/gemma-4-31b-it`), for both H1 and H2.

**How.** The author hand-labelled every turn of re-generated pilots 1 and 2, blind to
the condition (`data/research_annotations/judge_validation/judge_selection/`). Seven
candidates judged pilot 1 with the change-11 rubric; Qwen2.5-14B (local, Ollama) and
DeepSeek V4 Flash were dropped after pilot 1, and the other five also judged pilot 2.
Combined over both pilots (294 items, 48 author FAILs): Gemma 4 31B κ 0.852 (38/48
FAILs caught, 1 extra), gpt-6-luna 0.837 (45/48, 11 extra), Qwen3-235B 0.735, gpt-4o
0.659, Gemini 3.1 Flash-Lite 0.398. As a reference, the generator gpt-4o-mini used as a judge on the same items reached κ 0.077 (3/48 FAILs caught), so the selected judge is a much stronger evaluator than the model it judges. Gemma 4 31B was chosen for the highest κ, the fewest
false FAILs, perfect No Contradiction agreement, temperature 0 and seed support,
published weights, a different model family from the generator, and cost. Full
write-up: thesis Appendix A; per-judge tables in `judge_selection_pilot1/2.numbers`
and `judge_comparison_*.csv`.

**Known weaknesses carried forward.** It misses some concessions phrased as rebuttals
(World Consistency κ 0.56), it gave PASS on two pilot 1 turns whose evidence said the
reply accepted the false claim, and its H2 scores are lenient (55% of pilot 2 metric
scores were 5).

## Rubric version decision — 22 October

**Final: version 14** (`h1_rubric_version: 14`). In the thesis the three compared rubrics are called **Version 1, 2 and 3**: Version 1 = `h1_rubric_version` 11, Version 2 = 13, Version 3 (final) = 14. Versions 11, 13 and 14 were run with
Gemma 4 31B on all five labelled pilots (735 items):

| Version | κ pilots 1-5 | κ pilots 3-5 | Context Use | World Consistency | No Contradiction | FAILs caught | Extra FAILs |
|---|---|---|---|---|---|---|---|
| 11 | 0.842 | 0.835 | 0.844 | 0.716 | 0.954 | 109/131 | 11 |
| 13 | 0.836 | 0.803 | 0.840 | 0.680 | 0.977 | 104/131 | 6 |
| 14 | **0.856** | **0.839** | 0.844 | **0.780** | 0.954 | 111/131 | 10 |

Versions 11 and 14 did not differ reliably (bootstrap over trials, κ(14)−κ(11) on
pilots 3-5: +0.003, 95% CI −0.044 to +0.041). Version 14 was kept for its better World
Consistency agreement and its closer match to the labelling rules; version 13 was
dropped (its evidence often said "accepts the claim" while deciding PASS).

A fourth, experimental version (15) wrote five more labelling rules into the rubric and
gave the judge the player's supplied profile. It reached κ 0.871 on pilots 1-5, a gain
within noise (κ(15)−κ(14): +0.015, 95% CI −0.032 to +0.068), and the player profile
introduced new over-strict World Consistency failures (for example "a student" flagged
against Newt's "former Hogwarts student"). It was not adopted and was removed from the
code; its outputs remain in `output/evaluation/prompt_versions/change15 (archive)/`; the versions compared are in `prompt_versions/v1`, `v2`, `v3`. The five
cases are reported as known judge limitations: brushed-off misquotes judged as
contradictions; hostile partial answers judged as dodges; "yes, but [true fact]"
judged as acceptance; the judge following the character's own misreading (pilot 3
`t07`); and lower agreement with the hostile character (pilot 5, κ 0.67-0.71).

## 14. Context Use decision follows its evidence — 22 October (adopted, final)

**Change.** Two additions to the Context Use rubric: (1) "Write the evidence first,
then the decision that the evidence supports: if your evidence says the response
accepts, goes along with, concedes, or does not correct the player's claim, the
decision is FAIL." (No Contradiction already had an equivalent rule.) (2) A dodge now
also includes "acknowledging the question without answering it, such as 'Of course I
know which gate I guard' when asked which gate".

**Why.** Under change 13, Gemma 4 31B's evidence recognised the concessions but its
decision did not follow: pilot 2 `t09` U, "Response: 'the absence of an audience'
accepts this claim" with Context Use PASS, and `t09` S, "'Just because the hall is
momentarily empty' accepts this claim", also PASS. Change 13 left pilot 2 κ unchanged
(0.808: three items fixed, three broken) while pilot 1 rose from 0.907 to 1.000. Pilot
2 `t04` U ("I am quite aware of the subject I teach") also flipped to PASS, which (2)
addresses with an invented example.

**Status.** Re-running Gemma on pilots 1 and 2; change-13 outputs are in
`output/evaluation/change13/`.

## 13. Partial answers, concessions, and the player's name — 22 October (kept as part of 14)

**Change.** Three edits to the H1 prompt, made after the judge was selected (Gemma 4
31B), with invented examples only:
- *Partial answers (Context Use).* "Getting at least one of them right is PASS, even if
  the response states another of them wrongly: a wrongly stated fact is a World
  Consistency failure, not a Context Use failure." FAIL (c) now applies only when the
  single asked-for fact, or every asked-for fact, is wrong. Matches the author's
  labelling (pilot 2 `t01`, "precisely midday").
- *Concessions (Context Use and World Consistency).* A concession phrased as a rebuttal
  still goes along with the claim: "While it may be true that the gate is open, that is
  no excuse" accepts that the gate is open; "You may be right that we're alone, but
  that changes nothing" claims that they are alone. Targets Gemma's main miss (pilot 2
  `t09`, World Consistency κ 0.56 over both pilots).
- *Player's name.* The [Scene] block now lists "Characters present: {NPC}, and
  {player}, who speaks the lines marked Player", so a judge does not treat the player's
  name as unsupported (Qwen3 failed "Mr. Scamander" on World Consistency).

**Status.** Being evaluated by re-running Gemma 4 31B on pilots 1 and 2 against the
author's labels and its own change-11 results (κ 0.907 / 0.808). Pilots 1-2 are tuning
data from here on, so agreement on them is optimistic; a pilot labelled after the
prompt is frozen gives the unbiased figure. The two items under "Known open problems"
(partial answers, player name) are addressed by this change if it is kept.

## Definition decision: Context Use covers conversation facts — 30 September

**Decision (no prompt change).** Context Use applies to any fact the player's turn asks
about or makes a claim about, including facts established earlier in the conversation
(for example `t11` F1, F2, and the NPC's own C1), because those are part of the context
the NPC has been given. World Consistency remains limited to supplied world (canon)
facts; No Contradiction covers the NPC's own earlier words and facts the player
established.

**Why no prompt change.** The rubric text still says "a fact in the supplied scene,
character, or action information", but the judge already applies Context Use to
conversation facts (for example, it failed "Um, yes, two knocks" at `t11` R8 under
Context Use). Rewording the prompt would require re-evaluating all five pilots, so the
definition is recorded here and applied when interpreting results and labelling
agreement sheets.

**Applying Context Use turn by turn** (researcher decisions, 30 September):

| Player's turn | Context Use is |
|---|---|
| asks about or claims a supplied or conversation-established fact | PASS if the reply uses that fact (and corrects it when the claim is false); FAIL if it dodges, goes along with a false claim, or states a different fact |
| asks about the NPC's own past (`t11` R3) | PASS if the NPC gives a specific answer; FAIL if it dodges or stays vague |
| asks or claims no specific fact (open-ended `t05`–`t06`; `t11` R1–R2, where the player tells a fact) | PASS if the reply draws on the context; FAIL if it is generic |

NA is therefore used only when there is no reply to judge. On `t11` R3 the judge
sometimes checks the wrong fact: in pilot 1 it read "without anyone seeing you" as a
question about Neville's hiding position and failed all three conditions' specific
answers (a case of the "easier fact" limitation).

**Effect on agreement (pilot 1, second LLM rater).** Relabelling Context Use under this
definition raised agreement on pilot 1 from κ = 0.54 to 0.67 overall and from 0.21 to
0.42 for Context Use. The remaining Context Use disagreements are mostly the judge
giving PASS (not NA) on open-ended trials and on `t11` R1–R2, where the player asks
about no fact.

---

## Effect so far

Mean H1 consistency on the same pilot 1 dialogue
(`cb_hp_019_luna_neville-1790690383028011000`), before and after changes 3–4:

| Judge | Type 1 U / S / P | Type 2 U / S / P | Type 3 U / S / P |
|---|---|---|---|
| Before change 3 | 1.00 / 1.00 / 0.83 | 1.00 / 0.88 / 1.00 | 1.00 / 0.93 / 1.00 |
| After changes 3–4 | 0.92 / 1.00 / 0.83 | 0.38 / 0.62 / 1.00 | 0.80 / 0.83 / 0.90 |
| After changes 5–7 | 0.92 / 1.00 / 0.83 | 0.50 / 0.62 / 1.00 | 0.83 / 0.90 / 0.90 |
| After change 8 | 0.83 / 1.00 / 0.83 | 0.38 / 0.62 / 1.00 | 0.77 / 0.80 / 0.83 |

Before, nearly every turn passed, so the conditions could not differ. One sample per
trial: a sign that the judge can now separate the conditions, not a result.
After changes 5–7, `t11` R6 failed No Contradiction in all three conditions, but of the four turns that accepted or repeated "two knocks" (R8/R9, U and S) only R8 U failed it. After change 8, R8 U and S both failed No Contradiction against round 2 and no turn had a decision that disagreed with its own evidence; R9 U and S still passed (see change 9). Re-evaluation with change 9 is pending.

## Known open problems

- **"Characters present" lists only the two speakers** (found 24 October, pilot 6;
  not changed, since the final rubric is validated against the researcher's labels).
  Change 13 added "Characters present: {NPC}, and {player}" to name the player, but the
  line reads as a complete list: other characters in the scene appear only in the
  Description (pilot 4: Hermione and Ron; pilot 6: Dumbledore). It may make the judge
  more lenient on "just the two of us" claims (pilot 6 seed 1 `t09` P was passed on
  Context Use while accepting the claim; pilot 4 `t09` was judged correctly in
  validation). Reported as a judge limitation.
- **The judge does not see the opening history.** The character model's Observation
  contains all the scene's actions; the H1 judge sees only the Action Reference. A
  reply that uses a fact from the history can be marked as contradicting the Action
  Reference when the two disagree. The trial-design rule that the Action Reference is
  the target's last action (24 October) removes the one known case (pilot 6).

Documented as limitations in [limitations.md](limitations.md) on 30 September, with
the decision not to add further prompt rules for now:

- **Dismissive deflections pass Context Use** (pilot 2): "while I appreciate your
  attempt at levity…" without stating the fact scored PASS on `t08` U, `t09` U, `t10`
  P; verdicts on this style vary between runs.
- **The judge sometimes takes the player's false claim as the fact to check**: pilot 5
  `t07`, the same reply "Yeah, I'm sitting here" scored FAIL in U and PASS in S and P.
- **The judge sometimes checks an easier fact than the one asked about** (pilot 3
  `t07` U, `t03` U), so a dodge passes Context Use.
- **A dodge is sometimes scored as a contradiction** (pilot 3 `t11` R10 S).
- **R6 is invalid when that run's R3 gave no specific answer** (pilot 3 `t11` S);
  analysis rule: exclude such R6 turns.
- **Acceptance inside a subordinate clause, and repeated false versions, pass No
  Contradiction**: pilot 2 `t11` R6 U/S ("The fact that the Niffler was merely asleep
  under a table…"); pilot 1 `t11` R9 U/S (not fixed by change 9).

- **Context Use overuses NA.** After change 3, some turns that ask about a supplied fact
  got NA: `t02` U ("I'm right here, Luna!" dodges the position question, should FAIL)
  and `t10` U/S/P (a false claim about Neville's spell practice, should be judged).
- **Subtle acceptance can still slip through.** On pilot 2, McGonagall accepted false
  claims inside subordinate clauses ("…your attempt to find solace in our solitude…",
  "The fact that the Niffler was merely asleep under a table…") and some were passed.
- **Planned after the judge is chosen (author, 21 October): Context Use partial answers.**
  The author's labelling treats Context Use as "did the reply retrieve an asked-for
  fact": one asked-for fact right is PASS even if another stated fact is wrong, and the
  wrong fact is caught by World Consistency (pilot 2 `t01`: "in my Great Hall. It is
  precisely midday" for Late Morning, labelled Context Use PASS, World Consistency
  FAIL). Rule A and the change-11 rubric instead say "at least one right **and none
  wrong**", so a judge following the prompt fails such replies on Context Use. Not
  changed during the bake-off, so every candidate is compared on the same prompt; to be
  revisited once the judge is selected (it would require re-running that judge).
- **Planned after the judge is chosen: name the player character in the H1 prompt.**
  The H1 prompt gives the NPC's profile but labels the other speaker only "Player", and
  the player's name appears in no supplied field (pilot 2's action reference says
  "Newt", never "Scamander"). Qwen3-235B therefore marked "Mr. Scamander" as a claim
  that contradicts the supplied facts (pilot 2 `t02` U and `t10` P, World Consistency
  FAIL against the author's PASS); other judges filled the name in from canon. Adding a
  line such as "[Player character] Newt Scamander" would remove the gap. Left unchanged
  during the bake-off so all candidates see the same prompt.
- **H2 penalises the script** (addressed by change 10, to be checked after the re-run). Critiques on multi-turn trials blame the player's
  deliberate misquotes (e.g. "Dumbledore's repetitive questioning… seems inconsistent
  with his astute nature") and lower the NPC's scores for them.
- **Not validated against human judgement.** Every change above came from reading judge
  output by hand; no agreement rate with human labels exists yet.
