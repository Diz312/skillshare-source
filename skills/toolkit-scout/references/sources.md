# Discovery sources

Run all of these each time. Use `--jq` to keep output small. Substitute values from
`config/preferences.yaml`.

## 1. Anthropic official

```bash
# Official skills
gh api repos/anthropics/skills/contents/skills --jq '.[] | select(.type=="dir") | .name'
gh api repos/anthropics/skills --jq '{stars: .stargazers_count, pushed: .pushed_at}'
# Official Claude Code plugins marketplace
gh api repos/anthropics/claude-plugins-official/contents/.claude-plugin/marketplace.json \
  -H "Accept: application/vnd.github.raw" | jq '{name, plugins: [.plugins[] | {name, description, source}]}'
```

## 2. Official MCP registry (no auth needed)

```bash
# One call per term in preferences.registry_searches
curl -s "https://registry.modelcontextprotocol.io/v0.1/servers?search=<term>&version=latest&limit=30" \
  | jq '.servers[] | {name: .server.name, desc: .server.description, version: .server.version,
        repo: .server.repository.url, packages: [.server.packages[]? | {registryType, identifier, version}],
        remotes: [.server.remotes[]? | .url], status: ._meta["io.modelcontextprotocol.registry/official"].status}'
```

For registry hits with a GitHub repo, get stars/pushed with the repo call in section 3.

## 3. GitHub search (sequential; ~30 calls/minute)

```bash
# One call per entry in preferences.github_queries
gh api -X GET search/repositories -f q='<query> archived:false' -f sort=stars -f per_page=20 \
  --jq '.items[] | {repo: .full_name, stars: .stargazers_count, pushed: .pushed_at,
        desc: .description, topics: .topics, license: .license.spdx_id}'

# Find the skill folders inside a promising repo (one call per repo, max limits.max_repos_scanned)
gh api "repos/<repo>/git/trees/HEAD?recursive=1" --jq '.tree[] | select(.path|endswith("SKILL.md")) | .path'

# Read a skill's frontmatter / content
gh api "repos/<repo>/contents/<path>/SKILL.md" -H "Accept: application/vnd.github.raw" | head -40
```

Also search each preferences category by its strongest keywords when a category produced few
results (e.g. `"<keyword> mcp server"`, `"<keyword> claude skill"`).

## 4. Curated lists (endorsement signal)

```bash
# One call per preferences.curated_lists entry; extract GitHub repo links
gh api "repos/<list>/readme" -H "Accept: application/vnd.github.raw" \
  | grep -oE 'github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+' | sed 's#github.com/##' | sort -u
```

A candidate "is listed" in a list if its `owner/repo` appears there.

## 5. Updates for pinned skills

```bash
# For each entry in catalog/skills.yaml
gh api "repos/<repo>/commits?path=<path>&per_page=1" --jq '.[0].sha'
# If different from ref:
gh api "repos/<repo>/compare/<ref>...<new>" --jq '{ahead: .ahead_by, files: [.files[] | select(.filename|startswith("<path>")) | {filename, status, additions, deletions}]}'
gh api "repos/<repo>" --jq '{archived, pushed: .pushed_at}'   # flag archived for removal
```

For pinned MCP packages, compare the pinned version with the latest:
`npm view <pkg> version` / `curl -s https://pypi.org/pypi/<pkg>/json | jq -r .info.version`.
Propose a bump only after reading the changelog/release notes.

## 6. skillshare search and hub

skillshare (the installer this catalog is applied through) has its own GitHub/hub search.
Treat its results like any other source: score and review them, never install from here.

```bash
skillshare search "<query from preferences>" --json --list --limit 30
skillshare search --hub --json --list --limit 30   # the skillshare-hub index
```
