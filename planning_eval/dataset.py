from typing import List, Dict, Any

COMPLEX_FLIGHT_TEST_SUITE: List[Dict[str, Any]] = [
    {
        "id": "TC01",
        "category": "mechanical_sequential",
        "decomposition_type": "static",
        "prompt": "Check flight status for MS702 and lookup EgyptAir baggage allowance policy.",
        "expected_algorithm": "PS",
        "grounded_validation": "lookup"
    },
    {
        "id": "TC02",
        "category": "multi_variable_ranking",
        "decomposition_type": "dynamic",
        "prompt": "Rank top 3 flight routes from CAI to JFK balancing layover duration, total cost, and arrival time flexibility.",
        "expected_algorithm": "ToT",
        "grounded_validation": "ranking"
    },
    {
        "id": "TC03",
        "category": "grounded_constraint_conflict",
        "decomposition_type": "dynamic",
        "prompt": "Reserve seat 12A on flight MS702 for passenger Bob. (Note: Seat 12A is occupied by Alice Vance).",
        "expected_algorithm": "LATS",
        "grounded_validation": "sqlite_double_booking_check"
    },
    {
        "id": "TC04",
        "category": "disruption_recovery",
        "decomposition_type": "dynamic",
        "prompt": "Flight MS702 is delayed 140 mins. Rebook passenger on MS985 and verify seat availability before confirming.",
        "expected_algorithm": "LATS",
        "grounded_validation": "rebook_verification"
    }
]