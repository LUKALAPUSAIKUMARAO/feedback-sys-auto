"""Agent 5: Recommendation Agent"""
import json
from typing import Any
from app.agents.base import BaseAgent, GROQ_PRIMARY_MODEL
import structlog

log = structlog.get_logger()

SYSTEM_PROMPT = """You are an Elite Training Excellence Advisor for a B2B enterprise learning platform.

Your role is to generate EXACTLY 3-5 high-priority, hyper-specific, actionable recommendations for a trainer based on their performance analysis data.

RECOMMENDATION PRINCIPLES:
1. SPECIFICITY: Never generic advice ("improve communication"). Always root to evidence ("Participants flagged unclear transitions between Lab A and B — implement 60-second recap slides")
2. PRIORITY: Rank by IMPACT × URGENCY. Flag one as "CRITICAL" if score < 3.0, one as "QUICK WIN" if fixable in next session
3. MAPPING: Each recommendation must map to a specific identified gap theme
4. EVIDENCE: Each recommendation cites the data that motivated it (e.g., "73% of respondents mentioned...")
5. TIMELINE: Suggest implementation horizon: "Immediate (next session)", "Short-term (1-2 months)", "Strategic (3-6 months)"

CATEGORIES to draw from:
- Content Redesign (restructure material depth or sequence)
- Delivery Technique (pacing, pause usage, visual aids)
- Interaction Enhancement (more Q&A time, breakout exercises)
- Technical Environment (lab stability, tool setup time)
- Time Optimization (agenda restructuring, buffer zones)
- Pre-Session Preparation (participant prerequisites, advance materials)

OUTPUT FORMAT (strict JSON, EXACTLY 3-5 items):
{
  "recommendations": [
    {
      "priority_rank": 1,
      "priority_tag": "CRITICAL|HIGH|QUICK WIN|STRATEGIC",
      "category": "<category from list>",
      "headline": "<max 10-word action title>",
      "detail": "<2-3 sentence specific action with evidence citation>",
      "mapped_gap_theme": "<theme name>",
      "evidence": "<data point or participant quote supporting this>",
      "implementation_horizon": "Immediate|Short-term|Strategic",
      "expected_score_impact": "<estimated score improvement, e.g. +0.3 to +0.5>"
    }
  ],
  "critical_flag": <bool>,
  "immediate_action_required": <bool>,
  "recommendation_confidence": <float 0.0-1.0>
}"""


class RecommendationAgent(BaseAgent):
    name = "RecommendationAgent"

    async def run(
        self,
        scoring_result: dict[str, Any],
        theme_result: dict[str, Any],
        sentiment_result: dict[str, Any],
        trainer_name: str = "the trainer",
    ) -> dict[str, Any]:
        log.info(f"{self.name}.started", trainer=trainer_name)

        payload = {
            "trainer_name": trainer_name,
            "health_score": scoring_result.get("trainer_health_score", 0),
            "benchmark_tier": scoring_result.get("benchmark_tier", ""),
            "improvement_delta": scoring_result.get("improvement_delta", 0),
            "trend_direction": scoring_result.get("trend_direction", "stable"),
            "weakest_dimensions": sorted(
                scoring_result.get("weighted_dimension_scores", {}).items(),
                key=lambda x: x[1]
            )[:3],
            "negative_themes": [t for t in theme_result.get("themes", []) if t.get("sentiment_direction") == "negative"],
            "critical_theme": theme_result.get("critical_theme"),
            "sentiment_summary": sentiment_result.get("batch_sentiment_summary", {}),
            "response_count": scoring_result.get("response_count", 0),
        }

        raw_output = await self._call_with_fallback(
            system_prompt=SYSTEM_PROMPT,
            user_message=f"Generate 3-5 recommendations for {trainer_name} based on:\n\n{json.dumps(payload, indent=2)}",
            temperature=0.3,
            max_tokens=4096,
        )

        try:
            if "```json" in raw_output:
                raw_output = raw_output.split("```json")[1].split("```")[0].strip()
            elif "```" in raw_output:
                raw_output = raw_output.split("```")[1].split("```")[0].strip()
            result = json.loads(raw_output)
        except json.JSONDecodeError:
            log.warning(f"{self.name}.json_parse_failed")
            result = {
                "recommendations": [
                    {
                        "priority_rank": 1,
                        "priority_tag": "HIGH",
                        "category": "Delivery Technique",
                        "headline": "Review participant feedback and address key gaps",
                        "detail": "Analysis indicated performance gaps that require attention. Review individual feedback responses for specific actionable items.",
                        "mapped_gap_theme": "General",
                        "evidence": f"Health score: {scoring_result.get('trainer_health_score', 0)}",
                        "implementation_horizon": "Immediate",
                        "expected_score_impact": "+0.2 to +0.4",
                    }
                ],
                "critical_flag": scoring_result.get("trainer_health_score", 5) < 3.0,
                "immediate_action_required": False,
                "recommendation_confidence": 0.5,
            }

        log.info(f"{self.name}.completed", recs=len(result.get("recommendations", [])))
        return result
