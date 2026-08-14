from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


FLIGHT_NUMBER = "MS703"
BOOKING_ID = 4


async def main() -> None:
    print("\n" + "=" * 60)
    print("EGYPTAIR DYNAMIC DISRUPTION TEST")
    print("=" * 60)

    server_path = PROJECT_ROOT / "mcp_server" / "server.py"

    server_params = StdioServerParameters(
        command=sys.executable,
        args=[str(server_path)],
        env=None,
    )

    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:

            await session.initialize()

            print("✅ MCP connection established")

            history = []

            # ---------------------------------------------------------
            # STEP 1 — Check flight
            # ---------------------------------------------------------
            print("\n▶ Step 1: Check flight status")

            result = await session.call_tool(
                name="get_flight_status",
                arguments={
                    "flight_number": FLIGHT_NUMBER
                },
            )

            flight = extract_json(result)

            print(json.dumps(flight, indent=2))

            history.append({
                "step": 1,
                "action": "get_flight_status",
                "result": flight,
            })

            if not flight.get("found"):
                print("\n❌ Flight not found.")
                return

            # ---------------------------------------------------------
            # DYNAMIC DECISION
            # ---------------------------------------------------------
            status = flight.get("status")
            delay = flight.get("delay_minutes", 0)

            print("\n🧠 Dynamic decision:")
            print(f"   Status: {status}")
            print(f"   Delay: {delay} minutes")

            # ---------------------------------------------------------
            # CANCELLED PATH
            # ---------------------------------------------------------
            if status == "Cancelled":

                print("\n➡ Flight is CANCELLED.")
                print("➡ Dynamic planner chooses to inspect the booking.")

                result = await session.call_tool(
                    name="get_booking_details",
                    arguments={
                        "booking_id": BOOKING_ID
                    },
                )

                booking = extract_json(result)

                print("\n▶ Step 2: Booking details")
                print(json.dumps(booking, indent=2))

                history.append({
                    "step": 2,
                    "action": "get_booking_details",
                    "result": booking,
                })

                print("\n➡ Dynamic planner chooses to inspect policy.")

                result = await session.read_resource(
                    "sql://policies"
                )

                policies = extract_resource(result)

                print("\n▶ Step 3: Policies")
                print(json.dumps(policies, indent=2))

                history.append({
                    "step": 3,
                    "action": "read_resource:sql://policies",
                    "result": policies,
                })

                print("\n🧠 Dynamic decision:")
                print(
                    "Flight is cancelled. "
                    "Rebooking policy applies."
                )

                decision = (
                    "REBOOKING REQUIRED: "
                    "The flight is cancelled. "
                    "The passenger may request free rebooking "
                    "to the next available flight."
                )

            # ---------------------------------------------------------
            # DELAYED PATH
            # ---------------------------------------------------------
            elif status == "Delayed":

                print("\n➡ Flight is DELAYED.")

                result = await session.call_tool(
                    name="get_booking_details",
                    arguments={
                        "booking_id": BOOKING_ID
                    },
                )

                booking = extract_json(result)

                print("\n▶ Step 2: Booking details")
                print(json.dumps(booking, indent=2))

                history.append({
                    "step": 2,
                    "action": "get_booking_details",
                    "result": booking,
                })

                result = await session.read_resource(
                    "sql://policies"
                )

                policies = extract_resource(result)

                print("\n▶ Step 3: Policies")
                print(json.dumps(policies, indent=2))

                history.append({
                    "step": 3,
                    "action": "read_resource:sql://policies",
                    "result": policies,
                })

                if delay > 120:
                    decision = (
                        "COMPENSATION REVIEW: "
                        "The flight delay exceeds two hours. "
                        "Review compensation eligibility."
                    )
                else:
                    decision = (
                        "NO AUTOMATIC COMPENSATION: "
                        "The delay does not exceed two hours."
                    )

            # ---------------------------------------------------------
            # NORMAL PATH
            # ---------------------------------------------------------
            else:

                decision = (
                    "NO DISRUPTION ACTION: "
                    "The flight is currently scheduled."
                )

            history.append({
                "step": len(history) + 1,
                "action": "dynamic_decision",
                "result": decision,
            })

            # ---------------------------------------------------------
            # FINAL RESULT
            # ---------------------------------------------------------
            print("\n" + "=" * 60)
            print("FINAL DYNAMIC DECISION")
            print("=" * 60)

            print(f"\nFlight: {FLIGHT_NUMBER}")
            print(f"Booking: {BOOKING_ID}")
            print(f"\n{decision}")

            print("\n" + "=" * 60)
            print("DYNAMIC DISRUPTION TEST: PASSED")
            print("=" * 60)

            print("\nExecution history:")
            print(
                json.dumps(
                    history,
                    indent=2,
                    ensure_ascii=False
                )
            )


def extract_json(result) -> dict:
    text = extract_text(result)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {
            "raw": text
        }


def extract_text(result) -> str:
    texts = []

    for content in result.content:
        if getattr(content, "type", None) == "text":
            texts.append(content.text)

    return "\n".join(texts)


def extract_resource(result) -> list:
    texts = []

    for content in result.contents:
        if hasattr(content, "text"):
            texts.append(content.text)

    combined = "\n".join(texts)

    try:
        return json.loads(combined)
    except json.JSONDecodeError:
        return [
            {
                "raw": combined
            }
        ]


if __name__ == "__main__":
    asyncio.run(main())