from .models import ConversationTurn
from .short_term import ShortTermMemory
from .scratchpad import Scratchpad
from .consolidation import MemoryConsolidator


class MemoryManager:
    """
    Main entry point for the memory subsystem.

    The rest of the project interacts ONLY with this class.
    """

    def __init__(self):

        self.short_term = ShortTermMemory()

        self.scratchpad = Scratchpad()

        self.consolidator = MemoryConsolidator()

    # -------------------------------------------------

    def add_turn(
        self,
        role: str,
        content: str
    ):

        turn = ConversationTurn(
            role=role,
            content=content
        )

        self.short_term.add_turn(turn)

    # -------------------------------------------------

    def get_conversation(self):

        return self.short_term.get_history()

    # -------------------------------------------------

    def update_goal(self, goal):

        self.scratchpad.set_goal(goal)

    def update_plan(self, plan):

        self.scratchpad.set_plan(plan)

    def update_tool(self, tool):

        self.scratchpad.set_tool(tool)

    def update_intermediate_state(self, state):

        self.scratchpad.set_intermediate_state(state)

    # -------------------------------------------------

    def get_scratchpad(self):

        return self.scratchpad.get_state()

    # -------------------------------------------------

    def consolidate(self):

        self.consolidator.consolidate()