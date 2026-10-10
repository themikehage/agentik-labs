# Architecture & System Design

Enterprise Inference Microservice architecture for LLM Production Engineering Fundamentals (Curso 0 Capstone).

## Quantitative SLO Budgets

The microservice operates under strict engineering budgets:
- **Time To First Token (TTFT)**: <= 500 ms under standard prefill load.
- **Inter-Token Latency (ITL) P50**: <= 20 ms per token during decode phase.
- **Inter-Token Latency (ITL) P95**: <= 40 ms per token to ensure smooth human streaming perception.
- **Prompt Cache Hit Latency**: Reduction of TTFT by >= 70% on cached prefix calls.
- **Evaluation Consistency**: pass^3 >= 80% across regression evals with 95% bootstrap confidence interval lower bound >= 75%.

## Resilience & Rate Limiting

- **Shared Token Bucket**: Capacity of 10 requests with smooth refill rate of 2 tokens per second to absorb bursts without queue starvation.
- **Backoff & Jitter**: Exponential backoff with deterministic jitter on HTTP 429 and 503 errors; immediate rejection of 4xx client errors without retry amplification.
- **Economic Circuit Breaker**: Hard monthly spend cap per tenant with automatic cut-off and deterministic `BudgetExceededError` emission.
- **Graceful Fallback**: Automatic failover to secondary model upon reaching consecutive failure threshold, with mandatory `is_degraded: True` flag.

## Security & Containment Policy

- **Container Isolation**: Untrusted tools execute strictly within `HardenedSandbox` with flags `--network none`, `--read-only`, `--cap-drop ALL`, and unprivileged UID 10001.
- **Metadata Protection**: Complete block of link-local cloud metadata endpoint `169.254.169.254`.
- **Destructive Actions**: Mandatory human-in-the-loop approval token required before executing irreversible tools (database drops, fund transfers).
- **Trifecta Containment**: Absolute zero network egress for agents processing untrusted external inputs.

## Evaluation Methodology & Acceptance Thresholds

- **Grader Strategy**: Outcome-based grading verifying real infrastructure mutations rather than generated conversational transcript claims.
- **Statistical Significance**: Paired version comparisons evaluated via 1000-sample bootstrap intervals; deployments require CI lower bound > 0.
- **Cost Calculation**: Decoupled financial billing performed in backend observability pipelines; zero financial cost attributes inside OpenTelemetry spans.
