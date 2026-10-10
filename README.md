# agentik-labs

Core repository for Agentik AI Academy deterministic laboratory evaluations and the shared `agentik-labkit` Python package.

## Principles

1. **Zero-cost by default**: No laboratory evaluation requires paid third-party LLM API keys.
2. **Cross-platform**: Runs reliably on Linux, macOS, and Windows (WSL2).
3. **Deterministic**: Identical seed produces identical outcomes across all runs.
4. **Observable outcomes**: Acceptance criteria assert system effects (file schema, memory state, HTTP contracts), not open-ended text quality.

## Package Structure

- `labkit/`: Core deterministic testing kit.
  - `clock.py`: Injectable `Clock` (`RealClock` and `VirtualClock`) for instant timeout/TTFT testing without real sleep.
  - `llm.py`: Hexagonal `LLMClient` protocol decoupling tests from actual AI providers.
  - `replay.py`: `ReplayClient` reproducing pre-recorded cassettes.
  - `sim.py`: `SimClient` with deterministic pseudo-random seeds and configurable pass rates.
  - `fake_provider.py`: `FakeProviderServer` serving OpenAI-compatible streaming SSE with controllable TTFT/ITL latencies.
  - `tokenizer.py`: Offline token counting and prompt prefix hashing for caching checks.
  - `sandbox.py`: Hardened local container launcher (`--network none`, `--read-only`, `--cap-drop ALL`).
  - `assert_env.py`: Outcome assertion helpers for filesystem, databases, and HTTP contracts.
  - `seed.py`: Per-user seed generator derived from `user_id` or `github_username`.
- `curso-0/` to `curso-3/`: Hands-on lab tracks.

## Quick Start

```bash
# Install dependencies with uv
uv sync

# Run all deterministic tests (network socket blocked by default)
uv run pytest
```
