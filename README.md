# claude-cleaner

> As of Claude Code `2.1.289` (2026-10-05), the native CLI still has no
> built-in way to delete conversations — hence this tool. Courtesy of Opus 5.5 high effort.

A small terminal tool to list and delete Claude Code conversations — the
sessions shown by the `/resume` command. Claude Code has no built-in way to
clean these up, so this fills the gap with an interactive checklist UI.

It scans `~/.claude/projects/*/*.jsonl` across all your projects, shows each
conversation's project, title, last-modified time, and disk size, and lets
you mark any number of them for deletion before confirming.

Pure Python standard library — no dependencies to install.

![screenshot](demo/screenshot.png)

## Usage

```
./claude_cleaner.py [--claude-dir PATH]
```

- `--claude-dir PATH` — path to the Claude Code config dir (default: `~/.claude`)
- `--version` — print the version and exit

## Install system-wide

Copy it onto your `PATH` as `claude-cleaner`. For quick use, alias it in
`.bashrc` or `.zshrc`: `alias cc="claude-cleaner"`.

**macOS**

```
sudo cp claude_cleaner.py /usr/local/bin/claude-cleaner
```

**Linux**

```
cp claude_cleaner.py ~/.local/bin/claude-cleaner
```

Make sure `~/.local/bin` is on your `PATH`.

## Update

From your clone, run:

```
./update.sh
```

It fetches the latest `master` from GitHub, whatever branch your clone is on,
and updates every `claude-cleaner` it finds on your `PATH` or in the install
locations above. Works on macOS and Linux with plain
`sh`, no bash needed. If nothing is installed yet, it installs to
`/usr/local/bin` on macOS or `~/.local/bin` on Linux. Pass paths to update
specific copies instead: `./update.sh ~/bin/claude-cleaner`.

Privileges are only raised for locations you can't write to, using `sudo` or
`doas`, whichever is found first. Pick one explicitly with
`SUDO=doas ./update.sh`.

## What gets deleted

For each marked conversation, its `.jsonl` session file is removed, along
with any companion directory of the same session ID (e.g. stored tool
results). Nothing else under `~/.claude` is touched — per-project agent
memory and `~/.claude.json` are left alone.

## Disclaimer

Shipped as-is. Deletion is permanent — no undo, no backup. Use at your own
risk; I take no responsibility for loss of critical data in your
conversations.
