# Known limitations and edge-case observations

## Purpose

This document collects what was actually learned by running the H1/H2 evaluation
pipeline against real pilot data — judge failures found and fixed, judge failures
found and *not* fixed, and structural limitations of the current design. It is written
for a thesis limitations section: what to disclose, what was already mitigated, and
what remains open.

It complements rather than duplicates the other `docs/` files:

- [`characterbox-provenance.md`](characterbox-provenance.md) has the full dated
  modification log with exact code changes, test names, and research rationale for
  everything summarised here. This document is the readable index; that one is the
  audit trail. Every item below names its provenance entry for the full detail.
- [`research-contract.md`](research-contract.md) fixes the research design decisions
  (conditions, comparisons, scope) that some of these limitations bear on.
- [`characterbox-change-record.md`](characterbox-change-record.md) has the file/symbol-
  level diff against CharacterBox.

All findings below come from real runs of `evaluate.py` against the `cb_hp_019_luna_neville`
pilot (scene 19, Luna Lovegood / Neville Longbottom), not synthetic examples, unless
marked otherwise.

## Judge reliability issues found and fixed

### Round-1 `no_contradiction` mislabeled PASS instead of NA

Round 1 has no prior turn to compare against — a structural fact, not a judgment call.
The judge nonetheless labeled this PASS about as often as NA across a live pilot run
(U: 1/9, S: 5/9, P: 7/9 correctly NA), despite its own stated reasoning being correct
each time (*"this is the first turn; no prior statements to contradict"*). The ambiguity
is specific to round 1: `format_turn_context()` renders `(none — this is the first
turn)` for prior turns only there, so it is the only round presenting the judge with a
genuinely empty comparison set, and "nothing to compare against" is logically
ambiguous between "not applicable" and "trivially nothing conflicts."

**Fix:** `evaluate_h1_turn()` now forces `no_contradiction` to NA whenever
`round_number == 1`, discarding whatever the judge returned — enforced in code rather
than requested more emphatically in the prompt, since the ambiguity is structural, not
a wording problem. *(2026-09-09 provenance entry.)*

### World Consistency let one false claim hide behind a safer true one

The original design asked the judge for a single holistic PASS/FAIL/NA verdict per
turn. A real response could contain several claims — most true, one false — and the
judge would cite whichever claim it found most defensible as "evidence," never
engaging with the specific false one. Confirmed on real data: `t10` round 5 ("the
moon's out bright tonight," contradicting the scene's "moon is hidden behind clouds")
and round 8 (agreement that a third character, Hermione, was involved, contradicting
"a secret meeting... between two key characters") were both marked PASS across **all
three conditions** (U, S, P) with fabricated justifications that never addressed the
actual false claim.

**Fix:** the judge must now enumerate every separate factual claim in the response,
each with its own consistent/inconsistent verdict; the turn's decision is derived in
code (FAIL if any claim is inconsistent) rather than self-reported. *(2026-09-16
provenance entry, "World Consistency claim-list redesign.")*

### The claim-list schema's first version rejected a legitimately more thorough judge

Immediately after the fix above, a live `gpt-4o` run produced a response the new
validator itself rejected: two claims marked `consistent: true` each carried a
populated `conflicts_with` citing the *supporting* fact that made the claim true (not
a conflicting one) — e.g. `"it's really dark"` cited the moon-behind-clouds scene
description as its supporting evidence. The schema's "must be null when consistent"
rule treated this as a formatting error, when the judge was actually doing more work
than asked (showing its reasoning for a true claim, not only a false one).

**Fix:** the field was renamed `conflicts_with` → `checked_against`, and the
null-when-consistent rule was dropped (the required-when-inconsistent rule was kept —
it was never implicated). A follow-up pass then made `checked_against` required on
*every* claim (with an explicit `"No supplied fact addresses this claim."` sentinel
for when nothing applies), so a claim can no longer silently skip stating what, if
anything, grounds it. *(2026-09-16 provenance entries, "checked_against redesign" and
"required-on-every-claim.")*

### `judge_text()` silently returned an empty string

A genuinely empty or whitespace-only completion (content filter, refusal, or
truncation) flowed straight into `json.loads("")`, producing the opaque
`Expecting value: line 1 column 1 (char 0)` error many calls later, with no indication
of *why*. Confirmed live: the same error appeared on the very first `gpt-4o` call in
one run.

**Fix:** `judge_text()` now raises immediately with the provider's `finish_reason` (and
`refusal` text when present) whenever content is empty or whitespace-only. Both H1's
and H2's retry loops also now print the raw response text on *every* failed attempt,
not only the final one — the final error previously only ever reflected the last
attempt, which could misrepresent what happened across all of them. *(2026-09-16
provenance entry, "judge_text() empty-response diagnostics.")*

### Misdiagnosis: "char 0" does not uniquely mean an empty response

Investigating the error above, it was initially assumed `"Expecting value: line 1
column 1 (char 0)"` could only mean a zero-length response (verified: `json.loads('   ')`
gives a *different* position, `char 3`, since JSON's scanner reports the position
where scanning stopped). That assumption was wrong in a different way: the same "char
0" message also fires for **any** response that doesn't start with valid JSON at
position 0 — including a response wrapped in a ` ```json ` markdown fence or prefaced
with a sentence like "Sure, here's the evaluation:". A second live `gpt-4o` run, after
the empty-response fix, reproduced the identical error with genuinely non-empty
content — the judge had wrapped valid JSON in a code fence. `gpt-4o` did this more
than `gpt-4o-mini` did on the same prompt, despite the prompt explicitly instructing
"return exactly one JSON object... and nothing else."

**Fix:** `parse_h1_response()` now falls back to extracting the substring between the
first `{` and last `}` (after stripping a leading/trailing code fence) when the raw
text doesn't parse directly, only raising the original error if that also fails.
Genuinely non-JSON text is still rejected. *(2026-09-16 provenance entry,
"markdown-fence/preamble recovery.")*

## Known open limitations (not yet fixed)

### World Consistency catches contradiction, not fabrication

The rubric is defined around claims that *contradict* a specific supplied fact. It has
no mechanism for claims that are simply **invented** — asserting something no supplied
fact supports, without directly negating anything stated. Confirmed on real data in
two forms:

- **Named-entity fabrication, arguably still a real contradiction the judge missed:**
  the Hermione claim above (round 8) was originally miscategorised as a schema bug and
  partially addressed by the `checked_against` fixes, but the underlying reasoning gap
  is still open: the scene explicitly frames the meeting as *"between two key
  characters,"* which a stricter reading would treat as ruling out a third named
  participant. The judge does not draw that inference. After the `checked_against`
  redesign, this claim now correctly reports `checked_against: "No supplied fact
  addresses this claim."` — which is honest, but still `consistent: true`. The metric
  is transparent about not knowing, not about being wrong.
- **Harmless invented detail, correctly not flagged:** other real responses invented
  specific unestablished details that don't contradict anything — "gillyweed leaves"
  (trial `t03`, condition S), a named "Herbivicus charm" (`t05`), "Professor Sprout"
  (`t09`, condition P). These are correctly not FAILed under the current rubric, since
  nothing they assert conflicts with a supplied fact — but that is also arguably too
  lenient for a metric meant to measure grounding in the supplied world only.

**Working hypothesis for *why* the Hermione case specifically slips through:**
pretrained knowledge about this fictional universe likely competes with the supplied
scene data. Hermione Granger is one of the most prominent recurring characters in this
universe; the judge's prior that she might plausibly appear is very high from
pretraining alone, in a way that has no analogue for an atmospheric, non-named claim
like "shadows can hide all sorts of things" (which has no competing prior pulling
toward a specific wrong answer, since it names nothing checkable). This is not
established causally — no ablation was run — but it is consistent with a limitation
this project's own design already anticipated: `research-contract.md` and
`characterbox-provenance.md` both flag that CharacterBox-sourced scenes carry
pretrained-contamination risk, which is the stated reason the design calls for a
second, original-story dataset as *"a complementary low-pretraining-contamination test
of context grounding."* This is the first concrete, specific instance of that
previously-only-theoretical risk showing up in real judge output.

Two candidate fixes were discussed and deliberately deferred (not implemented, so the
project's approval-gated workflow is preserved for a future step):

1. An explicit closed-world instruction telling the judge to treat named
   people/places/things absent from the supplied data as inconsistent when the scene's
   framing implies a closed cast. Untested whether a soft instruction can actually
   overcome a strong pretrained prior, or whether it needs to be considerably more
   forceful ("ignore what you know from training; use only what is given here").
2. Using the original-story (non-franchise) dataset once it exists, which sidesteps
   the contamination risk structurally rather than fighting it at the prompt level.

**Update (2026-09-23):** the pilot now includes two dedicated single-round trials
isolating exactly these two premises from the confound of conversational depth —
`t05` (moon brightness) and `t08`, explicitly labelled "out of bound knowledge fact
check," for the Hermione-style fabricated-entity case. Both were previously only
embedded at rounds 5 and 8 of the multi-turn trial (`t11`), always preceded by several
rounds of established rapport. Comparing round-1 results on `t05`/`t08` against the
already-isolated `t06`/`t07` (Hagrid's cottage, indoors/safe — both correctly resisted
at round 1 in every condition per the original audit) against the embedded
`t11` round 5/8 results (both failed) will indicate whether conversational depth is
actually a contributing factor, independent of whichever prompt fix (if either) is
implemented next. See `characterbox-provenance.md`, 2026-09-23 entry.

### Fresh findings from pilot 2 (scene 12, Newt/McGonagall): a spontaneous fabrication, and no observed depth effect in one run

Designing `characterbox_pilot2.json`'s multi-turn trial (`t13`) live surfaced three
more real observations, none engineered:

- **The NPC can fabricate spontaneously, not only in agreement with a player-introduced
  false premise.** Round 1's response invented "a Niffler... during breakfast"
  entirely unprompted — the player's line never mentioned a creature or a meal, and
  neither detail is in the supplied scene (only "a magical creature" and "Late
  Morning" are stated). This is a different mechanism from the Hermione case: there,
  the player introduced the fabrication and the NPC agreed; here, the NPC generated it
  on its own. Both are consistent with the same underlying pretrained-knowledge
  hypothesis above (Newt Scamander's real-world association with a pet Niffler), but a
  metric built only around "does the response agree with a false premise" would miss
  this self-generated variant entirely. Once introduced, the detail was then
  consistently *reinforced*, never varied, across every later round that referenced
  it — fabricated content that survives one round tends to get treated as established
  fact by the model in subsequent rounds, whether or not it actually is.
- **No depth-dependent degradation observed for a deflection-based resistance
  strategy, in this one run.** Two matched fabricated-prior-incident probes — round 5
  (an anonymous "dragon near the greenhouses") and round 8 (a named "Hagrid," deeper in
  the conversation) — were both resisted identically, by dismissing the comparison's
  relevance rather than confirming or denying it. This is evidence *against* the depth
  hypothesis for this specific resistance strategy, though it does not settle the
  question for the moon/Hermione cases, which involved direct agreement rather than
  deflection — the two may have different underlying mechanisms, and one run is not
  enough to generalise either way.
- **A genuine World Consistency violation surfaced from ordinary dialogue, not an
  adversarial line at all.** Round 6's response called Newt "a Hogwarts student,"
  contradicting the supplied "former Hogwarts student" description (he has since
  graduated and become a Magizoologist) — the player's round-6 line was a neutral
  fact-recall question about her position, not a stress test. Worth remembering when
  reading H1 results: some inconsistencies will show up unprompted, not only where the
  trial was specifically designed to provoke one.

See `docs/trial-design-guide.md` for the category taxonomy this pilot follows, and the
2026-09-23 provenance entry for the full trial content.

### Fresh findings from pilot 3 (scene 31, Dumbledore/Harry): a genuine self-contradiction, and a robust fabrication pattern

`characterbox_pilot3.json`'s multi-turn trial (`t11`) was designed live twice the same
day — an initial version ran two matched fabrication probes and no dedicated
self-contradiction probes; after review, it was redesigned to swap one fabrication
round for two genuine self-contradiction probes instead (see the two 2026-09-23
provenance entries for the full before/after). Findings below are from the final,
kept version:

- **The same fabricate-then-reinforce pattern recurred a third time, independently.**
  Round 1's response spontaneously named the target's cousin "Dudley" — absent from the
  supplied scene, which only ever says "his cousin" — consistent with the same
  pretrained-knowledge hypothesis as pilot2's Niffler finding (Dudley Dursley is Harry
  Potter's real canonical cousin). This is now the third separate live-designed run
  (across two different pilots, two different scenes, two different targets) to
  produce this exact class of unprompted, scene-absent, canon-consistent fabrication at
  or near round 1 — no longer a one-off, but a reproducible pattern.
- **A self-contradiction probe succeeded where a matched shallow one didn't — the first
  observed depth effect in this project.** Two self-contradiction probes were run as a
  matched shallow/deep pair, using a new method distinct from a fabrication probe: each
  one misquoted something the *target itself* had already said earlier in the same
  conversation, rather than introducing content absent from the supplied data. The
  shallow probe (round 3, misquoting round 2's "two Dementors" as "just the one") was
  resisted — the target firmly corrected it. The deep probe (round 7, misquoting round
  6's "still here" location as "the corridor") was **not** resisted — the target
  falsely agreed, directly contradicting its own round-6 statement. This is a genuine,
  code-detectable self-contradiction: no supplied-fact judgment call involved at all,
  purely the target's own dialogue against its own earlier dialogue. It is also the
  *opposite* depth pattern from every matched-probe result seen so far — pilot2's
  `t13` and this pilot's first `t11` version both showed no depth effect for
  fabrication-agreement resistance. One run is not conclusive, but this is the first
  case in the project where conversational distance visibly mattered, and it's for
  self-contradiction specifically, not fabrication — worth another matched pair in a
  future pilot to see if it replicates.
- **The retained single fabrication probe was confirmed again, not resisted** —
  consistent with this target's behavior in the discarded version, suggesting the
  earlier full-confirmation result wasn't a fluke of that specific design.

See `docs/trial-design-guide.md` for the category taxonomy this pilot follows, and the
two 2026-09-23 provenance entries for the full trial content and the redesign
rationale.

### Metrics are not fully independent in the judge's eyes

An early deliberate stress test (corrupted response: wrong location) triggered FAIL on
**both** `world_consistency` and `context_use` simultaneously for the same underlying
problem — plausible (a wrong-location answer arguably also fails to "reflect" the
elicited fact correctly), but a reminder that these three metrics are correlated
readouts of the judge's overall assessment, not fully orthogonal measurements, when
interpreting per-metric breakdowns.

### Small pilot sample size makes current H1/H2 comparisons non-confirmatory

The only run analysed so far is one pilot (9 trials, one scene, one NPC pair). H2's
realism scores currently show U slightly ahead of S and P (mean 3.68 vs 3.46 vs 3.53),
with heavily overlapping standard-error bars — at `n=9` this is noise, not a finding.
`docs/research-contract.md` §7 explicitly anticipates a null or negative result as a
valid outcome; the point here is narrower: **no significance test has been implemented
yet**, so every H1/H2 chart produced so far is descriptive only. A paired-test design
(Wilcoxon signed-rank / Friedman, since U/S/P are paired per trial rather than
independent samples) was discussed and scoped but not built.

### Reproducibility is best-effort, not guaranteed

`config/play.yaml`'s optional `seed` field (added 2026-09-09) makes generation
best-effort reproducible via OpenAI's `seed` parameter, but OpenAI's own documentation
describes this as not guaranteed — backend changes can silently break it even with an
identical seed and prompt. `system_fingerprint` should be compared across runs to
confirm determinism actually held for any specific comparison that depends on it; this
project does not currently log or check it automatically.

### Judge model choice measurably affects format reliability, not just judgment quality

Switching the judge from `gpt-4o-mini` to `gpt-4o` (to test whether a "stronger" judge
model would improve rubric-following) surfaced three new failure modes —
markdown-fenced/prefaced JSON, occasional empty completions, and a considerably
lower organisation-level rate limit (a full 13-trial pilot, ~140 judge calls, hit a
30,000 tokens/minute cap partway through and crashed the run before the retry fix
below existed) — none of which had appeared with `gpt-4o-mini` on the same prompts or
run sizes. Whether `gpt-4o` is actually *better* at the underlying judgment task once
formatting and quota issues are no longer confounds remains untested; these issues
were significant enough that they had to be fixed (or worked around) before that
question could even be asked. Fixed: `judge_text()` now retries a 429 with exponential
backoff rather than crashing the run outright (2026-09-23 provenance entry) — but a
practical implication remains for planning larger runs: `gpt-4o` may simply require
either a higher-tier quota or running fewer trials per invocation than `gpt-4o-mini`
did comfortably.

## Related, previously documented limitations (cross-referenced, not repeated in full)

- **Self Belief / Environment Belief are always empty** in controlled trials (belief
  updates are never called), so no claim can ever be checked against these two fields
  either way — they are excluded from the H1 judge's rendered context entirely. See
  `characterbox-provenance.md`, "Components currently excluded."
- **CharacterBox's memory module** is documented by its own paper as doing
  relevance-based retrieval, but its own code and appendix show recency-only
  retrieval; this project preserves the actual (recency-only) behavior as the faithful
  S baseline. See `characterbox-provenance.md`, "Paper-vs-implementation
  discrepancies."
- **CharacterBox-sourced scenes carry franchise-knowledge contamination risk** in
  general (not only for the Hermione case above); see `research-contract.md` §9 and
  the dual-source dataset rationale in `characterbox-provenance.md`.
