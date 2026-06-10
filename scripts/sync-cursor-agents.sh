#!/usr/bin/env bash
# Clone CursorReactNativeAgents and copy .cursor rules, skills, and agents into this app.
#
# Usage (from app root):
#   npm run sync-agents
#   bash scripts/sync-cursor-agents.sh

set -euo pipefail

REPO_URL='https://github.com/codeandtheory/CursorReactNativeAgents.git'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_DIR=''

cleanup() {
  if [[ -n "$TMP_DIR" && -d "$TMP_DIR" ]]; then
    rm -rf "$TMP_DIR"
  fi
}

trap cleanup EXIT

if ! command -v git >/dev/null 2>&1; then
  echo "Error: git is required but not found in PATH."
  exit 1
fi

TMP_DIR="$(mktemp -d)"
CLONE_DIR="$TMP_DIR/CursorReactNativeAgents"

echo "=== Syncing Cursor agents ==="
echo "App root:  $PROJECT_ROOT"
echo "Repo:      $REPO_URL"
echo ""

git clone -q "$REPO_URL" "$CLONE_DIR"

mkdir -p "$PROJECT_ROOT/.cursor/rules" \
         "$PROJECT_ROOT/.cursor/skills" \
         "$PROJECT_ROOT/.cursor/agents"

rules_copied=0
skills_copied=0
agents_copied=0

for kit_dir in "$CLONE_DIR"/*/; do
  [[ -d "$kit_dir" ]] || continue
  cursor_dir="$kit_dir/.cursor"
  [[ -d "$cursor_dir" ]] || continue

  kit_name="$(basename "$kit_dir")"

  if [[ -d "$cursor_dir/rules" ]]; then
    for rule_file in "$cursor_dir/rules"/*.mdc; do
      [[ -f "$rule_file" ]] || continue
      cp "$rule_file" "$PROJECT_ROOT/.cursor/rules/"
      rules_copied=$((rules_copied + 1))
    done
  fi

  if [[ -d "$cursor_dir/skills" ]]; then
    for skill_dir in "$cursor_dir/skills"/*/; do
      [[ -d "$skill_dir" ]] || continue
      skill_name="$(basename "$skill_dir")"
      rm -rf "$PROJECT_ROOT/.cursor/skills/$skill_name"
      cp -R "$skill_dir" "$PROJECT_ROOT/.cursor/skills/$skill_name"
      skills_copied=$((skills_copied + 1))
      echo "✓ Installed .cursor/skills/$skill_name/ (from $kit_name)"
    done
  fi

  if [[ -d "$cursor_dir/agents" ]]; then
    for agent_file in "$cursor_dir/agents"/*; do
      [[ -f "$agent_file" ]] || continue
      cp "$agent_file" "$PROJECT_ROOT/.cursor/agents/"
      agents_copied=$((agents_copied + 1))
    done
  fi
done

echo ""
echo "Done. Copied $rules_copied rule(s), $skills_copied skill kit(s), $agents_copied agent file(s)."
echo "Open this app in Cursor to use the synced rules, skills, and agents."
