from pydantic import BaseModel


class CharacterInfo(BaseModel):
    id: int
    name: str
    # BEGIN RESEARCH EXTENSION: preserve an existing CharacterBox data field.
    # The upstream model silently discards gender even though every character
    # record supplies it and Simulator.create_human_player() later reads it.
    # __str__ intentionally remains unchanged so prompts do not gain a field.
    gender: str
    # END RESEARCH EXTENSION: preserve an existing CharacterBox data field.
    position: str
    states: str
    description: str

    def __str__(self):
        return f'Name: {self.name}\nPosition: {self.position}\nStates: {self.states}\nDescription: {self.description}'


class SceneInfo(BaseModel):
    id: int
    event: str
    time: str
    location: str
    description: str
    plot: str = ""

    def __str__(self):
        return f'Event: {self.event}\nTime: {self.time}\nLocation: {self.location}\nDescription: {self.description}'
