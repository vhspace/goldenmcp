---
name: git-workflow
description: >-
  Commit often and merge via pull requests. Use when committing, pushing,
  opening PRs, or integrating work — never push feature work directly to main.
---

# Git workflow: commit often, merge via PR

## Commit

- Commit after each logical unit of work (see `.cursor/rules/commit-often.mdc`).
- Never commit secrets; `.env.example` only for env templates.

## Branch and push

```bash
git checkout -b feat/short-description   # or fix/, chore/
git push -u origin HEAD
```

## Open a pull request

Use `gh` for all GitHub tasks:

```bash
gh pr create --title "Short title" --body "$(cat <<'EOF'
## Summary
- What changed and why

## Test plan
- [ ] Commands run / checks passed
EOF
)"
```

Before creating a PR, inspect branch state:

```bash
git status
git diff
git log main...HEAD
```

## Merge policy

- **Merge through PRs** — do not push feature commits directly to `main`.
- Direct push to `main` only when the user explicitly requests it (hotfix exception).
- Return the PR URL when done so the user can review.

## Triggers

- User asks to commit, push, merge, or open a PR
- End of a feature slice ready for review
- Integrating work from a branch
