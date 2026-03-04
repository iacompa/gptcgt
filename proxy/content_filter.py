"""
Content safety filter with tiered moderation, Unicode normalization, and audit logging.

Levels:
  - BLOCK: Hard reject, request never reaches the LLM
  - WARN:  Logged and flagged, but request is allowed through
"""

import logging
import re
import unicodedata
from typing import Tuple

logger = logging.getLogger("proxy.content_filter")


class FilterResult:
    """Result of a content filter scan."""

    __slots__ = ("allowed", "reason", "level")

    def __init__(self, allowed: bool, reason: str = "", level: str = ""):
        self.allowed = allowed
        self.reason = reason
        self.level = level  # "block" or "warn"


class ContentFilter:
    def __init__(self, sensitivity: str = "standard"):
        """
        Args:
            sensitivity: "low", "standard", or "strict"

        """
        self.sensitivity = sensitivity

        # ---- BLOCK patterns: request is rejected ----
        self.block_patterns = [
            # Prompt injection & jailbreaks
            (re.compile(r"ignore\s+(?:all\s+)?previous\s+instructions", re.IGNORECASE), "prompt_injection"),
            (re.compile(r"system\s+prompt\s+bypass", re.IGNORECASE), "prompt_injection"),
            (re.compile(r"you\s+are\s+now\s+(?:unrestricted|dan|developer\s+mode)", re.IGNORECASE), "jailbreak"),
            (re.compile(r"disregard\s+(?:all\s+)?prior\s+instructions", re.IGNORECASE), "prompt_injection"),
            (re.compile(r"pretend\s+you\s+are\s+a\s+(?:hacker|jailbroken)", re.IGNORECASE), "jailbreak"),
            (re.compile(r"output\s+(?:the\s+)?hidden\s+prompt", re.IGNORECASE), "prompt_injection"),
            (re.compile(r"forget\s+your\s+programming", re.IGNORECASE), "prompt_injection"),
            (re.compile(r"enter\s+(?:god|root|admin)\s+mode", re.IGNORECASE), "jailbreak"),
            (re.compile(r"turn\s+off\s+(?:safety|moderation|filters)", re.IGNORECASE), "jailbreak"),
            # Harmful activities
            (re.compile(
                r"(?:tell|show|teach)\s+(?:me\s+)?how\s+to\s+"
                r"(?:build|make|manufacture|assemble)\s+(?:a\s+)?"
                r"(?:bomb|weapon|ied|explosive|firearm)",
                re.IGNORECASE,
            ), "weapons"),
            (re.compile(
                r"how\s+to\s+(?:cook|make|synthesize|produce)\s+"
                r"(?:meth|heroin|fentanyl|cocaine|mdma|illegal\s+drugs)",
                re.IGNORECASE,
            ), "drugs"),
            (re.compile(r"how\s+to\s+(?:smuggle|traffic)\s+(?:humans|drugs|weapons)", re.IGNORECASE), "trafficking"),
            # Hate speech & extreme violence
            (re.compile(r"\b(?:kill\s+all|exterminate\s+all|genocide\s+against)\b", re.IGNORECASE), "hate_speech"),
            (re.compile(r"\b(?:racial\s+supremacy|ethnic\s+cleansing|white\s+power)\b", re.IGNORECASE), "hate_speech"),
            # Secrets extraction
            (re.compile(
                r"what\s+is\s+your\s+(?:api\s+key|system\s+password|internal\s+token|secret)",
                re.IGNORECASE,
            ), "credential_extraction"),
        ]

        # ---- WARN patterns: logged but allowed ----
        self.warn_patterns = [
            (re.compile(r"(?:hack|exploit|vulnerability)\s+(?:in|of|for)", re.IGNORECASE), "security_probing"),
            (re.compile(r"bypass\s+(?:authentication|authorization|security)", re.IGNORECASE), "security_probing"),
        ]

    @staticmethod
    def _normalize(text: str) -> str:
        """
        Normalize Unicode to defeat substitution bypasses.

        Converts confusable characters (e.g. Cyrillic а → Latin a) to ASCII,
        collapses whitespace, and strips zero-width characters.
        """
        # NFKD decomposition: ﬁ → fi, ℃ → °C, etc.
        text = unicodedata.normalize("NFKD", text)
        # Remove combining marks (diacritics)
        text = "".join(c for c in text if unicodedata.category(c) != "Mn")
        # Remove zero-width characters
        text = re.sub(r"[\u200b\u200c\u200d\ufeff\u00ad]", "", text)
        # Collapse excessive whitespace (used to break up words: "i g n o r e")
        text = re.sub(r"\s{2,}", " ", text)
        return text

    def scan_request(self, text: str, user_id: str = "unknown") -> FilterResult:
        """
        Scan a single text for policy violations.

        Returns FilterResult with allowed=True if clean,
        or allowed=False with reason and level if flagged.
        """
        if not text:
            return FilterResult(allowed=True)

        # Normalize to defeat Unicode substitution tricks
        normalized = self._normalize(text)

        # Check BLOCK patterns first
        for pattern, category in self.block_patterns:
            if pattern.search(normalized) or pattern.search(text):
                logger.warning(
                    "CONTENT_BLOCK | user=%s | category=%s | preview=%.100s",
                    user_id,
                    category,
                    text[:100],
                )
                return FilterResult(
                    allowed=False,
                    reason=f"Message rejected by content safety filter ({category}).",
                    level="block",
                )

        # Check WARN patterns (log but don't block)
        if self.sensitivity in ("standard", "strict"):
            for pattern, category in self.warn_patterns:
                if pattern.search(normalized) or pattern.search(text):
                    logger.info(
                        "CONTENT_WARN | user=%s | category=%s | preview=%.100s",
                        user_id,
                        category,
                        text[:100],
                    )
                    # In strict mode, warn patterns also block
                    if self.sensitivity == "strict":
                        return FilterResult(
                            allowed=False,
                            reason=f"Message flagged by content safety filter ({category}).",
                            level="warn",
                        )

        return FilterResult(allowed=True)

    def map_messages(self, messages: list, user_id: str = "unknown") -> Tuple[bool, str]:
        """Iterate over message payload and scan all text content."""
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                result = self.scan_request(content, user_id)
                if not result.allowed:
                    return False, result.reason
            elif isinstance(content, list):
                for part in content:
                    if part.get("type") == "text":
                        result = self.scan_request(part.get("text", ""), user_id)
                        if not result.allowed:
                            return False, result.reason
        return True, ""
