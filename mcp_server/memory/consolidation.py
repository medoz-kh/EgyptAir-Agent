from datetime import datetime

from .episodic_store import EpisodicStore
from .models import SemanticFact
from .semantic_store import SemanticStore


class MemoryConsolidator:

    """
    Converts Episodic Memory

    into

    Semantic Memory.
    """

    def __init__(self):

        self.episodic = EpisodicStore()

        self.semantic = SemanticStore()

    # --------------------------------------------------------

    def consolidate(self):

        episodes = self.episodic.get_all()

        print(f"\nScanning {len(episodes)} episodes...")

        for episode in episodes:

            self.process_episode(episode)

        self.semantic.mark_stale()

    # --------------------------------------------------------

    def process_episode(self, episode):

        """
        Demo extraction.

        In production an LLM would extract
        entity/attribute/value.

        Here we simulate it.
        """

        text = episode["context"]

        text_lower = text.lower()

        # --------------------------------------------------

        if "voucher" in text_lower:

            self.update_fact(

                entity="Passenger",

                attribute="preferred_compensation",

                value="Voucher",

                episode_id=episode["episode_id"]
            )

        # --------------------------------------------------

        elif "cash refund" in text_lower:

            self.update_fact(

                entity="Passenger",

                attribute="preferred_compensation",

                value="Cash Refund",

                episode_id=episode["episode_id"]
            )

        # --------------------------------------------------

        elif "manager is" in text_lower:

            manager = text.split("manager is")[-1].strip()

            self.update_fact(

                entity="Employee",

                attribute="manager",

                value=manager,

                episode_id=episode["episode_id"]
            )

    # --------------------------------------------------------

    def update_fact(

        self,

        entity,

        attribute,

        value,

        episode_id

    ):

        current = self.semantic.get_current_fact(

            entity,

            attribute

        )

        # ----------------------------------------

        if current is None:

            fact = SemanticFact(

                entity_id=entity,

                attribute=attribute,

                value=value,

                version=1,

                updated_from_episode=episode_id
            )

            self.semantic.add_fact(fact)

            print(

                f"[NEW FACT] "

                f"{attribute} = {value}"

            )

            return

        # ----------------------------------------

        if current["value"] == value:

            return

        print()

        print("CONFLICT DETECTED")

        print("--------------------------")

        print(

            f"Old : {current['value']}"

        )

        print(

            f"New : {value}"

        )

        self.semantic.deactivate_current(

            entity,

            attribute

        )

        new_fact = SemanticFact(

            entity_id=entity,

            attribute=attribute,

            value=value,

            version=current["version"] + 1,

            updated_from_episode=episode_id
        )

        self.semantic.add_fact(new_fact)

        print(

            f"Version "

            f"{new_fact.version}"

            f" created."

        )

    # --------------------------------------------------------

    def show_versions(

        self,

        entity,

        attribute

    ):

        versions = self.semantic.get_versions(

            entity,

            attribute

        )

        print()

        print("Version History")

        print("----------------")

        for row in versions:

            print(

                f"v{row['version']} "

                f"{row['value']} "

                f"(current={row['current']})"

            )