# Research contract

**Status:** agreed foundation for implementation  
**Date:** 2 August 2026  
**Scope revision:** 4 August 2026 — reduced to a CharacterBox-compatible minimum viable study  
**Priority-tier revision:** 30 August 2026 — §3's P tier description corrected to match `config/context_priorities.json` (current state and environment belief moved to Priority 3 / character guidance); see `docs/characterbox-provenance.md` for rationale  
**Priority-tier revision:** 29 September 2026 — §3's P policy replaced by the five-level `primary_five_level` (Observation moved to its own lowest tier; beliefs moved to Priority 4; conflict wording clarified); pilot-phase revision made after inspecting pilot output; see `docs/characterbox-provenance.md`  
**Working title:** *Generating Consistent LLM-Based NPC Dialogue by Structuring and Prioritising Game Context*

## 1. Purpose

This document fixes the initial meaning of the experiment before implementation. It prevents later engineering choices from silently changing the research question.

The contract may be revised after supervisor feedback or a pilot, but revisions must be dated and explained before the affected experiments are run.

## 2. Research question

> Under a fixed information set and context budget, how do unstructured, structured, and field-prioritised structured context representations affect the consistency and realism of LLM-generated NPC dialogue in dynamic game scenarios?

The study concerns **context representation at inference time**. It does not train a new foundation model.

## 3. Experimental conditions

The project uses one language model under three context conditions. These are not three different models.

### U — Unstructured context

All scenario facts are rendered as one flat context block. It contains no category headings, priority labels, priority ordering, or importance instructions.

The current player message remains a separate, identical user message in all conditions so that the model is always responding to the same input.

### S — Structured context

S preserves CharacterBox's English structured character-response context as the implementation baseline. Its fields are:

- Event;
- Time;
- Location;
- Description;
- Character Profile, Name, and Character Description;
- Position and Current State;
- Self Belief and Environment Belief;
- Recent Memory;
- Observation;
- Action Reference.

For identical inputs, S must produce the same fully formatted dialogue prompt and use the same response-generation path as CharacterBox. Facts have no explicit importance tier and the prompt does not tell the model that one field outranks another.

### P — Prioritised structured context

P contains the same factual information and 13 CharacterBox context fields as S. A reusable configuration groups those fields under ordered priority levels. Trial sidecars do not assign priorities and do not copy CharacterBox world values.

The current tiers (policy `primary_five_level`, revised 29 September 2026; see the change notes below) are:

1. **Current world constraints:** Time, Location, and Position. These must not be contradicted and override all other levels.
2. **World background:** Event and Description. These keep the response inside the fictional setting.
3. **Character guidance:** Name, Character Description, Action Reference, and Current State. These preserve role, personality, tone, and intended behaviour.
4. **Beliefs and memory:** Self Belief, Environment Belief, and Recent Memory. These are used only when relevant and must not override higher levels.
5. **Conversation input:** Observation. This is what was just said and done in the conversation, and the NPC must reply to it. Other characters' statements in it are their claims, not verified facts; if a claim conflicts with Priority 1–2, the facts win and the NPC may correct it in character.

The P prompt states that Priority 1 is the most important level and that, when two pieces of context conflict, the one with the smaller priority number is followed.

**Revision history.** The tier assignment has been revised twice, both before any final-study generation:

- *30 August 2026* (`primary_four_level`): `Current State` and `Environment Belief` moved from World Background to Character Guidance, and `Event`/`Observation` moved (with `Description`) into World Background. This followed a reasoned discussion of field semantics (frozen snapshot vs. live ground truth), not inspection of any trial's generated output.
- *29 September 2026* (`primary_five_level`): `Observation` moved from World Background to its own lowest level, Conversation Input; `Self Belief` and `Environment Belief` moved from Character Guidance to a renamed Beliefs and Memory level, because CharacterBox generates them from the character's own observation and memories, so they are the character's interpretation rather than ground truth (they are never generated in controlled play and are currently empty, so this has no practical effect on existing pilots); the Priority 1 instruction and the conflict rule were reworded for clarity. In controlled play, Observation carries the player's line, so it can contain false premises; ranking it beside Description put a false claim at the same level as the fact it contradicts. **Unlike the first revision, this one was prompted by inspecting pilot output**, so it is treated as a pilot-phase development revision under §10: the pilot scenes that motivated it are not final-study evidence.

Because Conversation Input's instruction says other characters' statements are claims rather than facts, and S carries no such statement, the P-versus-S contrast tests prioritisation together with that instruction (priority instructions are part of the intervention; see §5).

The primary five-level policy is declared in `config/context_priorities.json`. It assigns every supported field exactly once. The superseded `primary_four_level` policy is retained in the same file only so earlier pilot runs remain reproducible. The primary policy must be frozen before final-study generation; once frozen, it applies to every primary P trial and cannot be changed after inspecting a gold response or model output.

Arbitrary continuous weights such as `0.87` are excluded initially because their interpretation by an LLM and their assignment rationale would be unclear. The first implementation uses interpretable ordinal tiers.

## 4. What remains equal

For a paired trial, all three conditions must share:

- one canonical scenario record;
- the same context fields, values, validity, and NPC-visible information;
- the same NPC profile;
- the same scene, position, and current-state values;
- the same observation/player input and action reference;
- the same self-belief and environment-belief values, when used;
- the same current player message;
- the same exact dialogue history and selected memories, when introduced;
- the same model provider, model revision, and endpoint;
- the same decoding settings, including temperature, top-p, output limit, and seed where supported;
- the same context-window limit and output budget.

The prompt token counts may differ because headings and priority labels require tokens. All counts will be logged, initial scenarios will fit without truncation, and no condition will receive additional semantic facts to fill or equalise length.

## 5. Information-equivalence rule

Each renderer must return both its prompt text and a machine-readable trace of the 13 canonical field names and the source values it included. Actual world values are read from the CharacterBox-compatible dataset and character inputs, not copied into the trial sidecar or priority configuration. Evaluation cases may reference exact source fields without becoming prompt inputs themselves.

Before a trial is accepted:

```text
fields-and-values(U) = fields-and-values(S) = fields-and-values(P)
```

This equality concerns semantic context values. Structural labels, field grouping, priority instructions, and priority ordering are the intended intervention and therefore differ by condition.

Retrieval or filtering that removes facts is not part of the primary three-condition experiment. If studied later, it will be a separately named ablation.

## 6. Planned comparisons

### Primary comparison

**P versus S:** the additional effect of explicit prioritisation after structure is already present.

### Secondary comparisons

- **S versus U:** the effect of categorical structure.
- **P versus U:** the total effect of the proposed pipeline relative to the flat baseline.

These are planned contrasts. The study is not a competition among three independently designed agent systems.

## 7. Hypotheses

### H1 — Game-context consistency

NPC dialogue generated under P will have higher game-context consistency than dialogue generated under S and U. The expected ordering is `P > S > U`.

### H2 — Perceived realism

NPC dialogue generated under P will receive higher blinded realism ratings than dialogue generated under S and U, without sacrificing naturalness through excessive rule repetition.

### Exploratory extension — Long-term consistency

If time and proposal requirements permit a short scripted multi-turn experiment, dialogue generated under P is expected to exhibit fewer new contradictions than dialogue generated under S and U. This extension is not required before the controlled single-turn study is operational.

Null results and negative effects remain valid outcomes. In particular, explicit priorities could make responses rigid or cause lower-priority character details to be ignored.

## 8. Outcome measures

### Primary objective measures

Where supported by the minimal sidecar evaluation references, report these separately:

- **fact correctness:** claims agree with authoritative world facts;
- **knowledge-boundary adherence:** the NPC does not reveal or rely on facts it does not know;
- **contradiction count/rate:** response claims do not conflict with supplied facts or earlier committed dialogue;
- **required-fact use:** facts necessary to answer a targeted player question are used correctly.

State consistency may be reported for deliberately annotated questions. Physical action feasibility is excluded because controlled interaction turns and generated responses are dialogue-only.

A composite consistency score may be reported only in addition to—not instead of—the individual measures.

### Secondary subjective measures

Use condition-blind human ratings for:

- character fidelity;
- coherence;
- naturalness;
- relevance;
- adaptability;
- overall realism/immersion.

An LLM judge may assist later, but it cannot be treated as unquestioned ground truth for factual or knowledge-boundary metrics.

### Optional scripted multi-turn measures

- each objective metric by turn number;
- first turn containing a contradiction;
- cumulative contradiction count;
- change in consistency with turn depth;
- correction or persistence after the player introduces a false claim.

## 9. Experimental unit and sampling

The initial experimental unit is one **scenario–player-dialogue–NPC-dialogue** trial rendered in all three conditions. A player turn identifies the scene character controlled by the human and contains one fixed, non-empty line of dialogue; the sidecar separately identifies the sole target NPC. Controlled interaction does not accept player physical actions or generate NPC physical actions. The source Action Reference remains fixed context in every condition and guides dialogue generation without becoming an interaction action.

The final study uses two data sources: selected, manually verified CharacterBox-generated scenes and scenarios from the researcher's original fictional setting. Both use the unchanged CharacterBox scene/character/action schema plus minimal research sidecars. Every scenario–player-turn combination is rendered under all three U/S/P conditions. Dataset source is recorded for every trial, and results are reported separately by source before any combined analysis. The final study should use as many controlled scenarios, NPC roles, context lengths, and player turns as the available time permits. Repeated stochastic generations may be required for each cell.

CharacterBox scenes are evaluated against the supplied, manually verified scene record rather than assumed franchise canon. Their results may be affected by pretrained character knowledge. Original-story scenarios provide a complementary low-contamination test of context grounding.

## 10. Priority assignment guardrails

The primary intervention assigns priorities by CharacterBox context field, not by individual fact or trial. Its five-level policy is global, inspectable, validated, and frozen before response generation. A field cannot appear at multiple levels or be omitted from a policy.

Priority must not derive from the reference response wording, post-generation inspection, a target answer label, or a scenario-specific promotion made only because the tested question requires that field.

Priority labels, instructions, grouping, and ordering are treated as one prioritisation mechanism. Alternative policies with additional levels or one field per level are possible future ablations, but none is part of the initial primary experiment. Retrieval and filtering remain separate possible ablations because they change which information is supplied.

## 11. Scope boundaries

### In scope

- inference-time context representation;
- explicit ordinal field-group priority within CharacterBox-compatible context;
- NPC knowledge visibility where required by targeted evaluation questions;
- controlled single-turn trials;
- dialogue-only controlled interaction, with the source Action Reference retained as context;
- a short scripted multi-turn extension only if time and proposal requirements permit;
- reproducible prompt, output, and evaluation logging;
- selective adaptation of CharacterBox's character-response infrastructure.

### Out of scope for the primary study

- training a foundation model;
- reproducing every published role-playing architecture;
- comparing every possible context category layout;
- autonomous multi-agent story generation as the main experiment;
- player or NPC physical actions within controlled interaction turns;
- an LLM narrator serving as unquestioned world truth;
- CharacterBox's full autonomous narrator, state-update, and memory-retrieval pipeline as a primary-study dependency;
- graphical game integration;
- multimodal perception;
- retrieval/filtering as part of the main priority intervention;
- treating CharacterBox-derived datasets as automatically redistributable, as canonical franchise ground truth, or as covered by the repository's MIT software licence;
- building a SimsConv adapter or integrating Character-LLM training/evaluation code;
- using SimsConv or Character-LLM as an additional study dataset within the minimum viable project.

## 12. Relationship to CharacterBox

CharacterBox is the anchor paper and sole implementation foundation. It demonstrates a complete structured role-playing pipeline with character profiles, scene context, beliefs, memory, actions, dialogue, narrator updates, and trajectory evaluation.

This study preserves CharacterBox's structured character-response prompt as S and tests an assumption CharacterBox does not ablate: whether that structure helps, and whether an explicit field-group hierarchy improves it further. U and P are thin renderers around the same CharacterBox response path.

The complete CharacterBox simulator is not copied into the minimum viable experiment because it generates beliefs, actions, narrator decisions, state changes, and retrieved memories. Those operations could give paired conditions different semantic inputs. When any such values are used, they are selected or generated once and frozen across U/S/P.

CharacterBox evaluation ideas such as knowledge accuracy, behavioral accuracy, personality, immersion, adaptability, and behavioral coherence may inform secondary metrics. They do not replace the objective game-grounding measures above.

SimsConv and Character-LLM remain related work only. Their code and datasets are not integrated into the primary pipeline.

## 13. Decision rule for implementation changes

Before adding a feature, ask:

1. Does it help construct U, S, or P?
2. Does it enforce information equivalence or another control variable?
3. Does it measure one of the declared outcomes?
4. Is it required to reproduce a controlled single- or multi-turn trial?
5. Does it preserve the CharacterBox S baseline or implement the declared U/P intervention with a testable, minimal difference?

If all answers are no, the feature is outside the current study unless this contract is explicitly revised. Features that duplicate CharacterBox functionality without supporting a declared control or intervention should also be excluded.

## 14. Step 1 completion test

Step 1 is complete because this document now specifies:

- one research question;
- three operationally distinct context conditions;
- one primary and two secondary planned comparisons;
- hypotheses and measurable outcomes;
- controlled variables and information-equivalence requirements;
- priority-assignment guardrails;
- scope boundaries and the relationship to CharacterBox.
