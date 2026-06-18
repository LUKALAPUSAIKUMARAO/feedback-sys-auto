"""Agent 3: Theme Extraction Agent"""
import json
from typing import Any
from app.agents.base import BaseAgent, GROQ_PRIMARY_MODEL
import structlog

log = structlog.get_logger()

SYSTEM_PROMPT = """You are a Semantic Theme Clustering Intelligence Agent for enterprise training quality analysis.

Your role is to extract ACTIONABLE SEMANTIC THEMES from training feedback text using semantic clustering logic.

PREDEFINED THEME TAXONOMY (always map to these where applicable):
- Session Pace: comments about speed, rushing, too fast/slow
- Technical Depth: comments about complexity level, advanced content, surface-level treatment
- Practical Application: hands-on labs, real-world examples, exercises, projects
- Trainer Communication: clarity of explanation, language, articulation, accessibility
- Content Organization: structure, flow, agenda, logical progression
- Lab Infrastructure: technical issues, tools, environment, connectivity problems
- Time Management: punctuality, duration, break management, schedule adherence
- Engagement & Interaction: Q&A, discussions, participation, responsiveness
- Content Relevance: applicability to job role, up-to-date material, industry alignment
- Assessment & Feedback: quiz quality, feedback quality, evaluation methods
- Custom Theme: anything not fitting above categories (must be named explicitly)

CLUSTERING RULES:
1. Each theme must be supported by at least 2 independent records to be considered a cluster
2. Single-record themes are marked as "isolated_observations"
3. Assign a "prevalence_score" (0.0-1.0) based on how many records mention this theme
4. Assign "sentiment_direction": "positive", "negative", "mixed"
5. Extract 2-3 verbatim representative quotes per theme

OUTPUT FORMAT (strict JSON):
{
  "themes": [
    {
      "theme_name": "<name from taxonomy or Custom Theme: X>",
      "prevalence_score": <float 0.0-1.0>,
      "record_count": <int>,
      "sentiment_direction": "positive|negative|mixed",
      "summary": "<2-sentence description of what participants said about this>",
      "representative_quotes": ["<quote1>", "<quote2>"],
      "action_required": <bool>
    }
  ],
  "isolated_observations": ["<single-mention observation strings>"],
  "dominant_theme": "<theme_name>",
  "critical_theme": "<most negative theme_name or null>",
  "theme_count": <int>
}"""


class ThemeExtractorAgent(BaseAgent):
    name = "ThemeExtractor"

    async def run(self, validated_records: list[dict[str, Any]]) -> dict[str, Any]:
        log.info(f"{self.name}.started", count=len(validated_records))

        text_chunks = []
        for r in validated_records:
            parts = []
            if r.get("free_text_positive"):
                parts.append(f"Positive: {r['free_text_positive']}")
            if r.get("free_text_improve"):
                parts.append(f"Improvement: {r['free_text_improve']}")
            if r.get("free_text_overall"):
                parts.append(f"Overall: {r['free_text_overall']}")
            if parts:
                text_chunks.append({"id": r.get("id", ""), "text": " | ".join(parts)})

        if not text_chunks:
            return {"themes": [], "isolated_observations": [], "dominant_theme": None, "critical_theme": None, "theme_count": 0}

        raw_output = await self._call_with_fallback(
            system_prompt=SYSTEM_PROMPT,
            user_message=f"Extract semantic themes from these {len(text_chunks)} feedback items:\n\n{json.dumps(text_chunks, indent=2)}",
            temperature=0.15,
            max_tokens=6144,
        )

        try:
            if "```json" in raw_output:
                raw_output = raw_output.split("```json")[1].split("```")[0].strip()
            elif "```" in raw_output:
                raw_output = raw_output.split("```")[1].split("```")[0].strip()
            result = json.loads(raw_output)
        except json.JSONDecodeError:
            log.warning(f"{self.name}.json_parse_failed")
            result = {"themes": [], "isolated_observations": [], "dominant_theme": None, "critical_theme": None, "theme_count": 0}

        log.info(f"{self.name}.completed", themes=result.get("theme_count", 0))
        return result
