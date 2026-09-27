from __future__ import annotations

# Adapted from CharacterBox agents/human_player.py at commit 5c19141e.
# Original copyright (c) 2023 Lei Wang; MIT licensed.
# See docs/characterbox-provenance.md for modifications.

from datetime import datetime
from typing import Any, Dict, Optional, Tuple


from langchain.schema import BaseMemory
from langchain.prompts import PromptTemplate
from langchain_experimental.generative_agents import GenerativeAgent,GenerativeAgentMemory


from utils.character import SceneInfo

class HumanPlayer(GenerativeAgent):
    id: int
    """The agent's unique identifier"""

    # BEGIN RESEARCH EXTENSION: preserve source-data metadata.
    # Simulator.create_human_player() already passes this CharacterBox dataset
    # field. It is stored for role metadata only and is not added to prompts.
    gender: str
    # END RESEARCH EXTENSION: preserve source-data metadata.

    traits: str
    """The agent's traits"""

    position:str

    states: str

    scene: SceneInfo

    self_belief: str=""

    env_belief: str=""

    # BEGIN RESEARCH EXTENSION: dynamic simulator record compatibility.
    # Human terminal input is never a model call, so this remains empty while
    # allowing CharacterBox's dynamic save loop to inspect every agent uniformly.
    all_actions: list = []
    # END RESEARCH EXTENSION: dynamic simulator record compatibility.

    BUFFERSIZE = 10
    """The size of the agent's history buffer"""

    max_dialogue_token_limit: int = 2048
    """The maximum number of tokens to use in a dialogue"""

    memory: GenerativeAgentMemory
    """The memory module in Character."""


    def update_from_dict(self, data_dict: dict):
        for key, value in data_dict.items():
            setattr(self, key, value)

    def reset_agent(self):
        """
        Reset the agent attributes, including memory, watched_history and heared_history.
        """
        # Remove watched_history and heared_history
        self.watched_history = []
        self.heared_history = []

    def _generate_reaction(
        self, suffix: str, now: Optional[datetime] = None, **extra_kwargs
    ) -> str:
        """React to a given observation."""
        prompt = PromptTemplate.from_template(
            "Please act as {name} and respond using the tone, manner and vocabulary {name} would use.\n The context and {name}'s information is as follows:\n"
            +"Event: {event}\n"
            +"Time: {time}\n"
            +"Location: {location}\n"
            +"Description: {description}\n"
            +"Character Profile:\n"
            +"Name: {name}\n"
            +"Character Description: {character_description}\n"
            +"Position: {position}\n"
            +"Current Status: {states}\n"
            +"Self Belief: {self_belief}\n"
            +"Environment Belief: {env_belief}\n"
            +suffix
        )
        now = datetime.now() if now is None else now
        current_time_str = (
            datetime.now().strftime("%B %d, %Y, %I:%M %p")
            if now is None
            else now.strftime("%B %d, %Y, %I:%M %p")
        )
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
             **extra_kwargs
        )
        result = self.chain(prompt=prompt).invoke(input=kwargs)["text"].strip()
        return result

    # BEGIN RESEARCH MODIFICATION: CharacterBox simulator compatibility.
    # Simulator.one_step() supplies observation, plot, and time and expects a
    # (text, detail) pair. The upstream HumanPlayer accepts no arguments and
    # returns text alone, so its intended play_role path cannot unpack results.
    # Human input remains direct and never enters an LLM prompt.
    def generate_dialogue(
        self,
        observation,
        plot,
        now,
    ) -> Tuple[str, Dict[str, str]]:
        """Read and record one line of human-controlled dialogue."""
        response = input("Enter your dialogue: ")
        return response, {"text": response, "source": "human"}

    def take_action(
        self,
        observation,
        plot,
        now,
    ) -> Tuple[str, Dict[str, str]]:
        """Read and record one human-controlled physical action."""
        response = input("Enter your action: ")
        return response, {"text": response, "source": "human"}

    def take_reaction(
        self,
        observation,
        plot,
        now,
    ) -> Tuple[str, Dict[str, str]]:
        """Read and record a human reaction selected by dynamic Narrator flow."""
        response = input("Enter your reaction: ")
        return response, {"text": response, "source": "human"}
    # END RESEARCH MODIFICATION: CharacterBox simulator compatibility.
