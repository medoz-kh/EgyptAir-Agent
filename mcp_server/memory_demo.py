from datetime import datetime, timedelta

from memory.manger import MemoryManager
from memory.semantic_store import SemanticStore
from memory.models import SemanticFact


def main():

    memory = MemoryManager()

    print("=" * 60)
    print("SHORT TERM MEMORY DEMO")
    print("=" * 60)

    messages = [

        "Hello",

        "How are you?",

        "Passenger prefers Voucher.",

        "Weather is nice.",

        "Employee manager is Ahmed.",

        "Random small talk.",

        "Passenger now prefers Cash Refund.",

        "Another random message.",

        "Temporary office assignment.",

        "Coffee break.",

        "One more message to trigger overflow.",

        "Last message."
    ]

    for msg in messages:

        print(f"\nAdding: {msg}")

        memory.add_turn(
            role="user",
            content=msg
        )

    print("\n")
    print("=" * 60)
    print("RUNNING CONSOLIDATION")
    print("=" * 60)

    memory.consolidate()

    print("\n")
    print("=" * 60)
    print("VERSION HISTORY")
    print("=" * 60)

    memory.consolidator.show_versions(
        "Passenger",
        "preferred_compensation"
    )

    print("\n")
    print("=" * 60)
    print("EXPIRATION DEMO")
    print("=" * 60)

    semantic = SemanticStore()

    expired = SemanticFact(
        entity_id="Office",
        attribute="Temporary Office",
        value="Cairo Terminal 2",
        version=1,
        expires_at=datetime.utcnow() - timedelta(days=1)
    )

    semantic.add_fact(expired)

    semantic.mark_stale()

    print("Expired fact inserted and marked STALE.")

    print("\n")
    print("=" * 60)
    print("DEMO COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()