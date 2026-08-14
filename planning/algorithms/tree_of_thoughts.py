import json
from pydantic import BaseModel, ConfigDict, Field
from google import genai
from google.genai import types

from ..models import Thought


class ThoughtCandidates(BaseModel):
    model_config = ConfigDict(extra="forbid")
    candidates: list[str] = Field(min_length=1, max_length=3)


class ThoughtEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    score: float = Field(ge=0.0, le=1.0)
    rationale: str


async def tree_of_thoughts(
    problem: str,
    client: genai.Client,
    depth: int = 2,
    beam_width: int = 2,
    model_id: str = "gemini-3.1-flash-lite"
) -> list[Thought]:
    frontier = [Thought(state="Start", score=0.5, rationale="root")]
    
    for _ in range(depth):
        candidates: list[Thought] = []
        for parent in frontier:
            # 1. Generate candidates
            system_instruction_gen = "Generate distinct candidate next steps for Tree-of-Thoughts search."
            prompt_gen = (
                f"Problem: {problem}\n"
                f"Partial path: {parent.state}\n"
                "Propose two distinct promising continuations."
            )
            
            resp_gen = await client.aio.models.generate_content(
                model=model_id,
                contents=prompt_gen,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction_gen,
                    temperature=0.5,
                    response_mime_type="application/json",
                    response_schema=ThoughtCandidates,
                )
            )
            
            try:
                generated = ThoughtCandidates.model_validate_json(resp_gen.text)
            except Exception:
                continue  # Skip if JSON parsing fails
                
            for state in generated.candidates[:2]:
                # 2. Evaluate candidates
                system_instruction_eval = "Independently evaluate a partial solution."
                prompt_eval = (
                    f"Problem: {problem}\n"
                    f"Candidate path: {state}\n"
                    "Score correctness, feasibility, and progress. Do not reward confident wording."
                )
                
                resp_eval = await client.aio.models.generate_content(
                    model=model_id,
                    contents=prompt_eval,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction_eval,
                        temperature=0.1,
                        response_mime_type="application/json",
                        response_schema=ThoughtEvaluation,
                    )
                )
                
                try:
                    judged = ThoughtEvaluation.model_validate_json(resp_eval.text)
                    candidates.append(
                        Thought(state=state, score=judged.score, rationale=judged.rationale)
                    )
                except Exception:
                    pass
                    
        frontier = sorted(candidates, key=lambda item: item.score, reverse=True)[:beam_width]
        if not frontier:
            break
            
    return frontier