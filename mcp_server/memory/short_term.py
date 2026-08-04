""""Purpose

Implements the rolling buffer.

Notice something important:

The router is not called every message.

It is only called when an old message leaves the buffer"""
from collections import deque

from .config import SHORT_TERM_MAX_SIZE
from .models import ConversationTurn
from .router import MemoryRouter


class ShortTermMemory:

    """
    Rolling conversation buffer.

    Overflow triggers routing.
    """

    def __init__(self, max_size=SHORT_TERM_MAX_SIZE):

        self.max_size = max_size

        self.buffer = deque()

        self.router = MemoryRouter()

    def add_turn(self, turn: ConversationTurn):

        if len(self.buffer) >= self.max_size:

            oldest = self.buffer.popleft()

            self.router.route(oldest)

        self.buffer.append(turn)

    def get_history(self):

        return list(self.buffer)

    def clear(self):

        self.buffer.clear()

    def size(self):

        return len(self.buffer)