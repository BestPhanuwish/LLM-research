from __future__ import annotations

# Adapted from CharacterBox agents/character.py at commit 5c19141e.
# Original copyright (c) 2023 Lei Wang; MIT licensed.
# See docs/characterbox-provenance.md for modifications.

from datetime import datetime
from typing import Any, Dict, Optional, Tuple


from langchain.schema import BaseMemory
from langchain.prompts import PromptTemplate
from langchain_experimental.generative_agents import GenerativeAgent,GenerativeAgentMemory

import re
from utils.character import SceneInfo
import time


# BEGIN RESEARCH EXTENSION: no-op importance scoring for controlled trials.
# GenerativeAgentMemory.add_memory() unconditionally calls
# _score_memory_importance() (one extra model call) before checking
# reflection_threshold. At this project's importance_weight=0.1 and
# reflection_threshold=10, reflection cannot fire within any trial length
# this study runs (~100+ maximally-poignant turns would be required), and
# the importance score has no other consumer on the recency-only path that
# builds the Recent Memory field. Used only for controlled trials; dynamic
# play keeps the unmodified GenerativeAgentMemory. See
# docs/characterbox-provenance.md for the verification and rationale.
class NoScoreGenerativeAgentMemory(GenerativeAgentMemory):
    def _score_memory_importance(self, memory_content: str) -> float:
        return 0.0
# END RESEARCH EXTENSION: no-op importance scoring for controlled trials.


class Character(GenerativeAgent):
    id: int
    """The agent's unique identifier"""

    traits: str
    """The agent's traits"""

    position:str

    status=""

    states: str

    scene: SceneInfo

    self_belief: str=""

    env_belief: str=""

    BUFFERSIZE = 10
    """The size of the agent's history buffer"""

    max_dialogue_token_limit: int = 4096
    """The maximum number of tokens to use in a dialogue"""

    memory: GenerativeAgentMemory
    """The memory module in Character."""

    all_actions:list=[]

    def update_from_dict(self, data_dict: dict):
        for key, value in data_dict.items():
            setattr(self, key, value)

    # BEGIN RESEARCH EXTENSION: U/S/P prompt selection.
    # CharacterBox hard-codes the S prompt inside _generate_reaction(). This
    # helper retains that prompt verbatim for S and adds U/P renderings around
    # the same placeholders. No scene or character value is changed here.
    def _build_reaction_prompt(
        self,
        suffix: str,
        context_condition: str = "S",
        priority_policy=None,
    ):
        condition = context_condition.upper()
        if condition == "S":
            # CharacterBox baseline prompt: keep character-for-character.
            return PromptTemplate.from_template(
                "Please act as {name}  and respond using the tone, manner and vocabulary {name} would use.\n The context and {name}'s information is as follows:\n"
                +"Event: {event}\n"
                +"Time: {time}\n"
                +"Location: {location}\n"
                +"Description: {description}\n"
                +"Character Profile:\n"
                +"Name: {name}\n"
                +"Character Description: {character_description}\n"
                +"Position: {position}\n"
                +"Current State: {states}\n"
                +"Self Belief: {self_belief}\n"
                +"Environment Belief: {env_belief}\n"
                +"Recent Memory(Ordered in reverse chronological order): {most_recent_memories}\n"
                +"Observation: {observation}\n"
                +suffix
            )

        action_reference_line = "Action Reference: {plot}\n"
        if not suffix.startswith(action_reference_line):
            raise ValueError(
                "U/P context rendering is currently supported only for "
                "generate_dialogue()"
            )
        dialogue_instruction = suffix[len(action_reference_line):]

        if condition == "U":
            return PromptTemplate.from_template(
                "Please act as {name} and respond using the tone, manner and "
                "vocabulary {name} would use. Use the following context to "
                "produce one appropriate line of dialogue.\n"
                "{event}\n"
                "{time}\n"
                "{location}\n"
                "{description}\n"
                "{name}\n"
                "{character_description}\n"
                "{position}\n"
                "{states}\n"
                "{self_belief}\n"
                "{env_belief}\n"
                "{most_recent_memories}\n"
                "{observation}\n"
                "{plot}\n"
                + dialogue_instruction
            )

        if condition != "P":
            raise ValueError(
                f"Unknown context condition {context_condition!r}; expected U, S, or P"
            )
        if not isinstance(priority_policy, dict):
            raise ValueError("P requires one validated priority policy")

        field_templates = {
            "event": "Event: {event}",
            "time": "Time: {time}",
            "location": "Location: {location}",
            "description": "Description: {description}",
            "name": "Name: {name}",
            "character_description": (
                "Character Description: {character_description}"
            ),
            "position": "Position: {position}",
            "states": "Current State: {states}",
            "self_belief": "Self Belief: {self_belief}",
            "env_belief": "Environment Belief: {env_belief}",
            "recent_memory": "Recent Memory: {most_recent_memories}",
            "observation": "Observation: {observation}",
            "action_reference": "Action Reference: {plot}",
        }
        # A policy may supply its own conflict_rule; policies without one
        # (primary_four_level) keep the original wording so earlier P runs
        # remain reproducible.
        conflict_rule = priority_policy.get(
            "conflict_rule",
            "The context below is ordered from highest to lowest priority. "
            "Use all relevant context when it is compatible. If context "
            "conflicts, follow the lower priority number.",
        )
        prompt_parts = [
            "Please act as {name} and respond using the tone, manner and "
            "vocabulary {name} would use.",
            conflict_rule,
        ]
        assigned_fields = []
        for group in sorted(
            priority_policy.get("priorities", []),
            key=lambda item: item.get("priority", 0),
        ):
            number = group.get("priority")
            name = group.get("name")
            instruction = group.get("instruction")
            fields = group.get("fields", [])
            if not fields or any(field not in field_templates for field in fields):
                raise ValueError("P received an invalid or incomplete priority policy")
            assigned_fields.extend(fields)
            prompt_parts.append(f"Priority {number} — {name}")
            prompt_parts.append(f"Instruction: {instruction}")
            prompt_parts.extend(field_templates[field] for field in fields)
        if (
            set(assigned_fields) != set(field_templates)
            or len(assigned_fields) != len(set(assigned_fields))
        ):
            raise ValueError("P received an invalid or incomplete priority policy")
        prompt_parts.append(dialogue_instruction.rstrip("\n"))
        return PromptTemplate.from_template("\n".join(prompt_parts) + "\n")
    # END RESEARCH EXTENSION: U/S/P prompt selection.

    # BEGIN RESEARCH MODIFICATION: prompt-condition hook. The two optional
    # parameters and delegated prompt construction are absent from CharacterBox;
    # their defaults preserve its S behavior for every inherited caller.
    def _generate_reaction(
        self,
        observation,
        suffix: str,
        now: Optional[datetime] = None,
        verbose=False,
        context_condition="S",
        priority_policy=None,
        **extra_kwargs,
    ):
        """React to a given observation."""
        prompt = self._build_reaction_prompt(
            suffix,
            context_condition=context_condition,
            priority_policy=priority_policy,
        )
    # END RESEARCH MODIFICATION: prompt-condition hook.

        now = datetime.now() if now is None else now
        kwargs: Dict[str, Any] = dict(
            # source=self.scene.source,
            event=self.scene.event,
            time=self.scene.time,
            location=self.scene.location,
            description=self.scene.description,
            name=self.name,
            states=self.states,
            character_description=self.traits,
            position=self.position,
            self_belief=self.self_belief,
            env_belief=self.env_belief,
            observation=observation,
             **extra_kwargs
        )
        
        st=time.time()
        consumed_tokens = self.llm.get_num_tokens(prompt.format(most_recent_memories="", **kwargs))
        kwargs[self.memory.most_recent_memories_token_key] = consumed_tokens
        result = self.chain(prompt=prompt).invoke(input=kwargs)
        ed=time.time()
        duration=ed-st
        result['prompt']=prompt
        all_prompt=prompt.format(most_recent_memories=result['most_recent_memories'], **kwargs)
        self.all_actions.append({'character':self.name,'prompt':all_prompt,'response':result['text'].strip(),'duration':duration})
        if verbose:
            return result['text'].strip(),result
        else:
            return result['text'].strip()


    # BEGIN RESEARCH EXTENSION: optional condition/policy parameters. Existing
    # CharacterBox callers omit both and therefore continue to use exact S.
    def _clean_dialogue_response(self, response: str) -> str:
        """Return spoken dialogue without model-generated stage directions."""
        # BEGIN RESEARCH MODIFICATION: robust shared dialogue extraction.
        # CharacterBox keeps only the first line and then splits on every colon.
        # A multiline response beginning with an italic stage direction can
        # therefore collapse to "*". Prefer all explicitly quoted speech; retain
        # the original first-content-line approach as a fallback for unquoted
        # responses. This one cleanup path is shared by U/S/P and dynamic play.
        # Opening and closing marks may be mixed (a straight " opening and a
        # curly ” closing, or the reverse), so any opening mark pairs with any
        # closing mark.
        quoted_parts = [
            " ".join(quote.split())
            for quote in re.findall(
                r"[“\"]([^“”\"]+)[”\"]",
                response,
                flags=re.DOTALL,
            )
        ]
        if quoted_parts:
            return " ".join(quoted_parts).strip()

        lines = [line.strip() for line in response.splitlines() if line.strip()]
        spoken_lines = [
            line
            for line in lines
            if not (line.startswith("*") and line.endswith("*"))
        ]
        selected = spoken_lines[0] if spoken_lines else (lines[0] if lines else "")
        selected = re.sub(
            rf"^\s*{re.escape(self.name)}\s*:\s*",
            "",
            selected,
            count=1,
            flags=re.IGNORECASE,
        )
        return selected.strip().strip('"\u201c\u201d')
        # END RESEARCH MODIFICATION: robust shared dialogue extraction.

    def generate_dialogue(
        self,
        observation,
        plot,
        now,
        context_condition="S",
        priority_policy=None,
        remember=True,
    ):
        """Generate one line of character dialogue and, unless remember=False,
        save it to memory. The controlled loop passes remember=False so it can
        save the player's line first, keeping memory in chronological order."""
        call_to_action_template = (
            "Action Reference: {plot}\n"
            "Based on the provided character profile, current action reference, and observation, describe a line {name} might say at this moment. Consider {name}'s personality, observation, the characters in the story, and recent memories to determine the tone and content of the dialogue. The line {name} says at this moment should align with the character profile and behavioral traits, ensuring it is closely related to the current environment and observation, and distinct from the content in recent memories.\n"
        )
        response,detail = self._generate_reaction(
            observation=observation,
            suffix=call_to_action_template,
            now=now,
            plot=plot,
            verbose=True,
            context_condition=context_condition,
            priority_policy=priority_policy,
        )
        response = self._clean_dialogue_response(response)
        if remember:
            self.memory.save_context(
                {},
                {
                    self.memory.add_memory_key: f"{self.name}: {response}",
                    self.memory.now_key: now,
                },
            )
        return response,detail
    # END RESEARCH EXTENSION: optional condition/policy parameters.

    def take_action(self,observation,plot, now):
        """Generate and remember one visible physical action."""
        call_to_action_template = (
            "Action Reference: {plot}\n"
            "Following the guidance of the current action reference, describe {name}'s next specific action based on their profile, recent memories, and the details of the current scene. This action should revolve around the 'Action Reference' and 'Observation', further reflecting {name}'s character traits, current situation, and physical environment.\n"
            "NOTE:\n"
            "1. The next specific action must be logical within the context of the scene and be a clear, observable behavior\n"
            "2. The next action must differ from any actions described in recent memories.\n"
            "3. Avoid including any dialogue or thought processes in the next specific action; focus on a physical action {name} is about to take. This action should be easily observable by anyone in the scene.\n"
            "4. This action must significantly advance the story or character arc and be true to {name}'s character and current circumstances. The action should be plausible within the established environment and narrative, driving actual progress in the scene or {name}'s objectives.\n"
        )
        response,detail = self._generate_reaction(observation,call_to_action_template, now,plot=plot,verbose=True)
        response = response.strip().split("\n")[0]
        response=response.split(":")[-1]
        self.memory.save_context(
            {},
            {
                self.memory.add_memory_key: f"{self.name}:{response}",
                self.memory.now_key: now,
            },
        )
        return response,detail
    
    def take_reaction(self,observation,plot, now):
        """Generate one visible physical reaction to an observation."""
        call_to_action_template = (
            "Based on {name}'s 'Observation' in the current scene, describe a specific action {name} takes in response to what they see. This action should reflect {name}'s personality, position, and state, logically align with the events {name} observes, and consider how others' actions influence the response. Focus on a visible, external action, avoiding dialogue or internal thoughts. The action must be directly relevant to the current environment and observable by others.\n"
            "NOTE: 1. The action is a reaction to {name}'s immediate surroundings or the events they observe. 2. Recent memories are events that have already occurred and should not be repeated. 3. The action should be a response to the content in the 'Observation'.\n"
        )
        response,detail = self._generate_reaction(observation,call_to_action_template, now,plot=plot,verbose=True)
        
        response = response.strip().split("\n")[0]
        return response,detail


    def update_self_belief(self,observation, now: datetime):
        """Update the agent's self-belief."""
        call_to_action_template = (
    
            "Assuming you are now {name}, based on your understanding of this character, the environmental context, observation and recent memories,"
        " please describe from the first-person perspective your self-belief as this character. Focus on your identity, your current location, "
        "your state (emotional, physical, and psychological), and your goals. Reflect briefly on how this character might react, plan, and act based on their beliefs, desires, and intentions.\n"
        "1. Belief: As {name}, what do I believe about my current situation and condition? Briefly describe your perception of yourself, "
        "highlighting key physical aspects like any injuries, your sense of movement (e.g., running, jumping), your energy levels, and any changes in physical abilities. Consider how these "
        "details influence your identity and role within the story.\n"
        "2. Desire: What are my goals? Summarize your short-term and long-term objectives, including the strategies "
        "and actions you plan to implement to achieve these goals.\n"
        "3. Intention: How do I plan to act? Outline specific actions you intend to take in pursuit of your goals, noting "
        "any potential challenges and your strategies for overcoming them.\n"
        "Provide concise responses shortly in a few short sentences, focusing on your self-belief, understanding of the current situation, and future action plan.\n"
        )
        response = self._generate_reaction(observation,call_to_action_template, now)
        self.self_belief = response

        return response

    def update_env_belief(self, observation, other_characters, now: datetime):
        """Update the agent's belief about the environment."""

        env_belief_template = (
            "Other Characters: {other_characters}\n"
            "Please act as {name}, given the information about other characters, the environment, and your own character's profile, "
            "please describe your belief about the environment in the first person. This includes your perception "
            "of other characters, your understanding of the scene, and how these elements influence your actions and decisions.\n"
            "1. Perception of Others: Based on the interactions and information available, how do I perceive other characters? "
            "Describe your understanding of their intentions, relationships, and potential influence on your character.\n"
            "2. Understanding of the Scene: What is my understanding of the current scene and its significance to my character? "
            "Detail the environmental factors, challenges, or opportunities present.\n"
            "Please provide a consice overview of your environment belief shortly, focusing on the interpersonal and environmental aspects that shape your character's perspective and future actions.\n"
        )
        response = self._generate_reaction(observation,env_belief_template, now, other_characters=other_characters)
        self.env_belief = response

        return response

    def update_character(self,  observation, now) -> Tuple[str|None, str|None]:

        call_to_action_template = (
            "Given the character's rich backstory, obsrvation recent and recent memories within the scene, distill this information into a succinct summary of their present location and condition. Focus on how their interactions, especially the dynamic interplay with other characters, shape their current circumstances. This interaction's effects should be evident in the nuanced portrayal of their condition and placement within the scene. Utilize this structured format for your depiction:\n\n"
            "Position: [Specify {name}'s exact position, incorporating environmental details or spatial context to enhance the scene's visuality.]\n"
            "State: [Describe {name}'s current state, weaving together emotional nuances, physical readiness, and the influence of recent encounters or developments. Highlight how these elements contribute to their overall disposition and readiness for what lies ahead.]"
        )
        response = self._generate_reaction(observation,call_to_action_template, now)
        
        robust_position_value_pattern = r"Position:\s*(.+)"
        robust_state_value_pattern = r"State:\s*(.+)"

        # Extracting location and state using the defined regular expressions
        position_value_match = re.search(robust_position_value_pattern, response, re.IGNORECASE)
        state_value_match = re.search(robust_state_value_pattern, response, re.IGNORECASE)
        
        position_value = position_value_match.group(1).strip() if position_value_match else None
        state_value = state_value_match.group(1).strip() if state_value_match else None
        if position_value:
            self.position = position_value
        if state_value:
            self.states = state_value
        return position_value, state_value

    def generate_synopsis(self,actions,sequence,history, now) -> str:

        prompt=PromptTemplate.from_template(
            "As the screenwriter of a key scene in an art novel, design the current plot for each character to drive the plot forward."
            "Historical Plot: {history}\n"
            "Historical Actions: {actions}\n"
            "Character Action Sequence: {sequence}\n"
            "At this crucial moment, each character is prepared to take action, influenced by their unique motivations and the immediate scene. Your task is to design the current plot for each character based on the historical plot and actions to indicate the characters' next actions, reflecting their current motivations and the dynamics of the scene. Focus on specific actions, such as attacks, evasions, the use of specific skills, or any other visible behaviors that can advance the plot and reveal the characters' intentions. Avoid broad strategies or long-term goals. This action should be a direct response to the current situation, showcasing a clear and engaging development in the story.\n"
            "NOTE:\n"
            "1. To advance the plot, the characters' next actions must build on the previous actions to progress the plot, rather than repeat or duplicate previous actions.\n"
            "2. Each character's actions and intentions should only involve themselves and not impact other characters.\n"
            "3. Output Format: [Character Name]: [Brief description of the character's current plot and upcoming actions].\n"
            "4. Output only the plot in the specified format, one character per line, without any additional content.\n"
            "5. The current plot must advance the plot compared to the historical plot and actions, avoiding repetition or similarity to the past.\n"
            "6. Focus on describing the current plot and character actions, without the need for dialogue or internal monologues."
            "Current Plot:\n"
        )
       
        result = self.chain(prompt=prompt).invoke(input={"actions":actions,"sequence":sequence,"history":history})
        
        pattern = r"([^:\n]+):\s*([\s\S]+?)(?=\n|$)"
        result['prompt']=prompt
        response=result["text"].strip().split("\n\n")[0]
        print(response)
        matches = re.findall(pattern, response)
        synopsis={}
        for match in matches:
            name=match[0].strip(" []'\"")
            plot=match[1].strip(" []'\"")
            synopsis[name] = plot
        
        return synopsis
