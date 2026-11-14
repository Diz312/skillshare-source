#!/bin/sh
# Set up skillshare on a new machine from this repo (Diz312/skillshare-source).
#   curl -fsSL https://raw.githubusercontent.com/Diz312/skillshare-source/main/bootstrap.sh | sh
# or, with the repo private: gh api repos/Diz312/skillshare-source/contents/bootstrap.sh \
#   -H "Accept: application/vnd.github.raw" | sh
# Idempotent. Put secrets in ~/.secrets/agent.env (KEY=value lines, chmod 600) first.
set -eu
REMOTE=https://github.com/Diz312/skillshare-source.git
CFG="$HOME/.config/skillshare/config.yaml"

command -v skillshare >/dev/null || brew install skillshare

if [ ! -f "$CFG" ]; then
  # Connects the existing repo: pulls skills, agents and mcp.yaml; detects installed tools.
  skillshare init --remote "$REMOTE" --git-root root --all-targets --mode merge --no-skill --no-tui
else
  skillshare pull
  skillshare init --discover --no-tui || true
fi

# MCP servers live in the committed mcp.yaml; config.yaml is per machine.
grep -q '^  mcp: ./mcp.yaml' "$CFG" || sed -i.bak 's|^sources:$|sources:\
  mcp: ./mcp.yaml|' "$CFG"
if ! grep -q '^mcp:' "$CFG"; then
  clients=""
  [ -d "$HOME/.claude" ] && clients="$clients claude"
  [ -d "$HOME/.cursor" ] && clients="$clients cursor"
  [ -d "$HOME/.codex" ] && clients="$clients codex"
  [ -f "$HOME/.gemini/settings.json" ] && clients="$clients gemini"
  # antigravity is left out: it cannot receive context7's fromEnv bearer token.
  printf 'mcp:\n  targets: [%s]\n' "$(echo $clients | sed 's/ /, /g')" >> "$CFG"
fi

# Cursor also reads ~/.claude/skills and ~/.agents/skills; syncing into its own folder duplicates.
skillshare target cursor --skills=false >/dev/null 2>&1 || true

# Claude Code plugins (skillshare cannot share native-only plugin installs between machines).
if command -v claude >/dev/null; then
  claude plugin marketplace add anthropics/claude-plugins-official >/dev/null 2>&1 || true
  for p in pyright-lsp typescript-lsp; do
    claude plugin install "$p@claude-plugins-official" -s user >/dev/null 2>&1 || true
    skillshare plugin import "$p@claude-plugins-official" --from claude --name "$p" --no-tui >/dev/null 2>&1 || true
  done
fi

if [ -f "$HOME/.secrets/agent.env" ]; then set -a; . "$HOME/.secrets/agent.env"; set +a; fi
skillshare sync --all --no-tui
skillshare mcp check --no-dns || echo "Set the missing variables in ~/.secrets/agent.env, then re-run."
