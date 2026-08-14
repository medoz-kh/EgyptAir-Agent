from __future__ import annotations

import math
import json
from dataclasses import dataclass, field

from pydantic import BaseModel, ConfigDict, Field
from google import genai
from google.genai import types

from ..models import EnvironmentFeedback
from .environment import Environment


class LATSAction(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    action: str = Field(min_length=2)
    state: str = Field(min_length=2)


class LATSActionBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    actions: list[LATSAction] = Field(min_length=1, max_length=3)


class ValueEstimate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    score: float = Field(ge=0.0, le=1.0)


@dataclass
class LATSNode:
    state: str
    action: str = "root"
    parent: "LATSNode | None" = field(default=None, repr=False)
    children: list["LATSNode"] = field(default_factory=list, repr=False)
    visits: int = 0
    value_sum: float = 0.0
    environment_score: float = 0.0
    model_score: float = 0.0
    feedback: EnvironmentFeedback | None = None
    reflections: list[str] = field(default_factory=list)

    @property
    def mean_value(self) -> float:
        return self.value_sum / self.visits if self.visits else 0.0


@dataclass
class LATSResult:
    success: bool
    output: str
    best_score: float
    iterations: int
    root: LATSNode


def _uct(node: LATSNode, exploration_weight: float) -> float:
    if node.visits == 0:
        return float("inf")
    parent_visits = max(node.parent.visits if node.parent else 1, 1)
    return node.mean_value + exploration_weight * math.sqrt(math.log(parent_visits) / node.visits)


def _select_leaf(root: LATSNode, exploration_weight: float) -> LATSNode:
    node = root
    while node.children:
        node = max(node.children, key=lambda child: _uct(child, exploration_weight))
    return node


def _backpropagate(node: LATSNode, value: float) -> None:
    while node is not None:
        node.visits += 1
        node.value_sum += value
        node = node.parent


def _trajectory_reflections(node: LATSNode) -> list[str]:
    path: list[str] = []
    while node is not None:
        path.extend(node.reflections)
        node = node.parent
    return list(reversed(path))


async def lats(
    task: str,
    client: genai.Client,
    environment: Environment,
    iterations: int = 2,
    n_actions: int = 2,
    exploration_weight: float = 1.414,
    model_id: str = "gemini-3.1-flash-lite"
) -> LATSResult:
    
    if iterations < 1 or n_actions < 1:
        raise ValueError("iterations and n_actions must be positive")
        
    root = LATSNode(state="No attempt yet.")
    best = root
    completed_iterations = 0
    
    for iteration in range(1, iterations + 1):
        completed_iterations = iteration
        leaf = _select_leaf(root, exploration_weight)
        lessons = _trajectory_reflections(leaf)
        lesson_text = "\n".join(f"- {item}" for item in lessons[-4:]) or "- None yet."
        
        system_instruction_action = "You are the action generator in LATS."
        prompt_action = (
            f"Task: {task}\n"
            f"Current trajectory/state:\n{leaf.state}\n"
            f"Reflections learned from failed branches:\n{lesson_text}\n\n"
            f"Propose exactly {n_actions} distinct complete candidate solution(s). Each state must "
            "contain the fully written solution, not a placeholder or description of a solution."
        )

        resp_action = await client.aio.models.generate_content(
            model=model_id,
            contents=prompt_action,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction_action,
                temperature=0.5,
                response_mime_type="application/json",
                response_schema=LATSActionBatch,
            )
        )
        
        try:
            proposed = LATSActionBatch.model_validate_json(resp_action.text)
        except Exception:
            continue
            
        for item in proposed.actions[:n_actions]:
            child = LATSNode(state=item.state.strip(), action=item.action, parent=leaf)
            leaf.children.append(child)
            
            # The actual grounded environment check
            feedback = await environment.evaluate(child.state)
            child.feedback = feedback
            child.environment_score = feedback.score
            
            system_instruction_val = "You are the LATS value function."
            prompt_val = (
                f"Task: {task}\n"
                f"Candidate state:\n{child.state}\n"
                f"External score: {feedback.score}\n"
                f"External feedback: {feedback.details}\n"
                "Estimate the candidate's future usefulness."
            )
            
            resp_val = await client.aio.models.generate_content(
                model=model_id,
                contents=prompt_val,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction_val,
                    temperature=0.1,
                    response_mime_type="application/json",
                    response_schema=ValueEstimate,
                )
            )
            
            try:
                value_judgment = ValueEstimate.model_validate_json(resp_val.text)
                child.model_score = value_judgment.score
            except Exception:
                child.model_score = 0.0
                
            combined_value = 0.75 * child.environment_score + 0.25 * child.model_score
            
            if not feedback.success:
                system_instruction_ref = "Create a branch-level LATS reflection grounded in environment feedback."
                prompt_ref = (
                    f"Task: {task}\n"
                    f"Action: {child.action}\n"
                    f"Resulting state: {child.state}\n"
                    f"External feedback: {feedback.details}\n"
                    "Explain briefly why this branch failed and how a later expansion should change."
                )
                
                resp_ref = await client.aio.models.generate_content(
                    model=model_id,
                    contents=prompt_ref,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction_ref,
                        temperature=0.2
                    )
                )
                
                reflection = resp_ref.text
                if not reflection or not reflection.strip():
                    raise RuntimeError("The chat model returned an empty or unsupported response")
                child.reflections.append(reflection.strip())
                
            _backpropagate(child, combined_value)
            
            if best is root or child.environment_score > best.environment_score:
                best = child
                
            if feedback.success:
                return LATSResult(True, child.state, child.environment_score, completed_iterations, root)
                
    return LATSResult(False, best.state, best.environment_score, completed_iterations, root)


def flatten_lats_tree(root: LATSNode) -> list[dict]:
    records: list[dict] = []
    queue: list[tuple[LATSNode, str | None]] = [(root, None)]
    next_id = 0
    while queue:
        node, parent_id = queue.pop(0)
        node_id = f"n{next_id}"
        next_id += 1
        records.append(
            {
                "id": node_id,
                "parent_id": parent_id,
                "action": node.action,
                "state": node.state,
                "visits": node.visits,
                "mean_value": node.mean_value,
                "environment_score": node.environment_score,
                "model_score": node.model_score,
                "feedback": node.feedback.model_dump() if node.feedback else None,
                "reflections": node.reflections,
            }
        )
        queue.extend((child, node_id) for child in node.children)
    return records