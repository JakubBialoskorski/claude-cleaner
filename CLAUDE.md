# Conventions

## Commits
- Lowercase first letter in commit message subjects
- Short subject line only, no extended commit body
- Prefix with a bracketed tag describing the type of change, e.g. `[fix]`, `[docs]`, `[feat]`

## Pull Requests
- PR titles always start with a capital letter
- Keep descriptions short, no extended descriptions
- Do not include summary or test plan blocks in the description

## Versioning
- Every PR that changes `claude_cleaner.py` bumps `__version__` in the same PR — `update.sh` installs only released versions, so an unbumped change never reaches users
- Fixes and small changes bump the last number (`1.1.0` → `1.1.1`), new features bump the middle one and reset the last (`1.1.1` → `1.2.0`)
- Merging the bump to `master` creates the `vX.Y.Z` tag and GitHub release automatically
