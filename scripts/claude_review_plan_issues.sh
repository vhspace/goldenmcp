#!/usr/bin/env bash
# Bundle GoldenMCP plan + GitHub issues, run Claude Code (Fable, 300k) review,
# archive to docs/reviews/, and post suggestions to GitHub.
set -euo pipefail

REPO="vhspace/goldenmcp"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PLAN="$ROOT/docs/plans/2026-06-12-goldenmcp-eval-marketplace.md"
REVIEW_DIR="$ROOT/docs/reviews"
BUNDLE="$REVIEW_DIR/_review_bundle.md"
DATE_TAG="$(date +%Y-%m-%d)"
OUT="$REVIEW_DIR/plan-issues-review-${DATE_TAG}.md"
MODEL="claude-fable-5"
CONTEXT_TOKENS=300000
MAX_GH_COMMENTS=10

bundle_only=false
archive_only=false
post_github_only=false
post_github=true

usage() {
  cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Options:
  --bundle-only       Bundle plan + issues only; no Claude review
  --archive-only      Run Claude review; save archive; skip GitHub posting
  --post-github-only  Post GitHub suggestions from existing archive (no Claude run)
  --no-post-github    Same as --archive-only
  -h, --help          Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --bundle-only) bundle_only=true; post_github=false ;;
    --archive-only|--no-post-github) archive_only=true; post_github=false ;;
    --post-github-only) post_github_only=true; post_github=true ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 1 ;;
  esac
  shift
done

if ! command -v gh >/dev/null 2>&1; then
  echo "gh CLI required" >&2
  exit 1
fi

if [[ ! -f "$PLAN" ]]; then
  echo "Plan not found: $PLAN" >&2
  exit 1
fi

mkdir -p "$REVIEW_DIR"

gh_authed=false
if gh auth status -h github.com >/dev/null 2>&1; then
  gh_authed=true
elif $post_github; then
  echo "gh not authenticated — skipping GitHub post (archive still written)" >&2
  post_github=false
fi

bundle_inputs() {
  local issue_count
  issue_count="$(gh issue list -R "$REPO" --state open --json number --jq 'length')"
  if [[ "$issue_count" -eq 0 ]]; then
    echo "No open issues on $REPO — run scripts/create_github_issues.sh first" >&2
    exit 1
  fi

  echo "Bundling plan + $issue_count issues..."
  {
    echo "# GoldenMCP Review Bundle"
    echo ""
    echo "Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "Repo: https://github.com/$REPO"
    echo ""
    echo "## Plan"
    echo ""
    echo '```markdown'
    cat "$PLAN"
    echo '```'
    echo ""
    echo "## GitHub issues (open)"
    echo ""
    gh issue list -R "$REPO" --state open --limit 100 \
      --json number,title,labels,body \
      --jq '.[] | "### GH #\(.number): \(.title)\n\nLabels: \([.labels[].name] | join(", "))\n\n\(.body)\n"'
  } > "$BUNDLE"

  echo "Wrote $BUNDLE ($(wc -c < "$BUNDLE" | tr -d ' ') bytes)"
}

run_claude_review() {
  if ! command -v claude >/dev/null 2>&1; then
    echo "claude CLI not found on PATH" >&2
    exit 1
  fi

  local prompt
  prompt="$(cat <<'EOF'
You are reviewing the GoldenMCP ETHGlobal NYC 2026 project plan and its GitHub issues.

Read the bundled plan and all open issues below. Produce a structured review with these sections:

## Executive summary
2-3 sentences on overall plan/issue health.

## Plan ↔ issues alignment
- Map plan issue IDs (#1–#64) to GitHub issue titles
- List missing plan items, orphan issues, numbering mismatches

## Epic coverage
For each epic (infra, eval, walrus, web, identity, chainlink, marketplace): complete / partial / missing

## Bounty traceability
ENS, Chainlink CRE+CAI, Arc x402, main track, Walrus/Sui reserve — what issues cover each criterion?

## Sequencing and dependencies
Critical path, blockers, env prerequisites, booth/demo deadlines

## Acceptance test quality
Weak or ambiguous "done when" criteria; suggest fixes

## Recommendations
Prioritized actions using machine-parseable prefixes on every bullet:
- [GH-N] — comment on existing GitHub issue N (e.g. [GH-14])
- [NEW epic/name] — create a new issue for a gap (e.g. [NEW epic/walrus] Add benchmark CI gate)
- [META] — epic-level or reprioritization notes (meta review issue only)

Example:
- [GH-14] Tighten acceptance test for post-eval Walrus hook
- [NEW epic/walrus] Add issue for benchmark CI gate
- [META] Reprioritize identity epic before ENS booth deadline

Be specific. Reference plan issue IDs and GitHub issue numbers. Do not propose editing the plan file itself.

---
BUNDLE START
EOF
)"

  export CLAUDE_CODE_MAX_CONTEXT_TOKENS="$CONTEXT_TOKENS"
  export DISABLE_COMPACT=1

  echo "Running Claude Code review: model=$MODEL context_cap=${CONTEXT_TOKENS}..."
  if ! claude -p "${prompt}

$(cat "$BUNDLE")

---
BUNDLE END" \
    --model "$MODEL" \
    --add-dir "$ROOT/docs/plans" \
    --add-dir "$ROOT/docs" \
    --permission-mode bypassPermissions \
    --output-format text \
    < /dev/null \
    > "$OUT" 2>"$REVIEW_DIR/_claude_review.stderr"; then
    echo "Claude Code review failed. stderr:" >&2
    cat "$REVIEW_DIR/_claude_review.stderr" >&2
    exit 1
  fi

  echo "Review saved: $OUT"
  wc -l "$OUT"
}

extract_section() {
  local file="$1"
  local heading="$2"
  awk -v h="$heading" '
    $0 ~ "^## " h { found=1; next }
    found && /^## / { exit }
    found { print }
  ' "$file"
}

post_to_github() {
  if ! $gh_authed; then
    echo "Skipping GitHub post — gh not authenticated" >&2
    return 0
  fi

  if [[ ! -f "$OUT" ]]; then
    echo "Archive not found: $OUT — run review first" >&2
    exit 1
  fi

  local summary recommendations meta_body rel_archive
  rel_archive="docs/reviews/plan-issues-review-${DATE_TAG}.md"
  summary="$(extract_section "$OUT" "Executive summary")"
  recommendations="$(extract_section "$OUT" "Recommendations")"

  if [[ -z "$recommendations" ]]; then
    echo "No ## Recommendations section in $OUT — skipping GitHub post" >&2
    return 0
  fi

  meta_body="$(cat <<EOF
Automated plan review for GoldenMCP (${DATE_TAG}).

**Archive:** \`${rel_archive}\` (in repo)

## Executive summary
${summary:-_(no executive summary found)_}

## Recommendations
${recommendations}
EOF
)"

  echo "Creating meta review issue..."
  local meta_url meta_number
  meta_url="$(gh issue create -R "$REPO" \
    --title "Plan review ${DATE_TAG}" \
    --label "P0" \
    --body "$meta_body")"
  meta_number="${meta_url##*/}"
  echo "Meta issue: $meta_url (#$meta_number)"

  local comment_count=0
  local new_count=0

  while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    [[ "$line" =~ ^[[:space:]]*[-*] ]] || continue

    if [[ "$line" =~ \[GH-([0-9]+)\] ]]; then
      local gh_num="${BASH_REMATCH[1]}"
      if [[ "$comment_count" -ge "$MAX_GH_COMMENTS" ]]; then
        echo "Reached max GH comments ($MAX_GH_COMMENTS); skipping further [GH-N]" >&2
        continue
      fi
      local comment_body
      comment_body="**Plan review ${DATE_TAG}** (from meta #$meta_number)

${line#*- }"
      if gh issue comment "$gh_num" -R "$REPO" --body "$comment_body" >/dev/null 2>&1; then
        echo "Commented on #$gh_num"
        comment_count=$((comment_count + 1))
      else
        echo "Failed to comment on #$gh_num" >&2
      fi
    elif [[ "$line" =~ \[NEW[[:space:]]+epic/([a-z0-9_-]+)\][[:space:]]+(.*) ]]; then
      local epic="${BASH_REMATCH[1]}"
      local title="${BASH_REMATCH[2]}"
      title="${title%%$'\r'}"
      local new_body
      new_body="$(cat <<EOF
## Source
Plan review ${DATE_TAG} — meta issue #$meta_number

## Recommendation
${line#*- }

## Archive
\`${rel_archive}\`
EOF
)"
      local new_url
      new_url="$(gh issue create -R "$REPO" \
        --title "[review] ${title}" \
        --label "P0,epic/${epic}" \
        --body "$new_body")"
      echo "Created issue: $new_url"
      new_count=$((new_count + 1))
    fi
  done <<< "$recommendations"

  echo "GitHub post complete: meta #$meta_number, $comment_count comments, $new_count new issues"
}

# --- main ---

if $post_github_only; then
  post_to_github
  exit 0
fi

bundle_inputs

if $bundle_only; then
  exit 0
fi

run_claude_review

if $post_github && ! $archive_only; then
  post_to_github
fi
