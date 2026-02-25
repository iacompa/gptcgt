"""
Smart Intent Extraction Engine.

Replaces naive zero-cost string heuristics by utilizing `QualityTier.LIGHT` models
(e.g., Gemini Flash, GPT-4o-mini). Evaluates a prompt to determine mathematical
complexity (1-10) and extracts exact filenames and symbols to guarantee the
heavy models are only spun up when absolutely necessary.
"""

from __future__ import annotations

import json
from typing import Any

from src.core.logger import get_logger
from src.core.model_registry import ModelRegistry
from src.core.router import TaskIntent

logger = get_logger("core.intent_analyzer")


class IntentAnalyzer:
    """Uses a fast LIGHT LLM to strictly evaluate task complexity and scope."""

    def __init__(self):
        self.registry = ModelRegistry()

    async def analyze(self, user_text: str, attached_files: list[dict]) -> dict[str, Any]:
        """
        Runs a fractional-token query to parse the user's intent.

        Returns:
            dict: {
                "intent": TaskIntent.value,
                "complexity": int (1-10),
                "mentioned_files": list[str],
                "mentioned_symbols": list[str]
            }

        """
        # Default fallback payload mapping to naive heuristics if API fails

        try:
            from src.core.router import CodingRouter

            CodingRouter()

            # Phase 19: Robust Fallback — Get the absolute cheapest model the user actually has keys for.
            # If they don't have a LIGHT model configured, fall back to whatever they do have.
            available_models = self.registry.get_available_models()
            if not available_models:
                logger.warning("Intent Analyzer bypassed: No API keys configured.")
                return self._naive_fallback(user_text, attached_files)

            # Sort by input token cost to guarantee we only burn fractional cents on this analysis
            cheapest_available = sorted(available_models, key=lambda x: x.input_cost_per_mtok)[0]
            light_model = cheapest_available

            from src.agents.factory import PROVIDER_KEY_MAP, AgentFactory
            from src.auth.keychain import KeyChainManager

            key_name = PROVIDER_KEY_MAP.get(light_model.provider.value)
            api_key = KeyChainManager.get_key(key_name) if key_name else None

            if not api_key:
                logger.warning("Intent Analyzer bypassed: No API key found for LIGHT model.")
                return self._naive_fallback(user_text, attached_files)

            agent = AgentFactory.create_agent(light_model, api_key=api_key)
            agent.config.max_tokens = 500
            # Force JSON structured output for reliable parsing
            try:
                agent.config.response_format = {"type": "json_object"}
            except AttributeError:
                pass

            valid_intents = [e.value for e in TaskIntent]

            system_prompt = f"""
You are the Intent Analyzer routing engine.
Determine the objective of the user's request.
Return strictly a raw JSON object matching this schema:
{{
    "intent": "string (MUST BE EXACTLY ONE OF: {', '.join(valid_intents)})",
    "complexity": "int (1-10, where 1=simple question/typo, 10=architectural rewrite)",
    "mentioned_files": ["list of explicit filename strings mentioned"],
    "mentioned_symbols": ["list of explicit functions/classes mentioned"]
}}

RULES FOR COMPLEXITY (1-10):
- 1-3: Simple chitchat, asking "how does X work", finding a file, formatting.
- 4-7: Writing new functions, editing existing logic, writing unit tests.
- 8-10: Huge refactors, complex bug hunting across multiple files, architectural work.
"""
            file_names = [f["path"] for f in attached_files] if attached_files else []
            user_prompt = f"USER REQ: {user_text}\nATTACHED FILES: {file_names}"

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]

            full_response = ""
            async for chunk in agent.chat_stream(messages):
                if chunk.text:
                    full_response += chunk.text

            # Clean JSON block
            raw = full_response.strip()
            if raw.startswith("```json"):
                raw = raw[7:]
            if raw.endswith("```"):
                raw = raw[:-3]

            parsed = json.loads(raw.strip())

            # Sanitize Intent
            intent_val = parsed.get("intent", TaskIntent.CHAT.value)
            if intent_val not in valid_intents:
                intent_val = TaskIntent.CHAT.value

            # Sanitize Complexity
            comp_val = parsed.get("complexity", 5)
            try:
                comp_val = int(comp_val)
                comp_val = max(1, min(10, comp_val))
            except (ValueError, TypeError):
                comp_val = 5

            logger.info(f"IntentAnalyzer mapped '{intent_val}' at Complexity {comp_val}/10")

            return {
                "intent": intent_val,
                "complexity": comp_val,
                "mentioned_files": parsed.get("mentioned_files", []),
                "mentioned_symbols": parsed.get("mentioned_symbols", []),
            }

        except Exception as e:
            logger.error(f"IntentAnalyzer failed, falling back to naive heuristics: {e}")
            return self._naive_fallback(user_text, attached_files)

    def _naive_fallback(self, text: str, files: list[dict]) -> dict[str, Any]:
        """Uses fast keyword-based heuristics if the LLM analyzer fails."""
        lower = text.lower()

        architect_keywords = ["build an app", "make a game", "create an application"]
        create_keywords = ["write", "create", "add", "implement", "generate"]
        debug_keywords = ["fix", "bug", "debug", "error", "solve"]
        edit_keywords = ["refactor", "update", "change", "remove", "delete", "modify"]
        explain_keywords = ["explain", "what", "how", "why", "describe"]

        intent = TaskIntent.CHAT.value

        if any(kw in lower for kw in architect_keywords):
            intent = TaskIntent.ARCHITECT.value
        elif any(kw in lower for kw in debug_keywords):
            intent = TaskIntent.DEBUG.value
        elif any(kw in lower for kw in create_keywords):
            intent = TaskIntent.CREATE.value
        elif any(kw in lower for kw in edit_keywords):
            intent = TaskIntent.EDIT.value
        elif any(kw in lower for kw in explain_keywords):
            intent = TaskIntent.QUESTION.value

        complexity = min(10, max(1, len(lower) // 500 + len(files) * 2))
        if intent == TaskIntent.QUESTION.value:
            complexity = max(1, complexity // 2)

        return {
            "intent": intent,
            "complexity": complexity,
            "mentioned_files": [],
            "mentioned_symbols": [],
        }
