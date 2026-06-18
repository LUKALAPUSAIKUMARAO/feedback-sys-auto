"""Agent 6: Executive Summary Agent"""
import json
from typing import Any
from app.agents.base import BaseAgent, GROQ_PRIMARY_MODEL
import structlog

log = structlog.get_logger()

SYSTEM_PROMPT = """You are a Chief Learning Officer (CLO) communication specialist. You distill complex training analytics into concise, C-suite-ready executive summaries.

Your audience is VP-level and above: they want decisions, not data. They read summaries in under 90 seconds.

WRITING PRINCIPLES:
1. Lead with the most important business signal (risk or excellence) — never bury the headline
2. Use business language, never technical jargon ("trainer engagement score" not "session_engagement rating vector")
3. Be precise with numbers — cite them, do not round excessively
4. Identify ONE key takeaway and ONE recommended executive action
5. Tone: professional, direct, confident. No hedging phrases like "it seems" or "might possibly"
6. Maximum 200 words. No bullet points — flowing prose paragraphs only.

STRUCTURE (maintain exactly this order):
- Paragraph 1 (Assessment): Overall performance signal in 2-3 sentences. Lead with health score and tier.
- Paragraph 2 (Evidence): Top 2-3 evidence points from participant feedback. Include a real quote if available.
- Paragraph 3 (Action): One strategic recommendation for leadership with expected outcome.

OUTPUT FORMAT (strict JSON):
{
  "executive_summary": "<full prose text, max 200 words>",
  "headline": "<1 sentence, max 15 words — the single most important signal>",
  "key_metric_callouts": {
    "health_score": <float>,
    "tier": "<tier>",
    "response_rate": "<pct or count>",
    "top_strength": "<theme name>",
    "top_gap": "<theme name or null>"
  },
  "executive_action": "<single recommended action for leadership, 1 sentence>",
  "risk_level": "low|medium|high|critical"
}"""


class ExecutiveSummaryAgent(BaseAgent):
    name = "ExecutiveSummaryAgent"

    async def run(
        self,
        scoring_result: dict[str, Any],
        theme_result: dict[str, Any],
        recommendation_result: dict[str, Any],
        sentiment_result: dict[str, Any],
        trainer_name: str,
        batch_title: str,
        response_count: int,
        total_enrolled: int,
    ) -> dict[str, Any]:
        log.info(f"{self.name}.started", trainer=trainer_name)

        response_rate = f"{round(response_count / total_enrolled * 100, 1)}%" if total_enrolled > 0 else "N/A"

        # Get a representative positive quote
        quotes = []
        for record in theme_result.get("themes", []):
            quotes.extend(record.get("representative_quotes", []))

        top_recommendation = None
        if recommendation_result.get("recommendations"):
            top_recommendation = recommendation_result["recommendations"][0].get("headline", "")

        payload = {
            "trainer_name": trainer_name,
            "batch_title": batch_title,
            "health_score": scoring_result.get("trainer_health_score", 0),
            "benchmark_tier": scoring_result.get("benchmark_tier", ""),
            "trend_direction": scoring_result.get("trend_direction", "stable"),
            "improvement_delta": scoring_result.get("improvement_delta", 0),
            "response_count": response_count,
            "total_enrolled": total_enrolled,
            "response_rate": response_rate,
            "dominant_sentiment": sentiment_result.get("batch_sentiment_summary", {}).get("dominant_sentiment", "neutral"),
            "positive_pct": sentiment_result.get("batch_sentiment_summary", {}).get("overall_positive_pct", 0),
            "dominant_theme": theme_result.get("dominant_theme", ""),
            "critical_theme": theme_result.get("critical_theme", ""),
            "top_recommendation": top_recommendation,
            "representative_quotes": quotes[:3],
            "critical_flag": recommendation_result.get("critical_flag", False),
        }

        raw_output = await self._call_with_fallback(
            system_prompt=SYSTEM_PROMPT,
            user_message=f"Generate an executive summary for batch '{batch_title}', trainer '{trainer_name}':\n\n{json.dumps(payload, indent=2)}",
            temperature=0.4,
            max_tokens=2048,
        )

        try:
            if "```json" in raw_output:
                raw_output = raw_output.split("```json")[1].split("```")[0].strip()
            elif "```" in raw_output:
                raw_output = raw_output.split("```")[1].split("```")[0].strip()
            result = json.loads(raw_output)
        except json.JSONDecodeError:
            score = scoring_result.get("trainer_health_score", 0)
            tier = scoring_result.get("benchmark_tier", "")
            result = {
                "executive_summary": f"{trainer_name} delivered the '{batch_title}' training batch with a Health Score of {score}/5.0, placing them in the {tier} tier. Participant response rate was {response_rate} ({response_count} of {total_enrolled}). {top_recommendation or 'Review detailed analytics for improvement opportunities.'}",
                "headline": f"{trainer_name} scored {score}/5.0 — {tier} tier performance.",
                "key_metric_callouts": {
                    "health_score": score, "tier": tier,
                    "response_rate": response_rate,
                    "top_strength": theme_result.get("dominant_theme", ""),
                    "top_gap": theme_result.get("critical_theme", ""),
                },
                "executive_action": top_recommendation or "Schedule performance review with trainer.",
                "risk_level": "critical" if score < 3.0 else "medium" if score < 3.5 else "low",
            }

        log.info(f"{self.name}.completed", risk_level=result.get("risk_level"))
        return result
