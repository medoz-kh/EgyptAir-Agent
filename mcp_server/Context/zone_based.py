import copy
from typing import List
from google.genai import types

class ZoneBasedPruningStrategy:
    def process(self, history: List[types.Content]) -> List[types.Content]:
        if not history:
            return []

        total = len(history)
        pruned_history = []

        for idx, item in enumerate(history):
            dist = total - 1 - idx  # Distance from latest turn

            if dist < 2:
                # Zone 1 (Newest): Keep intact
                pruned_history.append(item)
            elif dist < 5:
                # Zone 2: Mask tool outputs without deleting turns
                item_copy = copy.deepcopy(item)
                for part in item_copy.parts:
                    if hasattr(part, "function_response") and part.function_response:
                        part.function_response.response = {"status": "[Zone 2: Masked Tool Output]"}
                pruned_history.append(item_copy)
            else:
                # Zone 3 & 4: Drop old tool calls/responses completely in pairs
                is_tool_call = any(hasattr(p, "function_call") and p.function_call for p in item.parts)
                is_tool_resp = any(hasattr(p, "function_response") and p.function_response for p in item.parts)
                
                # Keep regular user/model text dialogue turns; drop old tool execution turns
                if not (is_tool_call or is_tool_resp):
                    pruned_history.append(item)

        return pruned_history