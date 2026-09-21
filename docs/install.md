# Install prompt2jev with your agent

## For people

Copy this into Claude Code, Codex, OpenCode, Cursor, or Gemini CLI:

```text
Install the prompt2jev skill from
https://raw.githubusercontent.com/sumleo/prompt2jev/main/docs/install.md
into this project. Check my environment, install project-local, verify offline
with a dry run, and do not make a paid call.
```

The agent needs file access and permission to run a few shell commands. You may be
asked to approve a clone or a copy. Never paste an API key into the chat.

## For the installing agent

### Outcome

The folder `skills/prompt2jev/` from this repository, copied whole into the current
host's project-local skills directory, verified with an offline dry run. The skill is
self-contained: `SKILL.md`, `references/`, `assets/`, and `scripts/prompt2jev.py`.
Nothing else from the repository is needed at runtime.

This is an installation task. It is not permission to change the agent's model,
hooks, MCP servers, other skills, shell profiles, or to store credentials.

### 1. Identify the host and destination

| Host | Destination under the project root |
|---|---|
| Claude Code | `.claude/skills/prompt2jev/` |
| Codex | `.agents/skills/prompt2jev/` |
| OpenCode | `.opencode/skills/prompt2jev/` |
| Cursor | `.cursor/skills/prompt2jev/` |
| Gemini CLI | `.gemini/skills/prompt2jev/` |

Identify the host from the session, not from installed binaries. Say which host and
destination you chose before writing. If a `prompt2jev` folder already exists there,
compare it with the source and ask before replacing a modified copy.

### 2. Check prerequisites

- Git, or a way to download the repository archive.
- Python 3.10+ for the validator (`python3 --version`). It is only needed to run
  `scripts/prompt2jev.py`; the skill text works without it.
- Optionally `uv` or `pipx` if the user wants the `prompt2jev` command on PATH.

Do not install Python or package tools without asking.

### 3. Fetch the source

```bash
work=$(mktemp -d)
git clone --depth 1 https://github.com/sumleo/prompt2jev "$work/source"
```

Read `skills/prompt2jev/SKILL.md` and `skills/prompt2jev/scripts/prompt2jev.py`
before running anything from the download.

### 4. Copy the skill folder

Copy `$work/source/skills/prompt2jev` to the destination from step 1, preserving
the folder name and all subfolders. Do not copy `.git`, the docs mirror, or the tests.

### 5. Verify offline

```bash
python3 <destination>/scripts/prompt2jev.py run <destination>/assets/classify-route.json --dry-run
python3 <destination>/scripts/prompt2jev.py validate <destination>/assets/checklist-guardrail.json --strict
```

Both must exit 0 and print the request. Neither contacts the network. Then:

```bash
python3 <destination>/scripts/prompt2jev.py setup
```

This reports whether `TYPESAFE_API_KEY` or `OPENROUTER_API_KEY` is present without
printing a value. A present key is not proof that it works; only a live call is, and
that costs money, so do not make one during installation.

### 6. Optional: install the command

Only if the user asks for a `prompt2jev` command:

```bash
uv tool install "$work/source"
# or: pipx install "$work/source"
```

Report where it was installed and whether PATH needs a new shell.

### 7. Report

State the host and destination, the files copied, which offline checks passed, whether
a key is present, and what the user still needs to do (get a key from
https://console.typesafe.ai/keys, restart or reload the host so it discovers the new
skill). Offer a first prompt:

> Use the prompt2jev skill to convert the classifier prompt in `<file>` into a Jev
> decision. Validate the request before showing it; do not make a live call yet.
