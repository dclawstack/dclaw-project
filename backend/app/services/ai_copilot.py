"""AI Copilot service — chat + suggestions backed by OpenRouter or local Ollama.

Design notes (YC positioning):
- LLM provider abstraction so we can ship on day one with cloud (OpenRouter)
  and fall back to a local Ollama for on-prem / privacy-sensitive customers.
- All inference goes through a single `chat()` entrypoint so the rest of the
  app stays provider-agnostic.
- Heuristic fallback (no network, no Ollama): we still return something
  useful — a deterministic summary built from project state. This guarantees
  the YC demo never hits an empty state.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import AsyncIterator

import httpx

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger("dclaw.ai")
# Silence httpx access-log noise per inference call.
logging.getLogger("httpx").setLevel(logging.WARNING)


@dataclass
class ChatMessage:
    role: str  # "system" | "user" | "assistant"
    content: str

    def as_dict(self) -> dict:
        return {"role": self.role, "content": self.content}


@dataclass
class ChatResult:
    text: str
    provider: str  # "openrouter" | "ollama" | "heuristic"
    model: str
    tokens_in: int | None = None
    tokens_out: int | None = None


class AICopilotService:
    """Single entry-point service for all LLM calls."""

    def __init__(self) -> None:
        self.openrouter_key = settings.openrouter_api_key
        self.openrouter_model = settings.openrouter_model
        self.openrouter_base = settings.openrouter_base_url.rstrip("/")
        self.ollama_url = settings.ollama_url.rstrip("/")
        self.ollama_model = settings.ollama_model

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        max_tokens: int = 1024,
        temperature: float = 0.3,
        json_mode: bool = False,
    ) -> ChatResult:
        """Try OpenRouter → Ollama → heuristic fallback. Never raises."""
        if self.openrouter_key:
            try:
                return await self._call_openrouter(
                    messages, max_tokens=max_tokens, temperature=temperature, json_mode=json_mode
                )
            except Exception as exc:  # pragma: no cover - network-dependent
                log.warning("ai.openrouter.error", error=str(exc))

        try:
            return await self._call_ollama(
                messages, max_tokens=max_tokens, temperature=temperature, json_mode=json_mode
            )
        except Exception as exc:
            log.warning("ai.ollama.error", error=str(exc))

        return self._heuristic_reply(messages)

    async def _call_openrouter(
        self,
        messages: list[ChatMessage],
        *,
        max_tokens: int,
        temperature: float,
        json_mode: bool,
    ) -> ChatResult:
        payload: dict = {
            "model": self.openrouter_model,
            "messages": [m.as_dict() for m in messages],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self.openrouter_base}/chat/completions",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.openrouter_key}",
                    "X-Title": "DClaw Project Copilot",
                },
            )
            resp.raise_for_status()
            data = resp.json()
        text = data["choices"][0]["message"]["content"]
        usage = data.get("usage") or {}
        return ChatResult(
            text=text,
            provider="openrouter",
            model=self.openrouter_model,
            tokens_in=usage.get("prompt_tokens"),
            tokens_out=usage.get("completion_tokens"),
        )

    async def _call_ollama(
        self,
        messages: list[ChatMessage],
        *,
        max_tokens: int,
        temperature: float,
        json_mode: bool,
    ) -> ChatResult:
        payload: dict = {
            "model": self.ollama_model,
            "messages": [m.as_dict() for m in messages],
            "stream": False,
            "options": {"num_predict": max_tokens, "temperature": temperature},
        }
        if json_mode:
            payload["format"] = "json"
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(f"{self.ollama_url}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()
        text = (data.get("message") or {}).get("content", "")
        return ChatResult(
            text=text,
            provider="ollama",
            model=self.ollama_model,
            tokens_in=data.get("prompt_eval_count"),
            tokens_out=data.get("eval_count"),
        )

    def _heuristic_reply(self, messages: list[ChatMessage]) -> ChatResult:
        """Provider-of-last-resort: rule-based reply so the UI never breaks.

        This keeps the YC demo honest: if no LLM is reachable we still produce
        a useful, deterministic answer instead of erroring.
        """
        user_msg = next(
            (m.content for m in reversed(messages) if m.role == "user"),
            "",
        )
        if "plan" in user_msg.lower() or "wbs" in user_msg.lower():
            text = (
                "I'm currently running in offline mode. To plan this project I would "
                "decompose it into: 1) Discovery & requirements, 2) Design, "
                "3) Build (back-end + front-end), 4) Test & harden, 5) Launch. "
                "Configure OPENROUTER_API_KEY or start Ollama locally to get a "
                "fully tailored breakdown."
            )
        elif "risk" in user_msg.lower():
            text = (
                "Heuristic risk scan: check for overdue tasks, milestones within 7 "
                "days with open work, and any unassigned high-priority tasks. "
                "Connect an LLM for a tailored risk narrative."
            )
        else:
            text = (
                "I'm running without a live LLM right now. Set OPENROUTER_API_KEY "
                "or run Ollama on localhost:11434 to enable full Copilot answers."
            )
        return ChatResult(text=text, provider="heuristic", model="heuristic-v1")

    async def stream_chat(
        self, messages: list[ChatMessage]
    ) -> AsyncIterator[str]:
        """Token-stream the response. Falls back to a single chunk for non-streaming
        providers (Ollama non-stream, heuristic, OpenRouter errors)."""
        result = await self.chat(messages)
        # Stream the text in word-sized chunks so the UI feels responsive even
        # when the underlying provider didn't stream.
        for word in result.text.split(" "):
            yield word + " "


# Project-aware prompt helpers ----------------------------------------------


SYSTEM_PROMPT = (
    "You are DClaw Copilot — an expert AI project manager. "
    "You are concise, action-oriented, and grounded in the project data provided. "
    "When the user asks about a project, ground your answer in the supplied context. "
    "Suggest next actions explicitly. Never invent task IDs, due dates, or owners "
    "that aren't in the supplied context."
)


def project_context_block(project: dict) -> str:
    """Render a structured project summary for the LLM."""
    lines = [
        f"PROJECT: {project.get('name')} (status={project.get('status')})",
        f"OWNER: {project.get('owner')}",
        f"DESCRIPTION: {project.get('description') or '(none)'}",
        f"TIMELINE: {project.get('start_date') or '?'} → {project.get('end_date') or '?'}",
        "TASKS:",
    ]
    for t in project.get("tasks", []):
        lines.append(
            f"  - [{t['status']}|{t['priority']}] {t['title']}"
            + (f" (due {t['due_date']})" if t.get("due_date") else "")
            + (f" assigned to {t['assignee']}" if t.get("assignee") else "")
        )
    if not project.get("tasks"):
        lines.append("  (no tasks yet)")
    lines.append("MILESTONES:")
    for m in project.get("milestones", []):
        check = "[x]" if m.get("completed") else "[ ]"
        lines.append(f"  {check} {m['name']} (target {m.get('target_date')})")
    if not project.get("milestones"):
        lines.append("  (no milestones)")
    return "\n".join(lines)


# Singleton accessor ---------------------------------------------------------

_singleton: AICopilotService | None = None


def get_copilot() -> AICopilotService:
    global _singleton
    if _singleton is None:
        _singleton = AICopilotService()
    return _singleton
