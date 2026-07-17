# claude-cleaner

> As of Claude Code `2.1.212` (2026-07-17), the native CLI still has no
> built-in way to delete conversations — hence this tool. Courtesy of Sonnet 5 high effort.

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

Marked conversations are highlighted in red; the confirmation dialog shows
the total count and disk space that will be freed. Controls are listed in
the footer of the UI itself (see screenshot above).

## Install system-wide

Copy it onto your `PATH` as `claude-cleaner` so you can just type
`claude-cleaner` from anywhere.

**macOS**

```
sudo cp claude_cleaner.py /usr/local/bin/claude-cleaner
```

**Linux**

```
mkdir -p ~/.local/bin
cp claude_cleaner.py ~/.local/bin/claude-cleaner
```

Make sure `~/.local/bin` is on your `PATH`.

## What gets deleted

For each marked conversation, its `.jsonl` session file is removed, along
with any companion directory of the same session ID (e.g. stored tool
results). Nothing else under `~/.claude` is touched — per-project agent
memory and `~/.claude.json` are left alone.

## Disclaimer

Shipped as-is. Deletion is permanent — no undo, no backup. Use at your own
risk; I take no responsibility for loss of critical data in your
conversations.
