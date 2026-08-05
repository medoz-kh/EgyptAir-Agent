from typing import List
from google.genai import types

class SlidingWindowStrategy:
    def __init__(self, window_size: int = 6):
        self.window_size = window_size

    def process(self, history: List[types.Content]) -> List[types.Content]:
        if not history:
            return []
        
        pruned = history[-self.window_size:] if len(history) > self.window_size else history[:]

        # If the first turn in the window is a orphaned tool response, include its preceding function_call
        if pruned and len(history) > len(pruned):
            first_part = pruned[0].parts[0] if pruned[0].parts else None
            if first_part and hasattr(first_part, "function_response") and first_part.function_response:
                # Move start back 1 step to include the function_call turn
                cut_index = len(history) - len(pruned) - 1
                pruned = history[cut_index:]

        return pruned