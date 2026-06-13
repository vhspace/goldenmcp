---
name: claude-code-plan-review
description: >-
  Launch Claude Code (Fable, 300k context) to review GoldenMCP plan and GitHub
  issues. Use when the user asks to review the plan, audit issues, validate epic
  breakdown, or run a Claude Code plan review after issues are created.
---

# Claude Code Plan + Issues Review

Review the GoldenMCP implementation plan and GitHub issues using **Claude Code CLI** with **Fable** capped to **300k context**.

## Model and context

- Model: `claude-fable-5` (alias `fable`)
- Context cap: `CLAUDE_CODE_MAX_CONTEXT_TOKENS=300000` **and** `DISABLE_COMPACT=1` (required per [env-vars](https://code.claude.com/docs/en/env-vars))
- Do **not** use `claude-fable-5[300k]` — that suffix is invalid in Claude Code
- Do **not** use `claude-fable-5[1m]` when the user asked for 300k

## Headless delegation pattern (Cursor → Claude Code)

Use shell `claude -p` when the parent agent (Cursor) needs a different model or large-context review. Official docs: [headless mode](https://code.claude.com/docs/en/headless), [CLI reference](https://code.claude.com/docs/en/cli-reference).

| Pattern | Skill / doc | When |
|---------|-------------|------|
| Cursor spawns Cursor subagents | [Cursor Subagents](https://cursor.com/docs/agent/subagents), `dispatching-parallel-agents` | Same IDE, parallel explore/bash tasks |
| Cursor spawns Claude Code headless | **this skill** + `scripts/claude_review_plan_issues.sh` | Cross-model review (Fable 300k) |
| External app spawns Cursor agents | `~/.cursor/skills-cursor/sdk/SKILL.md` | CI, bots, `@cursor/sdk` |
| External app spawns Claude subagents | [Agent SDK subagents](https://code.claude.com/docs/en/agent-sdk/subagents) | Python/TS orchestration |
| Cross-LLM routing (reference) | [shinpr/sub-agents-skills](https://github.com/shinpr/sub-agents-skills) | Claude + Codex + Cursor CLI mix |

## Prerequisites

- `claude` CLI on PATH (`claude --version`)
- `gh` authenticated to `vhspace/goldenmcp`
- Plan file exists: `docs/plans/2026-06-12-goldenmcp-eval-marketplace.md`
- GitHub issues created (run `scripts/create_github_issues.sh` if empty)

## Workflow

### 1. Bundle inputs

```bash
./scripts/claude_review_plan_issues.sh --bundle-only
```

Writes `docs/reviews/_review_bundle.md` with plan excerpt + all open issues.

### 2. Run full review (archive + GitHub)

```bash
./scripts/claude_review_plan_issues.sh
```

Default: Claude Code review, archive file, then post suggestions to GitHub.

### 3. Archive only (skip GitHub)

```bash
./scripts/claude_review_plan_issues.sh --archive-only
```

### 4. Force GitHub post after existing archive

```bash
./scripts/claude_review_plan_issues.sh --post-github-only
```

## Where suggestions go (dual output)

### Layer 1 — Repo archive (full review)

| File | Role |
|------|------|
| `docs/reviews/plan-issues-review-YYYY-MM-DD.md` | Primary archive — full review including `## Recommendations` |
| `docs/reviews/_review_bundle.md` | Input snapshot (plan + open issues) |
| `docs/reviews/_claude_review.stderr` | Failure logs only |

**Never edit:** `docs/plans/2026-06-12-goldenmcp-eval-marketplace.md`

### Layer 2 — GitHub (actionable suggestions)

After archive is written, `--post-github` (default when `gh` is authenticated):

| Target | When |
|--------|------|
| **Meta review issue** | Every run — title `Plan review YYYY-MM-DD`, body has executive summary + recommendations + archive path |
| **Issue comments** | Lines tagged `[GH-N]` — max 10 per run |
| **New issues** | Lines tagged `[NEW epic/...]` — missing plan items or gaps |

Recommendations must use machine-parseable prefixes:

```markdown
## Recommendations
- [GH-14] Tighten acceptance test for post-eval Walrus hook
- [NEW epic/walrus] Add issue for benchmark CI gate
- [META] Reprioritize identity epic before ENS booth deadline
```

## Review prompt sections

1. Plan ↔ issues alignment
2. Epic coverage
3. Bounty traceability
4. Sequencing and dependencies
5. Acceptance test quality
6. Recommendations (with `[GH-N]`, `[NEW epic/...]`, `[META]` tags)

## Output rules

- Archive under `docs/reviews/`
- Post meta issue + targeted comments + new issues on GitHub (unless `--archive-only`)
- Do not edit the plan file from review output
- If Claude Code fails (auth, model), print stderr and stop — no mock review

## Triggers

- "review our plan and issues"
- "launch claude code to review plan"
- "audit github issues against plan"
- after `create_github_issues.sh` completes
