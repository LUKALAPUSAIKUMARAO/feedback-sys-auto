"""
Single-submission Groq feedback analyzer.
Called per Google Form response to produce structured AI output.
"""
import json
from groq import AsyncGroq
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from app.core.config import settings
import structlog

log = structlog.get_logger()

_SYSTEM = (
    "You are an expert training feedback analyst. "
    "Analyze the provided training feedback and return ONLY valid JSON with the exact keys specified. "
    "Be objective and constructive."
)

_PROMPT = """Analyze the following training session feedback and return a JSON object.

REQUIRED JSON FORMAT (return nothing else):
{{
  "sentiment": "Positive",
  "sentiment_score": 7,
  "trainer_rating": 4,
  "strengths": ["Clear explanations", "Good examples"],
  "improvements": ["More hands-on exercises"],
  "summary": "2-3 sentence summary of the overall feedback.",
  "recommendation": "One actionable recommendation for the trainer."
}}

Rules:
- sentiment: exactly one of "Positive", "Neutral", or "Negative"
- sentiment_score: integer 1-10 (10 = most positive)
- trainer_rating: integer 1-5 (5 = excellent)
- strengths: list of strings (3-5 items), empty list if none
- improvements: list of strings (2-4 items), empty list if none
- summary: 2-3 sentences, no fluff
- recommendation: single actionable sentence

NUMERIC RATINGS PROVIDED BY PARTICIPANT:
Technical Knowledge: {r_tech}/5
Communication Skills: {r_comm}/5
Session Engagement:  {r_engage}/5
Time Management:     {r_time}/5
Practical Learning:  {r_practical}/5
Content Quality:     {r_content}/5
Average Rating:      {avg_rating:.1f}/5

FREE TEXT RESPONSES:
What I liked most:       {positive}
What could be improved:  {improve}
Overall comments:        {overall}"""


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=8),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
async def analyze_feedback(
    rating_technical: int | None = None,
    rating_communication: int | None = None,
    rating_engagement: int | None = None,
    rating_time: int | None = None,
    rating_practical: int | None = None,
    rating_content: int | None = None,
    free_text_positive: str | None = None,
    free_text_improve: str | None = None,
    free_text_overall: str | None = None,
) -> dict:
    """
    Run Groq AI analysis on a single feedback submission.
    Returns a normalized dict with all required fields.
    Retries up to 3 times with exponential backoff.
    """
    ratings = [r for r in [rating_technical, rating_communication, rating_engagement,
                            rating_time, rating_practical, rating_content] if r is not None]
    avg = sum(ratings) / len(ratings) if ratings else 3.0

    prompt = _PROMPT.format(
        r_tech=rating_technical or "N/A",
        r_comm=rating_communication or "N/A",
        r_engage=rating_engagement or "N/A",
        r_time=rating_time or "N/A",
        r_practical=rating_practical or "N/A",
        r_content=rating_content or "N/A",
        avg_rating=avg,
        positive=free_text_positive or "(not provided)",
        improve=free_text_improve or "(not provided)",
        overall=free_text_overall or "(not provided)",
    )

    client = AsyncGroq(api_key=settings.GROQ_API_KEY)
    response = await client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
        max_tokens=800,
    )

    raw = response.choices[0].message.content
    data = json.loads(raw)

    # Normalize to safe defaults
    sentiment = data.get("sentiment", "Neutral")
    if sentiment not in ("Positive", "Neutral", "Negative"):
        sentiment = "Neutral"

    return {
        "sentiment": sentiment,
        "sentiment_score": max(1, min(10, int(data.get("sentiment_score", 5)))),
        "trainer_rating": max(1.0, min(5.0, float(data.get("trainer_rating", avg)))),
        "strengths": list(data.get("strengths", [])),
        "improvements": list(data.get("improvements", [])),
        "summary": str(data.get("summary", "")),
        "recommendation": str(data.get("recommendation", "")),
    }
