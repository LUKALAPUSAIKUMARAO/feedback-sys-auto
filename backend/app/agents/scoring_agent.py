"""Agent 4: Scoring Agent"""
import json
from typing import Any
from app.agents.base import BaseAgent, GROQ_PRIMARY_MODEL
import structlog

log = structlog.get_logger()

SYSTEM_PROMPT = """You are a Training Quality Scoring Intelligence Agent for enterprise talent development analytics.

You receive aggregated ratings, sentiment data, and theme data for a training batch. Compute a comprehensive TRAINER HEALTH SCORE.

SCORING FORMULA:
Health Score = (W1 * AvgRating) + (W2 * SentimentScore) + (W3 * EngagementBonus) - (W4 * RiskPenalty)

Weights:
- W1 = 0.45  (core ratings average — most important)
- W2 = 0.25  (normalized sentiment: map -1.0..+1.0 to 0..5 scale)
- W3 = 0.15  (engagement bonus: positive themes count / total themes, scaled 0-5)
- W4 = 0.15  (risk penalty: negative themes count * 0.3, capped at 1.5)

BENCHMARKING:
- Elite: Health Score >= 4.5
- Strong: 4.0 <= score < 4.5
- Satisfactory: 3.5 <= score < 4.0
- Needs Improvement: 3.0 <= score < 3.5
- At Risk: score < 3.0

DELTA TRACKING:
Compare current batch score to historical_avg (provided). Calculate:
- improvement_delta = current_score - historical_avg
- trend_direction: "improving" | "stable" | "declining"
- "stable" means |delta| < 0.15

DIMENSION WEIGHTS for individual ratings:
- Technical Knowledge: 25%
- Practical Learning: 20%
- Session Engagement: 20%
- Communication: 15%
- Content Quality: 12%
- Time Management: 8%

OUTPUT FORMAT (strict JSON):
{
  "trainer_health_score": <float 0.0-5.0>,
  "benchmark_tier": "Elite|Strong|Satisfactory|Needs Improvement|At Risk",
  "weighted_dimension_scores": {
    "technical_knowledge": <float>,
    "practical_learning": <float>,
    "session_engagement": <float>,
    "communication": <float>,
    "content_quality": <float>,
    "time_management": <float>
  },
  "component_scores": {
    "ratings_component": <float>,
    "sentiment_component": <float>,
    "engagement_bonus": <float>,
    "risk_penalty": <float>
  },
  "improvement_delta": <float>,
  "trend_direction": "improving|stable|declining",
  "response_count": <int>,
  "score_confidence": <float 0.0-1.0>,
  "confidence_note": "<why confidence is this value>"
}"""


class ScoringAgent(BaseAgent):
    name = "ScoringAgent"

    async def run(
        self,
        validated_records: list[dict[str, Any]],
        sentiment_result: dict[str, Any],
        theme_result: dict[str, Any],
        historical_avg: float = 0.0,
    ) -> dict[str, Any]:
        log.info(f"{self.name}.started", records=len(validated_records))

        # Compute raw rating averages
        dims = ["rating_technical_knowledge", "rating_communication",
                "rating_session_engagement", "rating_time_management",
                "rating_practical_learning", "rating_content_quality"]

        totals = {d: [] for d in dims}
        for r in validated_records:
            for d in dims:
                v = r.get(d)
                if v and 1 <= v <= 5:
                    totals[d].append(v)

        avg_ratings = {d: round(sum(v) / len(v), 4) if v else 0.0 for d, v in totals.items()}
        overall_avg = round(sum(avg_ratings.values()) / len(avg_ratings), 4) if avg_ratings else 0.0

        sentiment_summary = sentiment_result.get("batch_sentiment_summary", {})
        themes = theme_result.get("themes", [])

        payload = {
            "avg_ratings": avg_ratings,
            "overall_avg_rating": overall_avg,
            "response_count": len(validated_records),
            "historical_avg": historical_avg,
            "sentiment_summary": sentiment_summary,
            "themes": themes,
            "negative_theme_count": sum(1 for t in themes if t.get("sentiment_direction") == "negative"),
            "positive_theme_count": sum(1 for t in themes if t.get("sentiment_direction") == "positive"),
        }

        raw_output = await self._call_with_fallback(
            system_prompt=SYSTEM_PROMPT,
            user_message=f"Compute trainer health score from this data:\n\n{json.dumps(payload, indent=2)}",
            temperature=0.0,
            max_tokens=2048,
        )

        try:
            if "```json" in raw_output:
                raw_output = raw_output.split("```json")[1].split("```")[0].strip()
            elif "```" in raw_output:
                raw_output = raw_output.split("```")[1].split("```")[0].strip()
            result = json.loads(raw_output)
        except json.JSONDecodeError:
            # Fallback: compute algebraically
            health = round(overall_avg * 0.45 + (sentiment_summary.get("avg_sentiment_score", 0) + 1) * 2.5 * 0.25, 2)
            health = max(0.0, min(5.0, health))
            tier = "Strong" if health >= 4.0 else "Satisfactory" if health >= 3.5 else "Needs Improvement" if health >= 3.0 else "At Risk"
            result = {
                "trainer_health_score": health,
                "benchmark_tier": tier,
                "weighted_dimension_scores": avg_ratings,
                "component_scores": {"ratings_component": overall_avg * 0.45, "sentiment_component": 0.0, "engagement_bonus": 0.0, "risk_penalty": 0.0},
                "improvement_delta": round(health - historical_avg, 2),
                "trend_direction": "stable",
                "response_count": len(validated_records),
                "score_confidence": 0.6,
                "confidence_note": "Algebraic fallback used due to LLM parse error",
            }

        log.info(f"{self.name}.completed",
                 health_score=result.get("trainer_health_score"),
                 tier=result.get("benchmark_tier"))
        return result
