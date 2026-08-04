""""Purpose

Scratchpad is NOT conversation history.

It stores the agent's current working state.

Even if 100 conversation messages disappear, this object remains."""
from .models import ScratchpadState


class Scratchpad:
    """
    Stores the agent's temporary working state.

    Completely independent from the conversation transcript.
    """

    def __init__(self):
        self.state = ScratchpadState()

    def set_goal(self, goal: str):
        self.state.current_goal = goal

    def set_plan(self, plan: str):
        self.state.current_plan = plan

    def set_tool(self, tool: str):
        self.state.current_tool = tool

    def set_intermediate_state(self, state: str):
        self.state.intermediate_state = state

    def clear(self):
        self.state = ScratchpadState()

    def get_state(self):
        return self.state