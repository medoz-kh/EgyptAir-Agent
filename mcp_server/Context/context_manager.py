from typing import List, Optional
from google import genai
from google.genai import types

# Import the 4 separate strategy classes
from .sliding_window import SlidingWindowStrategy
from .tool_mask import ObservationMaskingStrategy
from .summery import RecursiveSummarizationStrategy
from .zone_based import ZoneBasedPruningStrategy

class ContextWindowManager:
    def __init__(self, strategy_name: str = "zone_based", window_size: int = 6):
        self.strategy_name = strategy_name
        
        # Instantiate strategy objects
        self.sliding_window = SlidingWindowStrategy(window_size=window_size)
        self.observation_masking = ObservationMaskingStrategy()
        self.recursive_summarization = RecursiveSummarizationStrategy(window_size=window_size)
        self.zone_based = ZoneBasedPruningStrategy()

    async def process_context(
        self, 
        chat_history: List[types.Content], 
        genai_client: Optional[genai.Client] = None,
        model_id: str = "gemini-2.5-flash"
    ) -> List[types.Content]:
        
        if self.strategy_name == "sliding_window":
            return self.sliding_window.process(chat_history)

        elif self.strategy_name == "observation_masking":
            return self.observation_masking.process(chat_history)

        elif self.strategy_name == "recursive_summarization":
            return await self.recursive_summarization.process(chat_history, genai_client, model_id)

        elif self.strategy_name == "zone_based":
            return self.zone_based.process(chat_history)

        return chat_history