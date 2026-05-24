"""Agentic project planner — multi-step LLM workflow.

State machine: goal → research → wbs → estimate → critical-path → assignment → review.
Each step is a discrete LLM call (or, in fallback mode, a deterministic
heuristic) whose output is fed into the next step. The full trace is
returned to the caller and persisted as an AgentRun for observability.

YC positioning: this is what separates "AI feature" from "AI product."
The agent doesn't just answer a question, it executes a workflow and you
can see every step it took.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

from app.services.ai_copilot import ChatMessage, get_copilot


PLANNER_STEPS = ["research", "wbs", "estimate", "critical_path", "assignment", "review"]


@dataclass
class AgentStep:
    name: str
    prompt: str
    output: dict | str
    provider: str
    model: str
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: int = 0


@dataclass
class AgentTrace:
    goal: str
    steps: list[AgentStep] = field(default_factory=list)
    final: dict = field(default_factory=dict)
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: int = 0


_STEP_PROMPTS: dict[str, str] = {
    "research": (
        "Given the project goal, identify 3-5 key questions to answer before "
        "planning starts (scope ambiguity, unknowns). Output JSON: {\"questions\": [str]}."
    ),
    "wbs": (
        "Decompose the goal into 5-12 tasks. Output JSON: "
        "{\"tasks\": [{\"title\": str, \"description\": str}]}."
    ),
    "estimate": (
        "Estimate each task's effort. Output JSON: "
        "{\"estimates\": [{\"title\": str, \"hours\": int, \"priority\": str}]}."
    ),
    "critical_path": (
        "Identify dependencies between tasks. Output JSON: "
        "{\"edges\": [{\"from\": str, \"to\": str}]}."
    ),
    "assignment": (
        "Suggest a role (e.g., 'backend', 'design', 'pm') for each task. "
        "Output JSON: {\"assignments\": [{\"title\": str, \"role\": str}]}."
    ),
    "review": (
        "Produce a one-paragraph summary of risks and the recommended kick-off "
        "order. Output JSON: {\"summary\": str, \"risks\": [str]}."
    ),
}


def _deterministic_step(step: str, goal: str, prior: list[AgentStep]) -> dict:
    """No-LLM fallback so the agent path is always demoable."""
    if step == "research":
        return {
            "questions": [
                f"What is the primary success metric for: {goal}?",
                "Who are the stakeholders?",
                "What is the hard deadline (if any)?",
            ]
        }
    if step == "wbs":
        return {
            "tasks": [
                {"title": "Discovery", "description": "Define scope + acceptance criteria"},
                {"title": "Design", "description": "Wireframes + data model"},
                {"title": "Build", "description": "Implement core feature set"},
                {"title": "Test", "description": "QA + performance"},
                {"title": "Launch", "description": "Deploy + announce"},
            ]
        }
    if step == "estimate":
        return {
            "estimates": [
                {"title": t["title"], "hours": 16, "priority": "high"}
                for t in (prior[-1].output.get("tasks") if prior else [])
            ]
        }
    if step == "critical_path":
        tasks = prior[-2].output.get("tasks", []) if len(prior) >= 2 else []
        titles = [t["title"] for t in tasks]
        return {
            "edges": [
                {"from": titles[i], "to": titles[i + 1]}
                for i in range(len(titles) - 1)
            ]
        }
    if step == "assignment":
        tasks = prior[-3].output.get("tasks", []) if len(prior) >= 3 else []
        role_map = {"Discovery": "pm", "Design": "design", "Build": "backend",
                    "Test": "qa", "Launch": "pm"}
        return {
            "assignments": [
                {"title": t["title"], "role": role_map.get(t["title"], "engineer")}
                for t in tasks
            ]
        }
    if step == "review":
        return {
            "summary": (
                "Plan covers discovery → design → build → test → launch. "
                "Highest risk is scope ambiguity if discovery doesn't lock criteria."
            ),
            "risks": ["Scope creep", "Capacity at QA", "Launch comms"],
        }
    return {"note": f"unknown step {step}"}


async def run_planner_agent(goal: str, max_steps: int = 6) -> AgentTrace:
    """Run the full state machine. Always returns a complete trace, even
    when the LLM is unreachable (each step falls back to a deterministic
    heuristic)."""
    trace = AgentTrace(goal=goal)
    copilot = get_copilot()
    started = time.perf_counter()

    for step in PLANNER_STEPS[: max_steps]:
        step_started = time.perf_counter()
        instruction = _STEP_PROMPTS[step]
        prior_summaries = [
            f"Step {s.name} output: {json.dumps(s.output)[:500]}"
            for s in trace.steps
        ]
        user_msg = (
            f"GOAL: {goal}\n\n"
            f"PRIOR OUTPUTS:\n" + "\n".join(prior_summaries) + "\n\n"
            f"YOUR TASK ({step}): {instruction}"
        )
        result = await copilot.chat(
            [
                ChatMessage(role="system", content="You are DClaw Planner Agent."),
                ChatMessage(role="user", content=user_msg),
            ],
            json_mode=True,
            max_tokens=800,
        )

        # Try to parse JSON; otherwise fall back to deterministic step.
        try:
            output = json.loads(result.text)
            if not isinstance(output, dict):
                raise ValueError("non-dict")
        except (ValueError, json.JSONDecodeError):
            output = _deterministic_step(step, goal, trace.steps)
            provider, model = "fallback-template", "fallback-v1"
        else:
            provider, model = result.provider, result.model

        step_latency = int((time.perf_counter() - step_started) * 1000)
        trace.steps.append(
            AgentStep(
                name=step,
                prompt=user_msg,
                output=output,
                provider=provider,
                model=model,
                tokens_in=result.tokens_in or 0,
                tokens_out=result.tokens_out or 0,
                latency_ms=step_latency,
            )
        )
        trace.tokens_in += result.tokens_in or 0
        trace.tokens_out += result.tokens_out or 0

    trace.latency_ms = int((time.perf_counter() - started) * 1000)
    # Final synthesis: collect the deterministic-form artefacts
    by_step = {s.name: s.output for s in trace.steps}
    trace.final = {
        "questions": by_step.get("research", {}).get("questions", []),
        "tasks": by_step.get("wbs", {}).get("tasks", []),
        "estimates": by_step.get("estimate", {}).get("estimates", []),
        "edges": by_step.get("critical_path", {}).get("edges", []),
        "assignments": by_step.get("assignment", {}).get("assignments", []),
        "review": by_step.get("review", {}),
    }
    return trace
