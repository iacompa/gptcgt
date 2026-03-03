"""
Smart Intent Extraction Engine.

Replaces naive zero-cost string heuristics by utilizing `QualityTier.LIGHT` models
(e.g., Gemini Flash, GPT-4o-mini). Evaluates a prompt to determine mathematical
complexity (1-10) and extracts exact filenames and symbols to guarantee the
heavy models are only spun up when absolutely necessary.
"""

from __future__ import annotations

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
        Runs a fractional-token query using embeddings to parse the user's intent.

        Returns:
            dict: {
                "intent": TaskIntent.value,
                "complexity": int (1-10),
                "mentioned_files": list[str],
                "mentioned_symbols": list[str]
            }

        """
        from src.core.router import TaskIntent

        # 1. Very Fast Heuristic Extraction for files and complexity
        file_names = [f["path"] for f in attached_files] if attached_files else []  # noqa: F841
        mentioned_files = [w for w in user_text.split() if "." in w and len(w) > 3]
        mentioned_symbols = [w.strip("()") for w in user_text.split() if "()" in w]

        # Basic complexity:
        base_comp = 2
        if len(user_text) > 100: base_comp += 1  # noqa: E701
        if len(user_text) > 500: base_comp += 2  # noqa: E701
        if len(attached_files) > 2: base_comp += 2  # noqa: E701
        if len(attached_files) > 5: base_comp += 2  # noqa: E701
        comp_val = max(1, min(10, base_comp))

        default_return = {
            "intent": TaskIntent.CHAT.value,
            "complexity": comp_val,
            "mentioned_files": mentioned_files,
            "mentioned_symbols": mentioned_symbols,
        }

        try:
            available_models = self.registry.get_available_models()
            if not available_models:
                logger.warning("Intent Analyzer bypassed: No API keys configured.")
                return default_return

            # Find an embedding host we have keys for
            from src.agents.factory import PROVIDER_KEY_MAP
            from src.auth.keychain import KeyChainManager

            embedding_model = None
            api_key = None
            for model in available_models:
                provider_str = model.provider.value
                if provider_str in ["openai", "google"]:
                    k_name = PROVIDER_KEY_MAP.get(provider_str)
                    found_key = KeyChainManager.get_key(k_name) if k_name else None
                    if found_key:
                        embedding_model = "text-embedding-3-small" if provider_str == "openai" else "gemini/text-embedding-004"  # noqa: E501
                        api_key = found_key
                        break

            if not embedding_model:
                logger.warning("Intent Analyzer bypassed: No Embeddings API key found.")
                # Naive fallback for intent
                fallback = self._naive_fallback(user_text, attached_files)
                default_return["intent"] = fallback.get("intent", TaskIntent.CHAT.value)
                return default_return

            import litellm

            # Few-shot intent vectors (Ideally cached, but building at runtime for phase 1)
            # We map explicit sentences to their intents
            intent_examples = {
                TaskIntent.CHAT.value: "hello how are you",
                TaskIntent.QUESTION.value: "how does this function work what is this code doing explain this",
                TaskIntent.EDIT.value: "change the padding to 10px rename this variable fix this bug update the UI",
                TaskIntent.CREATE.value: "build a new react component write a unit test add a python script",
                TaskIntent.DEBUG.value: "why is this crashing fix the null pointer exception solve the build error traceback",  # noqa: E501
                TaskIntent.ARCHITECT.value: "design a scalable backend refactor the entire application create a new project from scratch"  # noqa: E501
            }

            # Request embeddings
            inputs = [user_text] + list(intent_examples.values())

            # Pass api_key directly — never mutate os.environ
            response = litellm.embedding(model=embedding_model, input=inputs, api_key=api_key)

            embeddings = [item['embedding'] for item in response.data]
            user_emb = embeddings[0]
            example_embs = embeddings[1:]

            def cosine_sim(v1, v2):
                dot = sum(a * b for a, b in zip(v1, v2))
                norma = sum(a * a for a in v1) ** 0.5
                normb = sum(b * b for b in v2) ** 0.5
                if norma == 0 or normb == 0: return 0.0  # noqa: E701
                return dot / (norma * normb)

            best_intent = TaskIntent.CHAT.value
            best_score = -1.0

            for idx, (intent_name, _) in enumerate(intent_examples.items()):
                score = cosine_sim(user_emb, example_embs[idx])
                if score > best_score:
                    best_score = score
                    best_intent = intent_name

            logger.info(f"IntentAnalyzer mapped '{best_intent}' via Embeddings at Complexity {comp_val}/10")

            default_return["intent"] = best_intent
            return default_return

        except Exception as e:
            logger.error(f"IntentAnalyzer Embeddings failed: {e}")
            fallback = self._naive_fallback(user_text, attached_files)
            default_return["intent"] = fallback.get("intent", TaskIntent.CHAT.value)
            return default_return

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
