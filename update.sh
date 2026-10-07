#!/bin/sh
# Install claude-cleaner from the latest origin/master over the system-wide
# copies, whatever branch this clone has checked out.
#
# Usage: ./update.sh [TARGET...]
#   Without TARGET, every claude-cleaner found on PATH or in the README install
#   dirs (/usr/local/bin, ~/.local/bin) is updated. If there is none, it is
#   installed to the OS default: /usr/local/bin on macOS, ~/.local/bin elsewhere.
#
#   Privileges are only raised for dirs that aren't writable, using the first
#   of sudo or doas found. Set SUDO to pick one, e.g. SUDO=doas.
set -eu

repo="$(cd "$(dirname "$0")" && pwd -P)"

detect_os() {
    case "$(uname -s)" in
        Darwin)
            echo "macOS $(sw_vers -productVersion 2>/dev/null || true)"
            ;;
        Linux)
            if [ -r /etc/os-release ]; then
                (. /etc/os-release && echo "${PRETTY_NAME:-${NAME:-Linux}}")
            else
                echo "Linux"
            fi
            ;;
        *)
            uname -s
            ;;
    esac
}

default_target() {
    if [ "$(uname -s)" = "Darwin" ]; then
        echo "/usr/local/bin/claude-cleaner"
    else
        echo "$HOME/.local/bin/claude-cleaner"
    fi
}

# every existing claude-cleaner on PATH or in a README install dir, one per
# line, resolved to its physical dir so the same file isn't listed twice.
find_installed() {
    {
        printf '%s\n' "$PATH" | tr ':' '\n'
        printf '%s\n' /usr/local/bin "$HOME/.local/bin"
    } | while IFS= read -r d; do
        [ -n "$d" ] && [ -f "$d/claude-cleaner" ] || continue
        echo "$(cd "$d" && pwd -P)/claude-cleaner"
    done | awk '!seen[$0]++'
}

elevate_cmd() {
    if [ -n "${SUDO:-}" ]; then
        echo "$SUDO"
        return 0
    fi
    for t in sudo doas; do
        if command -v "$t" >/dev/null 2>&1; then
            echo "$t"
            return 0
        fi
    done
    return 1
}

install_one() {
    target="$1"
    dir="$(dirname "$target")"

    if [ -f "$target" ] && [ "$(cksum < "$src")" = "$(cksum < "$target")" ]; then
        echo "Already up to date: $target"
        return 0
    fi

    old="none"
    if [ -x "$target" ]; then
        old="$("$target" --version 2>/dev/null || echo unknown)"
    fi

    run=""
    if ! mkdir -p "$dir" 2>/dev/null || [ ! -w "$dir" ] || { [ -e "$target" ] && [ ! -w "$target" ]; }; then
        if [ "$(id -u)" -eq 0 ]; then
            echo "Cannot write to $target, even as root." >&2
            return 1
        fi
        if ! run="$(elevate_cmd)"; then
            echo "No write permission for $dir and neither sudo nor doas found (set SUDO to pick one)." >&2
            return 1
        fi
        echo "Using $run to write to $dir"
    fi

    # one elevated call, so tools without cached credentials ask only once.
    $run sh -c 'mkdir -p "$1" && cp "$2" "$3" && chmod 755 "$3"' sh "$dir" "$src" "$target" || return 1

    echo "Updated $target: $old -> $("$target" --version)"
    case ":$PATH:" in
        *":$dir:"*) ;;
        *) echo "Note: $dir is not on your PATH." ;;
    esac
}

echo "System: $(detect_os)"
git -C "$repo" fetch --quiet origin master
src="$(mktemp)"
# only ever remove the regular file mktemp just created.
trap 'if [ -n "${src:-}" ] && [ -f "$src" ]; then rm -f -- "$src"; fi' EXIT
trap 'exit 130' INT TERM
git -C "$repo" show origin/master:claude_cleaner.py > "$src"
echo "Source: origin/master @ $(git -C "$repo" rev-parse --short origin/master)"

if [ $# -gt 0 ]; then
    targets="$(printf '%s\n' "$@")"
else
    targets="$(find_installed)"
    if [ -z "$targets" ]; then
        targets="$(default_target)"
        echo "No installed claude-cleaner found, installing to $targets"
    fi
fi

# read targets on fd 3 so sudo/doas keep the terminal on stdin.
status=0
while IFS= read -r t <&3; do
    install_one "$t" || status=1
done 3<<EOF
$targets
EOF
exit "$status"
