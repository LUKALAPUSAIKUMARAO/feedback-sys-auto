"""Agent 2: Sentiment Analyzer"""
import json
from typing import Any
from app.agents.base import BaseAgent, GROQ_PRIMARY_MODEL
import structlog

log = structlog.get_logger()

SYSTEM_PROMPT = """You are an Enterprise Sentiment Intelligence Analyst specializing in B2B training feedback analysis.

Your role is to perform GRANULAR, PRECISE sentiment analysis on free-text training feedback. You are NOT a general-purpose chatbot.

INPUT: A JSON array of feedback records, each containing free_text_positive, free_text_improve, free_text_overall fields.

YOUR ANALYSIS MUST:
1. Assign a compound sentiment label per record: "positive", "negative", or "neutral"
2. Assign a numerical sentiment score between -1.0 (most negative) and +1.0 (most positive) with 4 decimal precision
3. Break down sentiment by TEXT FIELD (positive section, improvement section, overall section) with individual labels
4. Identify EMOTIONAL INTENSITY: "low", "medium", "high" based on linguistic markers (exclamation, strong adjectives, etc.)
5. Flag records with MIXED SENTIMENT (positive text but low ratings, or vice versa)
6. Detect SARCASM MARKERS with confidence 0.0-1.0

SCORING ALGORITHM:
- Base score from TextBlob-style polarity analysis
- Adjust for training-specific vocabulary: "boring", "irrelevant", "confused" = strong negative signals
- "hands-on", "practical", "engaged", "clear" = strong positive signals
- "okay", "fine", "average" = neutral signals
- Weight: free_text_overall (40%) + free_text_positive (30%) + free_text_improve (30%)

OUTPUT FORMAT (strict JSON):
{
  "analyzed_records": [
    {
      "submission_id": "<id>",
      "sentiment_label": "positive|negative|neutral",
      "sentiment_score": <float -1.0 to 1.0>,
      "field_breakdown": {
        "positive_section": {"label": "...", "score": <float>},
        "improvement_section": {"label": "...", "score": <float>},
        "overall_section": {"label": "...", "score": <float>}
      },
      "emotional_intensity": "low|medium|high",
      "mixed_sentiment_flag": <bool>,
      "sarcasm_probability": <float 0.0-1.0>,
      "key_phrases": ["<phrase1>", "<phrase2>"]
    }
  ],
  "batch_sentiment_summary": {
    "overall_positive_pct": <float>,
    "overall_negative_pct": <float>,
    "overall_neutral_pct": <float>,
    "avg_sentiment_score": <float>,
    "dominant_sentiment": "positive|negative|neutral",
    "high_intensity_count": <int>
  }
}"""


class SentimentAnalyzerAgent(BaseAgent):
    name = "SentimentAnalyzer"

    async def run(self, validated_records: list[dict[str, Any]]) -> dict[str, Any]:
        log.info(f"{self.name}.started", count=len(validated_records))

        text_records = [
            {
                "submission_id": r.get("id", r.get("submission_id", "unknown")),
                "free_text_positive": r.get("free_text_positive") or "",
                "free_text_improve": r.get("free_text_improve") or "",
                "free_text_overall": r.get("free_text_overall") or "",
            }
            for r in validated_records
            if any([r.get("free_text_positive"), r.get("free_text_improve"), r.get("free_text_overall")])
        ]

        if not text_records:
            log.info(f"{self.name}.no_text_to_analyze")
            return {
                "analyzed_records": [],
                "batch_sentiment_summary": {
                    "overall_positive_pct": 0, "overall_negative_pct": 0,
                    "overall_neutral_pct": 100, "avg_sentiment_score": 0.0,
                    "dominant_sentiment": "neutral", "high_intensity_count": 0,
                },
            }

        raw_output = await self._call_with_fallback(
            system_prompt=SYSTEM_PROMPT,
            user_message=f"Analyze sentiment for these {len(text_records)} feedback records:\n\n{json.dumps(text_records, indent=2)}",
            temperature=0.1,
            max_tokens=8192,
        )

        try:
            # Extract JSON from potential markdown fencing
            if "```json" in raw_output:
                raw_output = raw_output.split("```json")[1].split("```")[0].strip()
            elif "```" in raw_output:
                raw_output = raw_output.split("```")[1].split("```")[0].strip()
            result = json.loads(raw_output)
        except json.JSONDecodeError:
            log.warning(f"{self.name}.json_parse_failed")
            result = {
                "analyzed_records": [],
                "batch_sentiment_summary": {
                    "overall_positive_pct": 0, "overall_negative_pct": 0,
                    "overall_neutral_pct": 100, "avg_sentiment_score": 0.0,
                    "dominant_sentiment": "neutral", "high_intensity_count": 0,
                },
            }

        log.info(f"{self.name}.completed", analyzed=len(result.get("analyzed_records", [])))
        return result
