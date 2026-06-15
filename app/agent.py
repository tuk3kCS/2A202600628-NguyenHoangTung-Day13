from __future__ import annotations

import time
from dataclasses import dataclass

from . import metrics
from .mock_llm import FakeLLM
from .mock_rag import retrieve
from .pii import hash_user_id, summarize_text
from .tracing import langfuse_context, observe


@dataclass
class AgentResult:
    answer: str
    latency_ms: int
    ttft_ms: int
    tokens_in: int
    tokens_out: int
    cost_usd: float
    quality_score: float


class LabAgent:
    def __init__(self, model: str = "claude-sonnet-4-5") -> None:
        self.model = model
        self.llm = FakeLLM(model=model)
        self.cache: dict[str, AgentResult] = {}

    @observe()
    def run(self, user_id: str, feature: str, session_id: str, message: str, model: str | None = None) -> AgentResult:
        active_model = model or self.model
        
        # Cache check
        if message in self.cache:
            cached_res = self.cache[message]
            metrics.record_cache(hit=True)
            metrics.record_request(
                latency_ms=5,
                ttft_ms=2,
                cost_usd=0.0001,
                tokens_in=cached_res.tokens_in,
                tokens_out=cached_res.tokens_out,
                quality_score=cached_res.quality_score
            )
            metrics.record_tool_call(success=True)
            return AgentResult(
                answer=cached_res.answer,
                latency_ms=5,
                ttft_ms=2,
                tokens_in=cached_res.tokens_in,
                tokens_out=cached_res.tokens_out,
                cost_usd=0.0001,
                quality_score=cached_res.quality_score
            )
            
        metrics.record_cache(hit=False)
        started = time.perf_counter()
        
        # Tool call with success tracking
        try:
            docs = retrieve(message)
            metrics.record_tool_call(success=True)
        except Exception as e:
            metrics.record_tool_call(success=False)
            raise e
            
        prompt = f"Feature={feature}\nDocs={docs}\nQuestion={message}"
        response = self.llm.generate(prompt, model=active_model)
        quality_score = self._heuristic_quality(message, response.text, docs)
        latency_ms = int((time.perf_counter() - started) * 1000)
        ttft_ms = response.ttft_ms
        cost_usd = self._estimate_cost(response.usage.input_tokens, response.usage.output_tokens, model=active_model)

        langfuse_context.update_current_trace(
            user_id=hash_user_id(user_id),
            session_id=session_id,
            tags=["lab", feature, active_model],
        )
        langfuse_context.update_current_observation(
            metadata={
                "doc_count": len(docs),
                "query_preview": summarize_text(message),
                "gen_ai.operation.name": "chat",
                "gen_ai.provider.name": "anthropic",
                "gen_ai.request.model": active_model,
                "gen_ai.usage.input_tokens": response.usage.input_tokens,
                "gen_ai.usage.output_tokens": response.usage.output_tokens,
            },
            usage_details={"input": response.usage.input_tokens, "output": response.usage.output_tokens},
        )

        metrics.record_request(
            latency_ms=latency_ms,
            ttft_ms=ttft_ms,
            cost_usd=cost_usd,
            tokens_in=response.usage.input_tokens,
            tokens_out=response.usage.output_tokens,
            quality_score=quality_score,
        )

        res = AgentResult(
            answer=response.text,
            latency_ms=latency_ms,
            ttft_ms=ttft_ms,
            tokens_in=response.usage.input_tokens,
            tokens_out=response.usage.output_tokens,
            cost_usd=cost_usd,
            quality_score=quality_score,
        )
        
        self.cache[message] = res
        return res

    def _estimate_cost(self, tokens_in: int, tokens_out: int, model: str) -> float:
        if "haiku" in model.lower():
            # Haiku rates: $1/1M input, $5/1M output
            input_cost = (tokens_in / 1_000_000) * 1
            output_cost = (tokens_out / 1_000_000) * 5
        else:
            # Sonnet rates: $3/1M input, $15/1M output
            input_cost = (tokens_in / 1_000_000) * 3
            output_cost = (tokens_out / 1_000_000) * 15
        return round(input_cost + output_cost, 6)

    def _heuristic_quality(self, question: str, answer: str, docs: list[str]) -> float:
        score = 0.5
        if docs:
            score += 0.2
        if len(answer) > 40:
            score += 0.1
        if question.lower().split()[0:1] and any(token in answer.lower() for token in question.lower().split()[:3]):
            score += 0.1
        if "[REDACTED" in answer:
            score -= 0.2
        return round(max(0.0, min(1.0, score)), 2)
