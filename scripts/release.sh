#!/bin/sh
set -e

# ── release.sh ───────────────────────────────────────────────────────────────
# Auto-detect version bump from conventional commits, update CHANGELOG,
# create a release commit + annotated tag, then push.
#
# Usage:
#   ./scripts/release.sh           # auto-detect bump from commits
#   ./scripts/release.sh patch     # force patch bump
#   ./scripts/release.sh minor     # force minor bump
#   ./scripts/release.sh major     # force major bump
# ─────────────────────────────────────────────────────────────────────────────

FORCE_BUMP="${1:-}"
REPO_URL="https://github.com/Andrevops/claude-stats"

# ── Get current version from latest tag ──────────────────────────────────────

LAST_TAG=$(git describe --tags --abbrev=0 2>/dev/null || echo "")

if [ -z "$LAST_TAG" ]; then
  MAJOR=0; MINOR=0; PATCH=0
  COMMIT_RANGE="HEAD"
  echo "no previous tag found — starting at v0.0.0"
else
  VERSION="${LAST_TAG#v}"
  MAJOR=$(echo "$VERSION" | cut -d. -f1)
  MINOR=$(echo "$VERSION" | cut -d. -f2)
  PATCH=$(echo "$VERSION" | cut -d. -f3)
  COMMIT_RANGE="${LAST_TAG}..HEAD"
  echo "current version: $LAST_TAG"
fi

# ── Collect commits since last tag ───────────────────────────────────────────

COMMITS=$(git log "$COMMIT_RANGE" --pretty=format:"%s" 2>/dev/null || echo "")

if [ -z "$COMMITS" ]; then
  echo "no commits since $LAST_TAG — nothing to release"
  exit 1
fi

echo ""
echo "commits since $LAST_TAG:"
git log "$COMMIT_RANGE" --pretty=format:"  %s" 2>/dev/null
echo ""

# ── Detect bump type from conventional commits ──────────────────────────────

if [ -n "$FORCE_BUMP" ]; then
  BUMP="$FORCE_BUMP"
  echo "forced bump: $BUMP"
else
  BUMP="patch"
  echo "$COMMITS" | while IFS= read -r msg; do
    case "$msg" in
      *"BREAKING CHANGE"*|*"!"*)  echo "major" > /tmp/_cs_bump ;;
      feat*) [ ! -f /tmp/_cs_bump ] && echo "minor" > /tmp/_cs_bump ;;
    esac
  done
  if [ -f /tmp/_cs_bump ]; then
    BUMP=$(cat /tmp/_cs_bump)
    rm -f /tmp/_cs_bump
  fi
  echo "detected bump: $BUMP"
fi

# ── Calculate new version ────────────────────────────────────────────────────

case "$BUMP" in
  major) MAJOR=$((MAJOR + 1)); MINOR=0; PATCH=0 ;;
  minor) MINOR=$((MINOR + 1)); PATCH=0 ;;
  patch) PATCH=$((PATCH + 1)) ;;
  *) echo "invalid bump type: $BUMP" >&2; exit 1 ;;
esac

NEW_VERSION="v${MAJOR}.${MINOR}.${PATCH}"
echo "new version: $NEW_VERSION"
echo ""

# ── Generate changelog entry ─────────────────────────────────────────────────

DATE=$(date +%Y-%m-%d)
FEATURES=""
FIXES=""
OTHER=""

SAVE_IFS="$IFS"
IFS='
'
for msg in $COMMITS; do
  # Skip release commits
  case "$msg" in chore\(release\)*) continue ;; esac

  case "$msg" in
    feat*)
      clean=$(echo "$msg" | sed 's/^feat[^:]*: //')
      FEATURES="${FEATURES}\n- ${clean}"
      ;;
    fix*)
      clean=$(echo "$msg" | sed 's/^fix[^:]*: //')
      FIXES="${FIXES}\n- ${clean}"
      ;;
    *)
      OTHER="${OTHER}\n- ${msg}"
      ;;
  esac
done
IFS="$SAVE_IFS"

COMPARE=""
if [ -n "$LAST_TAG" ]; then
  COMPARE="[Full changelog](${REPO_URL}/compare/${LAST_TAG}...${NEW_VERSION})"
else
  COMPARE="[Full changelog](${REPO_URL}/commits/${NEW_VERSION})"
fi

ENTRY="## ${NEW_VERSION} (${DATE})\n"
if [ -n "$FEATURES" ]; then
  ENTRY="${ENTRY}\n### Features\n${FEATURES}\n"
fi
if [ -n "$FIXES" ]; then
  ENTRY="${ENTRY}\n### Bug Fixes\n${FIXES}\n"
fi
if [ -n "$OTHER" ]; then
  ENTRY="${ENTRY}\n### Other\n${OTHER}\n"
fi
ENTRY="${ENTRY}\n${COMPARE}\n"

# ── Update CHANGELOG.md ─────────────────────────────────────────────────────

CHANGELOG="CHANGELOG.md"
if [ -f "$CHANGELOG" ]; then
  # Insert after the first heading line
  TMPFILE=$(mktemp)
  INSERTED=0
  while IFS= read -r line; do
    echo "$line" >> "$TMPFILE"
    if [ $INSERTED -eq 0 ] && echo "$line" | grep -q "^# "; then
      printf "\n" >> "$TMPFILE"
      printf "%b" "$ENTRY" >> "$TMPFILE"
      INSERTED=1
    fi
  done < "$CHANGELOG"
  mv "$TMPFILE" "$CHANGELOG"
else
  printf "# Changelog\n\n" > "$CHANGELOG"
  printf "%b" "$ENTRY" >> "$CHANGELOG"
fi

echo "updated $CHANGELOG"

# ── Commit and tag ───────────────────────────────────────────────────────────

git add CHANGELOG.md
git commit -m "chore(release): ${NEW_VERSION}"
git tag -a "$NEW_VERSION" -m "Release ${NEW_VERSION}"

echo ""
echo "created commit and tag: $NEW_VERSION"
echo ""
echo "to publish the release:"
echo "  git push --follow-tags"
echo ""
echo "GitHub Actions will build binaries and create the release."
