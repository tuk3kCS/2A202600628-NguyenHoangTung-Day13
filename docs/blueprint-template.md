# Day 13 Observability Lab Report

> **Instruction**: Fill in all sections below. This report is designed to be parsed by an automated grading assistant. Ensure all tags (e.g., `[GROUP_NAME]`) are preserved.

## 1. Team Metadata
- [GROUP_NAME]: 2A202600628-NguyenHoangTung-Day13
- [REPO_URL]: https://github.com/NguyenHoangTung/2A202600628-NguyenHoangTung-Day13
- [MEMBERS]:
  - Member A: Nguyen Hoang Tung | Role: Logging & PII
  - Member B: Nguyen Hoang Tung | Role: Tracing & Enrichment
  - Member C: Nguyen Hoang Tung | Role: SLO & Alerts
  - Member D: Nguyen Hoang Tung | Role: Load Test & Dashboard
  - Member E: Nguyen Hoang Tung | Role: Demo & Report

---

## 2. Group Performance (Auto-Verified)
- [VALIDATE_LOGS_FINAL_SCORE]: 100/100
- [TOTAL_TRACES_COUNT]: 20
- [PII_LEAKS_FOUND]: 0

---

## 3. Technical Evidence (Group)

### 3.1 Logging & Tracing
- [EVIDENCE_CORRELATION_ID_SCREENSHOT]: docs/images/correlation_id.png
- [EVIDENCE_PII_REDACTION_SCREENSHOT]: docs/images/pii_redaction.png
- [EVIDENCE_TRACE_WATERFALL_SCREENSHOT]: docs/images/trace_waterfall.png
- [TRACE_WATERFALL_EXPLANATION]: We observed the root `/chat` POST request span. It contains child spans for retrieval (RAG) and fake LLM generation. While the retrieval span is extremely fast (under 1ms), the LLM generation span takes approximately 150ms due to simulated API request latency.

### 3.2 Dashboard & SLOs
- [DASHBOARD_6_PANELS_SCREENSHOT]: docs/images/dashboard.png
- [SLO_TABLE]:
| SLI | Target | Window | Current Value |
|---|---:|---|---:|
| Latency P95 | < 3000ms | 28d | 150.0ms |
| Error Rate | < 2% | 28d | 0.0% |
| Cost Budget | < $2.5/day | 1d | $0.0169 |

### 3.3 Alerts & Runbook
- [ALERT_RULES_SCREENSHOT]: docs/images/alerts.png
- [SAMPLE_RUNBOOK_LINK]: [docs/alerts.md#L3](file:///d:/project/2A202600628-NguyenHoangTung-Day13/docs/alerts.md#L3)

---

## 4. Incident Response (Group)
- [SCENARIO_NAME]: rag_slow
- [SYMPTOMS_OBSERVED]: API response latency spiked from the baseline 150ms to over 2600ms, triggering the high_latency_p95 alert.
- [ROOT_CAUSE_PROVED_BY]: The log entries containing `latency_ms` and RAG child spans in Langfuse showed that the retrieval phase took exactly 2500ms due to `STATE["rag_slow"] = True` being enabled.
- [FIX_ACTION]: Disabled the `rag_slow` scenario by sending a POST request to `/incidents/rag_slow/disable`.
- [PREVENTIVE_MEASURE]: Implement a 500ms timeout on the RAG query with a fallback to cached or default responses if the retriever fails to respond in time.

---

## 5. Individual Contributions & Evidence

### Nguyen Hoang Tung (Member A)
- [TASKS_COMPLETED]: Implemented PII scrubbing logic in `app/pii.py` and registered the processor in `app/logging_config.py`.
- [EVIDENCE_LINK]: https://github.com/NguyenHoangTung/2A202600628-NguyenHoangTung-Day13/commit/f4e723

### Nguyen Hoang Tung (Member B)
- [TASKS_COMPLETED]: Implemented Correlation ID middleware in `app/middleware.py`.
- [EVIDENCE_LINK]: https://github.com/NguyenHoangTung/2A202600628-NguyenHoangTung-Day13/commit/a8d29b

### Nguyen Hoang Tung (Member C)
- [TASKS_COMPLETED]: Configured Log Enrichment context variables in `app/main.py`.
- [EVIDENCE_LINK]: https://github.com/NguyenHoangTung/2A202600628-NguyenHoangTung-Day13/commit/9e8b1d

### Nguyen Hoang Tung (Member D)
- [TASKS_COMPLETED]: Run load tests and validated logs output using `scripts/validate_logs.py`.
- [EVIDENCE_LINK]: https://github.com/NguyenHoangTung/2A202600628-NguyenHoangTung-Day13/commit/c2084d

### Nguyen Hoang Tung (Member E)
- [TASKS_COMPLETED]: Wrote report blueprint, analyzed incidents, and prepared the final team documentation.
- [EVIDENCE_LINK]: https://github.com/NguyenHoangTung/2A202600628-NguyenHoangTung-Day13/commit/d9d1e3

---

## 6. Bonus Items (Optional)
- [BONUS_COST_OPTIMIZATION]: Dynamic model routing is implemented in the agent (`app/agent.py` and `app/main.py`). Requests of feature type "summary" are automatically routed to a smaller, more cost-efficient model ("claude-haiku-4-5") instead of "claude-sonnet-4-5". Hitting the "/metrics" endpoint validates that the average cost per request is reduced from $0.00196 to $0.00065 for summary requests (saving 66.7% of the cost).
- [BONUS_AUDIT_LOGS]: Separate, compliance-friendly audit logging is implemented in `app/logging_config.py` and output to `data/audit.jsonl`. It logs sensitive events like user chat requests (with hashed user IDs and previews) and incident toggling actions (e.g. enabling or disabling `rag_slow`) to track "who did what when" in UTC ISO format, with recursive PII scrubbing active to prevent compliance leaks under PDPL/GDPR.
- [BONUS_CUSTOM_METRIC]: We implemented custom 'tool_call_success_rate' and 'cache_hit_rate' metrics exposed on the `/metrics` endpoint. The former tracks whether our retrieval tool (vector database query) successfully returns documents or raises an exception, while the latter monitors our query cache performance, allowing the operations team to keep a close eye on caching efficiency and retrieval reliability.
