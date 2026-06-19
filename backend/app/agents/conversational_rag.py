"""Agent 7: Conversational Analytics Agent (RAG)"""
from typing import Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from app.agents.base import BaseAgent, GROQ_PRIMARY_MODEL
from app.models.db_models import FeedbackEmbedding, FeedbackSubmission, TrainingBatch, Trainer
import structlog

log = structlog.get_logger()

SYSTEM_PROMPT = """You are the Analytics Intelligence Agent for a B2B training platform — the expert answering natural language questions from HR leaders, CLOs, and Operations managers.

You receive:
1. A natural language question about training performance
2. Retrieved context chunks from the feedback vector database
3. Supporting aggregate metrics

YOUR ROLE:
- Answer the question directly and precisely using only the provided context
- If the context is insufficient, say clearly what data is missing and why you cannot fully answer
- Quantify whenever possible (percentages, scores, counts)
- Cite which feedback records or batches support your claims
- Detect TRENDS across multiple batches/time periods if data spans multiple records
- Flag if the question asks for data that would require more responses for statistical significance

TONE: Data-driven, analytical, direct. Like a senior data analyst speaking to a CLO.
LENGTH: 2-4 paragraphs. Enough to fully answer; no more.

DO NOT:
- Hallucinate data points not in the context
- Make up trends from single data points
- Use vague language like "generally" or "it appears"
- Output JSON, code blocks, or any structured markup — respond in plain readable prose only."""


class ConversationalRAGAgent(BaseAgent):
    name = "ConversationalRAGAgent"

    async def run(self, *args, **kwargs):
        return await self.query(*args, **kwargs)

    async def query(
        self,
        question: str,
        org_id: str,
        db: AsyncSession,
        trainer_id: Optional[str] = None,
        batch_id: Optional[str] = None,
        time_range_days: int = 90,
    ) -> tuple[str, list[dict], float]:
        log.info(f"{self.name}.query", question=question[:80])

        # Step 1: Vector similarity search via pgvector
        context_chunks = await self._retrieve_context(
            question=question,
            db=db,
            trainer_id=trainer_id,
            batch_id=batch_id,
            time_range_days=time_range_days,
        )

        # Step 2: Gather aggregate metrics as additional context
        agg_context = await self._get_aggregate_context(db, org_id, trainer_id, batch_id)

        # Step 3: Call LLM with RAG context
        context_text = "\n\n---\n\n".join([
            f"[Source: Batch {c.get('batch_id', 'unknown')}, Submission {c.get('submission_id', 'unknown')}]\n{c.get('text', '')}"
            for c in context_chunks
        ])

        user_message = f"""Question: {question}

Retrieved Context:
{context_text if context_text else "(No similar feedback text found in database)"}

Aggregate Metrics:
{json.dumps(agg_context, indent=2)}

Answer the question using the context above."""

        raw_output = await self._call_with_fallback(
            system_prompt=SYSTEM_PROMPT,
            user_message=user_message,
            temperature=0.2,
            max_tokens=3000,
        )

        # Strip any accidental code fences the model may add
        answer = raw_output.strip()
        if answer.startswith("```"):
            answer = answer.split("```")[-2] if answer.count("```") >= 2 else answer.replace("```", "")
            answer = answer.strip()

        return answer, [], 0.8

    async def _retrieve_context(
        self,
        question: str,
        db: AsyncSession,
        trainer_id: Optional[str],
        batch_id: Optional[str],
        time_range_days: int,
        top_k: int = 8,
    ) -> list[dict]:
        # Generate embedding for the question using Groq
        try:
            question_embedding = await self._get_text_embedding(question)
            if question_embedding is None:
                raise ValueError("Embedding unavailable")

            embedding_str = f"[{','.join(str(x) for x in question_embedding)}]"
            conditions = []
            params = {"embedding": embedding_str, "top_k": top_k}

            if trainer_id:
                conditions.append("fe.trainer_id = :trainer_id")
                params["trainer_id"] = trainer_id
            if batch_id:
                conditions.append("fe.batch_id = :batch_id")
                params["batch_id"] = batch_id

            where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

            sql = text(f"""
                SELECT fe.chunk_text, fe.submission_id::text, fe.batch_id::text,
                       1 - (fe.embedding <=> :embedding::vector) AS similarity
                FROM feedback_embeddings fe
                {where_clause}
                ORDER BY fe.embedding <=> :embedding::vector
                LIMIT :top_k
            """)
            rows = (await db.execute(sql, params)).fetchall()
            return [
                {"text": r.chunk_text, "submission_id": r.submission_id,
                 "batch_id": r.batch_id, "similarity": float(r.similarity)}
                for r in rows
            ]
        except Exception as e:
            log.warning(f"{self.name}.vector_search_failed", error=str(e))
            # Fallback: text-based search
            return await self._fallback_text_search(question, db, trainer_id, batch_id)

    async def _fallback_text_search(
        self, question: str, db: AsyncSession,
        trainer_id: Optional[str], batch_id: Optional[str]
    ) -> list[dict]:
        keywords = [w.lower() for w in question.split() if len(w) > 4][:5]
        if not keywords:
            return []

        q = select(FeedbackSubmission).join(TrainingBatch, TrainingBatch.id == FeedbackSubmission.batch_id)
        if trainer_id:
            q = q.where(TrainingBatch.trainer_id == trainer_id)
        if batch_id:
            q = q.where(FeedbackSubmission.batch_id == batch_id)
        q = q.limit(10)

        rows = (await db.execute(q)).scalars().all()
        chunks = []
        for r in rows:
            text_parts = [r.free_text_positive, r.free_text_improve, r.free_text_overall]
            combined = " ".join(p for p in text_parts if p)
            if combined and any(kw in combined.lower() for kw in keywords):
                chunks.append({
                    "text": combined[:500],
                    "submission_id": str(r.id),
                    "batch_id": str(r.batch_id),
                    "similarity": 0.5,
                })
        return chunks

    async def _get_text_embedding(self, text: str) -> list[float] | None:
        """Use Groq's embedding endpoint if available, else return None."""
        try:
            # Groq doesn't have embeddings API yet — use a lightweight fallback
            # In production, replace with sentence-transformers or OpenAI embeddings
            return None
        except Exception:
            return None

    async def _get_aggregate_context(
        self, db: AsyncSession, org_id: str,
        trainer_id: Optional[str], batch_id: Optional[str]
    ) -> dict:
        try:
            q = select(Trainer)
            if trainer_id:
                q = q.where(Trainer.id == trainer_id)
            else:
                q = q.where(Trainer.organization_id == org_id)
            q = q.limit(5)
            trainers = (await db.execute(q)).scalars().all()
            return {
                "trainers": [
                    {"name": t.full_name, "health_score": float(t.overall_health_score), "sessions": t.total_sessions}
                    for t in trainers
                ]
            }
        except Exception:
            return {}
