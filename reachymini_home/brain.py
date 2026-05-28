"""Doubao Brain - Intent parsing module."""

import json
import logging
import re
from dataclasses import dataclass
from typing import Optional

import httpx

import config
BRAIN_CONFIG = config.BRAIN_CONFIG
SYSTEM_PROMPT = config.SYSTEM_PROMPT

logger = logging.getLogger(__name__)


@dataclass
class IntentResult:
    """Result from intent parsing."""

    reply: str
    device_command: str
    raw_output: str


class DoubaoBrain:
    """Doubao LLM for intent parsing."""

    def __init__(self, provider: str = "doubao"):
        """Initialize brain with provider."""
        self.provider = provider
        self.cfg = BRAIN_CONFIG[self.provider]

    async def query(self, user_input: str) -> IntentResult:
        """Query the brain with user input."""
        if self.provider == "doubao":
            return await self._query_doubao(user_input)
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

    async def _query_doubao(self, user_input: str) -> IntentResult:
        """Query Doubao LLM."""
        headers = {
            "Authorization": f"Bearer {self.cfg['api_key']}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.cfg["model"],
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_input},
            ],
            "temperature": 0.3,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.cfg['base_url']}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            raw = data["choices"][0]["message"]["content"]
            return self._parse_response(raw)

    def _parse_response(self, raw: str) -> IntentResult:
        """Parse LLM response to IntentResult."""
        json_str = self._extract_json(raw)
        try:
            parsed = json.loads(json_str)
            reply = parsed.get("reply", "")
            device_command = parsed.get("device_command", "NONE")
            return IntentResult(reply=reply, device_command=device_command, raw_output=raw)
        except json.JSONDecodeError as e:
            return IntentResult(
                reply=f"[JSON Parse Error: {e}]",
                device_command="NONE",
                raw_output=raw,
            )

    def _extract_json(self, text: str) -> str:
        """Extract JSON object from text."""
        text = text.strip()
        text = re.sub(r"^```json\s*", "", text)
        text = re.sub(r"^```\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()
        if text.startswith("{") and text.endswith("}"):
            return text
        match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text)
        if match:
            return match.group(0)
        return "{}"
