from __future__ import annotations

import os
from typing import Any
import langfuse

# For langfuse >= 3.2.0, observe decorator and tracing capabilities are exposed directly on the root module or client
observe = langfuse.observe

class _LangfuseContextWrapper:
    def update_current_trace(self, **kwargs: Any) -> None:
        try:
            client = langfuse.get_client()
            if client:
                client.update_current_trace(**kwargs)
        except Exception:
            pass

    def update_current_observation(self, **kwargs: Any) -> None:
        try:
            client = langfuse.get_client()
            if client:
                # Update span or generation if available in client context
                client.update_current_span(**kwargs)
        except Exception:
            pass

langfuse_context = _LangfuseContextWrapper()


def tracing_enabled() -> bool:
    return bool(os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"))
