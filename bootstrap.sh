#!/bin/sh
# Set up skillshare on a machine from this repo (Diz312/skillshare-source). The repo is private:
#   gh api repos/Diz312/skillshare-source/contents/bootstrap.sh -H "Accept: application/vnd.github.raw" | sh
# Idempotent: re-run it after installing a new AI tool. Steps and prerequisites:
# https://github.com/Diz312/agent-toolkit#new-machine
set -eu
REMOTE=https://github.com/Diz312/skillshare-source.git
SS="$HOME/.config/skillshare"
CFG="$SS/config.yaml"
SECRETS="$HOME/.secrets/agent.env"

command -v skillshare >/dev/null || brew install skillshare

# The repo is private: git must be able to read it before init, or init links an empty source.
if ! GIT_TERMINAL_PROMPT=0 git ls-remote -q "$REMOTE" >/dev/null 2>&1; then
  echo "Cannot read $REMOTE. Sign git in to GitHub first:" >&2
  echo "  gh auth login && gh auth setup-git" >&2
  exit 1
fi

if [ ! -f "$CFG" ]; then
  # Connects the existing repo: pulls skills, agents, mcp.yaml and plugins.txt; detects tools.
  skillshare init --remote "$REMOTE" --git-root root --all-targets --mode merge --no-skill --no-tui
else
  skillshare pull
  skillshare init --discover --no-tui || true
fi

# MCP servers live in the committed mcp.yaml; config.yaml is per machine.
if ! grep -q '^  mcp: ./mcp.yaml' "$CFG"; then
  sed -i.bak 's|^sources:$|sources:\
  mcp: ./mcp.yaml|' "$CFG" && rm -f "$CFG.bak"
fi
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

# Claude Code plugins from plugins.txt (written by agent-toolkit's apply.py). skillshare cannot
# share native-only plugin installs between machines, so each machine installs and imports them.
if command -v claude >/dev/null && [ -f "$SS/plugins.txt" ]; then
  grep -v '^#' "$SS/plugins.txt" | while read -r name ident marketplace; do
    [ -n "$name" ] || continue
    claude plugin marketplace add "$marketplace" >/dev/null 2>&1 || true
    claude plugin install "$ident" -s user >/dev/null 2>&1 || true
    skillshare plugin import "$ident" --from claude --name "$name" --no-tui >/dev/null 2>&1 || true
  done
fi

# Secrets reach shells through ~/.zshrc and GUI apps (Cursor, Claude desktop) through a
# LaunchAgent that copies them into launchd at login.
if [ -f "$SECRETS" ]; then
  chmod 600 "$SECRETS"
  if ! grep -qs 'secrets/agent.env' "$HOME/.zshrc"; then
    cat >> "$HOME/.zshrc" <<'EOF'

# Agent secrets (MCP fromEnv references used by skillshare)
[ -f "$HOME/.secrets/agent.env" ] && { set -a; . "$HOME/.secrets/agent.env"; set +a; }
EOF
  fi
  if [ "$(uname)" = Darwin ]; then
    plist="$HOME/Library/LaunchAgents/com.diz312.agent-env.plist"
    mkdir -p "$HOME/Library/LaunchAgents"
    cat > "$plist" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.diz312.agent-env</string>
  <key>ProgramArguments</key><array><string>/bin/sh</string><string>-c</string>
  <string>set -a; . "$HOME/.secrets/agent.env"; set +a; for v in $(cut -d= -f1 "$HOME/.secrets/agent.env" | grep -v '^#'); do eval "launchctl setenv $v \"\$$v\""; done</string></array>
  <key>RunAtLoad</key><true/>
</dict></plist>
EOF
    launchctl bootout "gui/$(id -u)/com.diz312.agent-env" >/dev/null 2>&1 || true
    launchctl bootstrap "gui/$(id -u)" "$plist"
  fi
  set -a; . "$SECRETS"; set +a
else
  echo "No $SECRETS yet: MCP servers that need a key will fail until you create it and re-run." >&2
fi

skillshare sync --all --no-tui
skillshare mcp check --no-dns || echo "Fix what mcp check reports (usually a key in $SECRETS), then re-run."
echo "Done. Restart Claude Code, Cursor and other AI apps so they load the new skills, MCP servers and keys."
