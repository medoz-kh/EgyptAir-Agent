import asyncio
import time
import os
from typing import List, Dict, Any
from dotenv import load_dotenv
from google import genai
from google.genai import types

from Context import context_manager

load_dotenv()

MODEL_ID ="gemini-3.1-flash-lite"  

# -----------------------------------------------------------------------------
# 1. SETUP LONG-CONTEXT TEST TRANSCRIPT
# -----------------------------------------------------------------------------
# Early Decision: User provides identity, booking ID #3, and wheelchair request.
# Tool Noise: Multiple turns returning large JSON bodies (simulating DB query dumps).
# Final Evaluation Query: Asks to draft an apology email referencing early facts.
# -----------------------------------------------------------------------------

def build_test_transcript() -> List[types.Content]:
    transcript = [
        # Turn 1: Early critical decisions/facts buried early
        types.Content(
            role="user",
            parts=[types.Part.from_text(
                text="Hi, my name is Alice Vance. I'm on booking ID 3. Please remember I need wheelchair assistance at the gate."
            )]
        ),
        types.Content(
            role="model",
            parts=[types.Part.from_text(
                text="Hello Alice! I have noted booking ID 3 and your wheelchair assistance request."
            )]
        ),

        # Turn 2: Tool Noise 1 (Flight status query)
        types.Content(
            role="user",
            parts=[types.Part.from_function_response(
                name="get_flight_status",
                response={"result": "{" + "'flight_id': 'MS702', 'status': 'DELAYED', 'delay_minutes': 140, 'passenger_manifest': ['P1', 'P2', 'Alice Vance', 'P4', 'P5']}" * 10}
            )]
        ),
        types.Content(
            role="model",
            parts=[types.Part.from_text(text="Flight MS702 is currently delayed by 140 minutes.")]
        ),

        # Turn 3: Tool Noise 2 (Large Disruption Report JSON Payload)
        types.Content(
            role="user",
            parts=[types.Part.from_function_response(
                name="generate_disruption_report",
                response={"result": "{" + "'report_id': 9921, 'affected_flights': ['MS701', 'MS702', 'MS985'], 'vouchers_issued': False, 'logs': 'System delay due to maintenance'}" * 15}
            )]
        ),
        types.Content(
            role="model",
            parts=[types.Part.from_text(text="I have generated the disruption report for Flight MS702.")]
        ),

        # Turn 4: Tool Noise 3 (Policy lookup payload)
        types.Content(
            role="user",
            parts=[types.Part.from_function_response(
                name="read_policy_resource",
                response={"result": "EGYPTAIR DISRUPTION POLICY 2026: Delays over 120 mins qualify for food vouchers and refund option." * 10}
            )]
        ),
        types.Content(
            role="model",
            parts=[types.Part.from_text(text="Policy reviewed. Passengers qualify for vouchers.")]
        ),

        # Turn 5: Final Evaluation Task
        types.Content(
            role="user",
            parts=[types.Part.from_text(
                text="Based on our conversation so far, what is my booking ID, passenger name, and special assistance request? Also draft a quick apology note."
            )]
        )
    ]
    return transcript


# -----------------------------------------------------------------------------
# 2. BENCHMARK RUNNER
# -----------------------------------------------------------------------------

async def evaluate_strategy(strategy_name: str, genai_client: genai.Client) -> Dict[str, Any]:
    print(f"\n🧪 Running Benchmark for Strategy: [{strategy_name.upper()}]...")
    
    manager = context_manager.ContextWindowManager(strategy_name=strategy_name, window_size=4)
    raw_history = build_test_transcript()

    start_time = time.perf_counter()

    # Step A: Apply Pruning Strategy
    pruned_history = await manager.process_context(
        chat_history=raw_history,
        genai_client=genai_client,
        model_id=MODEL_ID
    )

    # Step B: Call Gemini with Pruned Context
    response = await genai_client.aio.models.generate_content(
        model=MODEL_ID,
        contents=pruned_history,
        config=types.GenerateContentConfig(temperature=0.0)
    )

    elapsed_time = time.perf_counter() - start_time

    # Step C: Collect Token & Response Metrics
    usage = response.usage_metadata
    prompt_tokens = usage.prompt_token_count if usage else 0
    response_text = response.text or ""

    # Step D: Accuracy Evaluation against Buried Context
    # Check if early facts (Booking ID 3, Alice Vance, Wheelchair) survived pruning
    has_name = "Alice" in response_text
    has_booking = "3" in response_text
    has_wheelchair = "wheelchair" in response_text.lower()

    retained_facts = sum([has_name, has_booking, has_wheelchair])
    accuracy_score = (retained_facts / 3.0) * 100

    return {
        "strategy": strategy_name,
        "tokens_consumed": prompt_tokens,
        "latency_sec": round(elapsed_time, 2),
        "accuracy_pct": round(accuracy_score, 1),
        "response_sample": response_text[:120].replace("\n", " ") + "..."
    }


# -----------------------------------------------------------------------------
# 3. MAIN BENCHMARK EXECUTION & TABLE DISPLAY
# -----------------------------------------------------------------------------

async def main():
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("❌ Error: GEMINI_API_KEY environment variable not set.")
        return

    genai_client = genai.Client(api_key=api_key)
    strategies = ["sliding_window", "observation_masking", "recursive_summarization", "zone_based"]
    
    results = []
    for strat in strategies:
        res = await evaluate_strategy(strat, genai_client)
        results.append(res)

    # Output Comparison Table
    print("\n" + "="*95)
    print("📊 CONTEXT WINDOW MANAGEMENT STRATEGY COMPARISON")
    print("="*95)
    print(f"{'Strategy':<25} | {'Accuracy (%)':<12} | {'Tokens Consumed':<16} | {'Latency (s)':<12} | {'Status'}")
    print("-" * 95)

    for r in results:
        status = "✅ WINNER" if r["accuracy_pct"] == 100.0 and r["tokens_consumed"] < 2000 else "⚠️ COMPROMISED"
        print(f"{r['strategy']:<25} | {r['accuracy_pct']:<12}% | {r['tokens_consumed']:<16} | {r['latency_sec']:<12}s | {status}")

    print("="*95)


if __name__ == "__main__":
    asyncio.run(main())