# Scoring

GoldenMCP scores web3 MCPs per capability using three dimensions plus a binary security gate.

## Dimensions

| Score | Weight | Description |
|-------|--------|-------------|
| DataScore | 0.45 | Output correctness vs golden `expected_data` |
| PathScore | 0.35 | Tool-call sequence vs golden `expected_path` |
| TokenEfficiency | 0.20 | `1 - min(tokens/baseline_tokens, 1)` |

**Composite** = `0.45×Data + 0.35×Path + 0.20×Token`

## Binary fail

`security_scorer` runs first. Any fail → composite 0.0:

- Prompt injection patterns in MCP responses
- Tools outside `allowed_tools` allowlist
- Suspicious URLs or credential harvesting
- Policy violations (e.g. `execute_swap` during quote-only benchmark)

## Golden benchmarks

Located in `benchmarks/golden/{mcp}/{capability}.yaml`:

```yaml
expected_path: [get_chains, get_tokens, get_quote]
allowed_tools: [get_chains, get_tokens, get_quote]
baseline_tokens: 8000
expected_data:
  quote.amount_out:
    min: 1
policy:
  forbidden_actions: [execute_swap]
```

## Run scoring

```bash
uv run pytest packages/inspect-web3/tests/test_scorers.py -v
```
