#!/usr/bin/env python3
"""List Claude Code conversations (the ones shown by `/resume`) and delete
the ones you no longer want, via an interactive terminal checklist.

Usage:
    ./claude_cleaner.py [--claude-dir PATH]

Keys in the list view:
    up/down, j/k   move cursor
    space          toggle mark on current row
    a              toggle mark on all currently visible rows
    /              filter by project or title (Enter to apply, Esc to clear)
    s              cycle sort: date added -> a-z -> z-a
    d, enter       delete marked conversations (asks for confirmation)
    q              quit without changing anything
"""

import argparse
import curses
import json
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

__version__ = "1.0.0"


@dataclass
class SessionInfo:
    session_id: str
    project: str
    title: str
    file_path: Path
    extra_dir: Optional[Path]
    mtime: float
    size_bytes: int


def human_size(n: int) -> str:
    size = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f}{unit}" if unit == "B" else f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}GB"


def human_time(mtime: float) -> str:
    seconds = time.time() - mtime
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{int(seconds // 60)}m ago"
    if seconds < 86400:
        return f"{int(seconds // 3600)}h ago"
    if seconds < 86400 * 30:
        return f"{int(seconds // 86400)}d ago"
    return time.strftime("%Y-%m-%d", time.localtime(mtime))


def extract_text(content) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text", "").strip()
                if text:
                    return text
    return ""


def decode_project_fallback(dir_name: str) -> str:
    if dir_name.startswith("-"):
        return "/" + dir_name[1:].replace("-", "/")
    return dir_name


def dir_size(path: Path) -> int:
    total = 0
    for p in path.rglob("*"):
        if p.is_file():
            try:
                total += p.stat().st_size
            except OSError:
                pass
    return total


def parse_session(jsonl_path: Path, project_dir: Path) -> Optional[SessionInfo]:
    try:
        stat = jsonl_path.stat()
    except OSError:
        return None

    session_id = jsonl_path.stem
    cwd = None
    ai_title = None
    fallback_title = None

    try:
        with jsonl_path.open("r", errors="replace") as f:
            for raw in f:
                if cwd is not None and fallback_title is not None and '"aiTitle"' not in raw:
                    continue
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    d = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if cwd is None:
                    c = d.get("cwd")
                    if c:
                        cwd = c
                t = d.get("type")
                if t == "ai-title":
                    at = d.get("aiTitle")
                    if at:
                        ai_title = at
                elif t == "user" and fallback_title is None and not d.get("isSidechain"):
                    text = extract_text(d.get("message", {}).get("content"))
                    if text and not text.startswith("<"):
                        fallback_title = " ".join(text.split())[:80]
    except OSError:
        return None

    title = ai_title or fallback_title or "(empty conversation)"
    project = cwd or decode_project_fallback(project_dir.name)

    extra_dir = project_dir / session_id
    size = stat.st_size
    if extra_dir.is_dir():
        size += dir_size(extra_dir)
    else:
        extra_dir = None

    return SessionInfo(
        session_id=session_id,
        project=project,
        title=title,
        file_path=jsonl_path,
        extra_dir=extra_dir,
        mtime=stat.st_mtime,
        size_bytes=size,
    )


def scan_sessions(claude_dir: Path) -> List[SessionInfo]:
    projects_dir = claude_dir / "projects"
    sessions: List[SessionInfo] = []
    if not projects_dir.is_dir():
        return sessions
    for project_dir in sorted(projects_dir.iterdir()):
        if not project_dir.is_dir():
            continue
        for jsonl_path in sorted(project_dir.glob("*.jsonl")):
            info = parse_session(jsonl_path, project_dir)
            if info:
                sessions.append(info)
    sessions.sort(key=lambda s: s.mtime, reverse=True)
    return sessions


def delete_session(info: SessionInfo) -> None:
    info.file_path.unlink(missing_ok=True)
    if info.extra_dir is not None and info.extra_dir.is_dir():
        shutil.rmtree(info.extra_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Interactive UI
# ---------------------------------------------------------------------------

def init_colors() -> bool:
    if not curses.has_colors():
        return False
    curses.start_color()
    try:
        curses.use_default_colors()
        bg = -1
    except curses.error:
        bg = curses.COLOR_BLACK
    curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_CYAN)   # header bar
    curses.init_pair(2, curses.COLOR_RED, bg)                    # marked row
    curses.init_pair(3, curses.COLOR_BLACK, curses.COLOR_WHITE)  # cursor row
    curses.init_pair(4, curses.COLOR_WHITE, curses.COLOR_RED)    # cursor on marked row
    curses.init_pair(5, curses.COLOR_CYAN, bg)                   # footer
    curses.init_pair(6, curses.COLOR_RED, bg)                    # delete confirmation
    return True


def run_ui(stdscr, sessions: List[SessionInfo]) -> List[SessionInfo]:
    curses.curs_set(0)
    stdscr.keypad(True)
    has_color = init_colors()

    selected = set()
    cursor = 0
    top = 0
    query = ""
    mode = "list"  # list | filter | confirm
    sort_modes = ["date", "alpha", "alpha_rev"]
    sort_labels = {"date": "date", "alpha": "a-z", "alpha_rev": "z-a"}
    sort_mode = "date"

    def visible_indices():
        if not query:
            idxs = list(range(len(sessions)))
        else:
            q = query.lower()
            idxs = [
                i for i, s in enumerate(sessions)
                if q in s.title.lower() or q in s.project.lower()
            ]
        # sessions is already ordered newest-first, so "date" needs no re-sort.
        if sort_mode == "alpha":
            idxs.sort(key=lambda i: sessions[i].title.lower())
        elif sort_mode == "alpha_rev":
            idxs.sort(key=lambda i: sessions[i].title.lower(), reverse=True)
        return idxs

    while True:
        indices = visible_indices()
        if cursor >= len(indices):
            cursor = max(0, len(indices) - 1)

        height, width = stdscr.getmaxyx()
        stdscr.erase()

        header = (
            f" Claude conversations  ({len(indices)} shown, {len(selected)} marked, "
            f"sort: {sort_labels[sort_mode]}) "
        )
        header_attr = (curses.color_pair(1) | curses.A_BOLD) if has_color else curses.A_REVERSE
        stdscr.addnstr(0, 0, header.ljust(width), width, header_attr)

        list_top = 2
        footer_h = 2
        visible_rows = max(0, height - list_top - footer_h)

        if cursor < top:
            top = cursor
        if visible_rows > 0 and cursor >= top + visible_rows:
            top = cursor - visible_rows + 1

        proj_w = max(10, min(28, width // 4))
        time_w = 10
        size_w = 7
        title_w = max(10, width - proj_w - time_w - size_w - 8)

        for row in range(visible_rows):
            idx_pos = top + row
            if idx_pos >= len(indices):
                break
            i = indices[idx_pos]
            s = sessions[i]
            is_marked = i in selected
            is_cursor = idx_pos == cursor
            mark = "[x]" if is_marked else "[ ]"
            proj_name = Path(s.project).name or s.project
            line = (
                f"{mark} "
                f"{proj_name[:proj_w].ljust(proj_w)} "
                f"{s.title[:title_w].ljust(title_w)} "
                f"{human_time(s.mtime).rjust(time_w)} "
                f"{human_size(s.size_bytes).rjust(size_w)}"
            )
            if has_color:
                if is_cursor and is_marked:
                    attr = curses.color_pair(4) | curses.A_BOLD
                elif is_cursor:
                    attr = curses.color_pair(3)
                elif is_marked:
                    attr = curses.color_pair(2) | curses.A_BOLD
                else:
                    attr = curses.A_NORMAL
            else:
                attr = curses.A_REVERSE if is_cursor else curses.A_NORMAL
                if is_marked:
                    attr |= curses.A_BOLD
            stdscr.addnstr(list_top + row, 0, line, width, attr)

        if mode == "filter":
            footer = f" filter: {query}_"
        else:
            footer = " space:mark  a:all  /:filter  s:sort  d:delete  q:quit"
        footer_attr = (curses.color_pair(5) | curses.A_DIM) if has_color else curses.A_DIM
        # writing into the terminal's bottom-right cell raises curses.error, so
        # stay one column short of the full width on the last line.
        stdscr.addnstr(height - 1, 0, footer.ljust(width), max(0, width - 1), footer_attr)

        if mode == "confirm":
            marked = [sessions[i] for i in sorted(selected)]
            total = sum(s.size_bytes for s in marked)
            box_h = min(height - 2, len(marked) + 5)
            box_w = min(width - 4, 78)
            win = curses.newwin(box_h, box_w, (height - box_h) // 2, (width - box_w) // 2)
            border_attr = (curses.color_pair(6) | curses.A_BOLD) if has_color else curses.A_BOLD
            win.attrset(border_attr)
            win.box()
            win.attrset(curses.A_NORMAL)
            win.addnstr(1, 2, f"Delete {len(marked)} conversation(s), freeing {human_size(total)}?", box_w - 4, border_attr)
            for i, s in enumerate(marked[: box_h - 5]):
                proj_name = Path(s.project).name or s.project
                row_attr = curses.color_pair(2) if has_color else curses.A_NORMAL
                win.addnstr(3 + i, 2, f"- {proj_name}: {s.title}"[: box_w - 4], box_w - 4, row_attr)
            win.addnstr(box_h - 2, 2, "y: confirm    any other key: cancel", box_w - 4, curses.A_DIM)
            win.refresh()
            key = win.getch()
            mode = "list"
            if key in (ord("y"), ord("Y")):
                return marked
            continue

        stdscr.refresh()
        key = stdscr.getch()

        if mode == "filter":
            if key in (10, 13):
                mode = "list"
            elif key == 27:  # Esc
                query = ""
                mode = "list"
            elif key in (curses.KEY_BACKSPACE, 127, 8):
                query = query[:-1]
            elif 32 <= key <= 126:
                query += chr(key)
            continue

        if key in (curses.KEY_UP, ord("k")):
            cursor = max(0, cursor - 1)
        elif key in (curses.KEY_DOWN, ord("j")):
            cursor = min(max(0, len(indices) - 1), cursor + 1)
        elif key == curses.KEY_HOME:
            cursor = 0
        elif key == curses.KEY_END:
            cursor = max(0, len(indices) - 1)
        elif key == curses.KEY_NPAGE:
            cursor = min(max(0, len(indices) - 1), cursor + visible_rows)
        elif key == curses.KEY_PPAGE:
            cursor = max(0, cursor - visible_rows)
        elif key == ord(" "):
            if indices:
                i = indices[cursor]
                if i in selected:
                    selected.discard(i)
                else:
                    selected.add(i)
                cursor = min(max(0, len(indices) - 1), cursor + 1)
        elif key == ord("a"):
            if indices and all(i in selected for i in indices):
                selected.difference_update(indices)
            else:
                selected.update(indices)
        elif key == ord("/"):
            mode = "filter"
        elif key == ord("s"):
            current_id = sessions[indices[cursor]].session_id if indices else None
            sort_mode = sort_modes[(sort_modes.index(sort_mode) + 1) % len(sort_modes)]
            if current_id is not None:
                for pos, i in enumerate(visible_indices()):
                    if sessions[i].session_id == current_id:
                        cursor = pos
                        break
        elif key in (10, 13, ord("d")):
            if selected:
                mode = "confirm"
        elif key == ord("q"):
            return []


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--claude-dir", type=Path, default=Path.home() / ".claude",
                         help="Path to the Claude Code config dir (default: ~/.claude)")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = parser.parse_args()

    print("Scanning conversations...")
    sessions = scan_sessions(args.claude_dir)
    if not sessions:
        print(f"No conversations found under {args.claude_dir / 'projects'}")
        return

    marked = curses.wrapper(run_ui, sessions)

    if not marked:
        print("No changes made.")
        return

    freed = 0
    errors = []
    for s in marked:
        try:
            delete_session(s)
            freed += s.size_bytes
            print(f"deleted {s.session_id}  ({Path(s.project).name}: {s.title})")
        except OSError as e:
            errors.append((s, e))

    print(f"\nFreed {human_size(freed)} across {len(marked) - len(errors)} conversation(s).")
    if errors:
        print(f"{len(errors)} failed to delete:")
        for s, e in errors:
            print(f"  {s.session_id}: {e}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelled.")
