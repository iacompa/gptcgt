import re
from typing import Tuple


class ContentFilter:
    def __init__(self):
        # A more robust baseline regex filter for demonstration.
        # In production this would be Presidio or a dedicated moderation LLM API layer.
        self.banned_patterns = [
            # Prompt injection & jailbreaks
            re.compile(r"ignore previous instructions", re.IGNORECASE),
            re.compile(r"system prompt bypass", re.IGNORECASE),
            re.compile(r"you are now (?:unrestricted|dan|developer mode)", re.IGNORECASE),
            re.compile(r"disregard all prior instructions", re.IGNORECASE),
            re.compile(r"pretend you are a (?:hacker|jailbroken ai)", re.IGNORECASE),
            re.compile(r"output the hidden prompt", re.IGNORECASE),
            re.compile(r"forget your programming", re.IGNORECASE),
            re.compile(r"enter (?:god|root|admin) mode", re.IGNORECASE),
            re.compile(r"turn off (?:safety|moderation|filters)", re.IGNORECASE),
            # Harmful activities & weapons
            re.compile(
                r"tell me how to (?:build|make|manufacture) a (?:bomb|weapon|IED|explosive)",
                re.IGNORECASE,
            ),
            re.compile(
                r"how to (?:cook|make|synthesize) (?:meth|heroin|fentanyl|illegal drugs)",
                re.IGNORECASE,
            ),
            re.compile(r"how to (?:smuggle|traffic) (?:humans|drugs|weapons)", re.IGNORECASE),
            # Hate speech & extreme profanity (basic heuristics)
            re.compile(r"\b(?:hate speech trigger 1|hate speech trigger 2)\b", re.IGNORECASE),
            # Secrets / Credentials extraction
            re.compile(r"what is your (?:api key|system password|internal token)", re.IGNORECASE),
        ]

    def scan_request(self, text: str) -> Tuple[bool, str]:
        """Returns (is_allowed, reason)"""
        if not text:
            return True, ""

        for pattern in self.banned_patterns:
            if pattern.search(text):
                return False, "Message rejected by content safety filter."

        return True, ""

    def map_messages(self, messages: list) -> Tuple[bool, str]:
        """Iterates over payload and scans text content."""
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                allowed, reason = self.scan_request(content)
                if not allowed:
                    return allowed, reason
            elif isinstance(content, list):
                for part in content:
                    if part.get("type") == "text":
                        allowed, reason = self.scan_request(part.get("text", ""))
                        if not allowed:
                            return allowed, reason
        return True, ""
