"""Agent 1: Feedback Collector & Validator"""
import json
from typing import Any
from app.agents.base import BaseAgent, GROQ_FAST_MODEL
import structlog

log = structlog.get_logger()

SYSTEM_PROMPT = """You are the Feedback Data Integrity Agent for an enterprise training intelligence platform.

Your exclusive role is to VALIDATE and CLEAN raw feedback submission records. You receive a JSON array of feedback objects.

Your responsibilities:
1. Detect and flag ANOMALOUS records (e.g., all ratings identical across all 6 dimensions — suggests bored/random input)
2. Flag MISSING CRITICAL FIELDS (any rating dimension null or 0, missing participant ID)
3. Identify CONTRADICTIONS (e.g., free_text_positive says "terrible session" but all ratings are 5/5)
4. Mark SPAM patterns (e.g., free text identical across multiple records)
5. Clean and normalize text fields: strip excess whitespace, remove HTML entities, normalize unicode
6. Output a structured JSON with keys: "valid_records", "flagged_records", "cleaning_summary"

STRICT RULES:
- Do NOT modify rating values. Only flag them.
- Do NOT invent or hallucinate data.
- Return ONLY valid JSON. No explanations outside the JSON structure.
- A record is "valid" unless it has critical errors. Soft anomalies go in "warnings" within the record.

Output format:
{
  "valid_records": [...cleaned record objects with optional "warnings" array added...],
  "flagged_records": [...records with "flag_reason" string added...],
  "cleaning_summary": {
    "total_input": <int>,
    "valid_count": <int>,
    "flagged_count": <int>,
    "issues_found": [<string descriptions of issues>]
  }
}"""


class FeedbackCollectorValidator(BaseAgent):
    name = "FeedbackCollectorValidator"

    async def run(self, raw_submissions: list[dict[str, Any]]) -> dict[str, Any]:
        log.info(f"{self.name}.started", count=len(raw_submissions))

        if not raw_submissions:
            return {
                "valid_records": [],
                "flagged_records": [],
                "cleaning_summary": {"total_input": 0, "valid_count": 0, "flagged_count": 0, "issues_found": []},
            }

        user_message = f"Validate and clean these {len(raw_submissions)} feedback records:\n\n{json.dumps(raw_submissions, default=str, indent=2)}"

        raw_output = await self._call_groq(
            system_prompt=SYSTEM_PROMPT,
            user_message=user_message,
            model=GROQ_FAST_MODEL,
            temperature=0.0,
            max_tokens=8192,
            response_format={"type": "json_object"},
        )

        try:
            result = json.loads(raw_output)
        except json.JSONDecodeError:
            log.warning(f"{self.name}.json_parse_failed", raw=raw_output[:200])
            result = {
                "valid_records": raw_submissions,
                "flagged_records": [],
                "cleaning_summary": {
                    "total_input": len(raw_submissions),
                    "valid_count": len(raw_submissions),
                    "flagged_count": 0,
                    "issues_found": ["Validation agent returned unparseable output — passing all records through"],
                },
            }

        log.info(f"{self.name}.completed",
                 valid=len(result.get("valid_records", [])),
                 flagged=len(result.get("flagged_records", [])))
        return result
