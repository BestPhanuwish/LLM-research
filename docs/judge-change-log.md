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
| Judge model | `gpt-4o` (`config/evaluate.yaml`) |
| Temperature / seed | 0 / 1 |
| H1 metrics | Context Use, World Consistency (claim list), No Contradiction |
| H2 metrics | CharacterBox's seven-metric critique-then-score judge (unchanged) |
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
- **H2 penalises the script.** Critiques on multi-turn trials blame the player's
  deliberate misquotes (e.g. "Dumbledore's repetitive questioning… seems inconsistent
  with his astute nature") and lower the NPC's scores for them.
- **Not validated against human judgement.** Every change above came from reading judge
  output by hand; no agreement rate with human labels exists yet.
