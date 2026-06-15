from __future__ import annotations

import time

from .incidents import STATE

from .tracing import observe, langfuse_context

CORPUS = {
    "refund": ["Refunds are available within 7 days with proof of purchase."],
    "monitoring": ["Metrics detect incidents, traces localize them, logs explain root cause."],
    "policy": ["Do not expose PII in logs. Use sanitized summaries only."],
}


@observe(as_type="span")
def retrieve(message: str) -> list[str]:
    langfuse_context.update_current_observation(input=message)
    if STATE["tool_fail"]:
        raise RuntimeError("Vector store timeout")
    if STATE["rag_slow"]:
        time.sleep(2.5)
    lowered = message.lower()
    for key, docs in CORPUS.items():
        if key in lowered:
            langfuse_context.update_current_observation(output=docs)
            return docs
    fallback = ["No domain document matched. Use general fallback answer."]
    langfuse_context.update_current_observation(output=fallback)
    return fallback
