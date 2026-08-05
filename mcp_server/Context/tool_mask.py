import copy
from typing import List
from google.genai import types

class ObservationMaskingStrategy:
    """
    Strategy 2: Observation & Tool-Output Masking
    Preserves dialogue history but strips out large tool outputs/JSON payloads
    from turns prior to the active round.
    """
    def process(self, history: List[types.Content]) -> List[types.Content]:
        if not history:
            return []

        masked_history = []
        for idx, item in enumerate(history):
            # Mask function call outputs older than the current active turn (last 2 items)
            if idx < len(history) - 2:
                item_copy = copy.deepcopy(item)
                for part in item_copy.parts:
                    if hasattr(part, "function_response") and part.function_response:
                        part.function_response.response = {
                            "status": "[TOOL OUTPUT MASKED: Payload truncated to preserve context]"
                        }
                masked_history.append(item_copy)
            else:
                masked_history.append(item)

        return masked_history