""""Purpose

The router is intentionally simple.

It only decides:

Forget

or

Promote

It NEVER writes to semantic memory"""
from .episodic_store import EpisodicStore
from .logger import RoutingLogger
from .models import Episode
from .models import RoutingDecision


class MemoryRouter:

    def __init__(self):

        self.logger = RoutingLogger()

        self.episodic_store = EpisodicStore()

    def route(
        self,
        conversation_turn
    ) -> RoutingDecision:

        text = conversation_turn.content.lower()

        keywords = [

            "prefer",

            "remember",

            "important",

            "always",

            "never",

            "manager",

            "policy",

            "compensation",

            "refund",

            "voucher"
        ]

        promote = any(word in text for word in keywords)

        if not promote:

            decision = RoutingDecision(
                reasoning="No long-term value detected.",
                destination="forget"
            )

            self.logger.log(
                message=conversation_turn.content,
                decision="forget",
                reasoning=decision.reasoning
            )

            return decision

        decision = RoutingDecision(

            reasoning="Contains potentially valuable information.",

            destination="episodic",

            event_summary=conversation_turn.content[:100],

            context=conversation_turn.content,

            outcome="Stored as an episode."
        )

        episode = Episode(

            entity_id="unknown",

            event_summary=decision.event_summary,

            context=decision.context,

            outcome=decision.outcome
        )

        self.episodic_store.add_episode(episode)

        self.logger.log(
            message=conversation_turn.content,
            decision="episodic",
            reasoning=decision.reasoning
        )

        return decision