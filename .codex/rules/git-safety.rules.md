# Git Safety Rules

These rules are repository policy for Codex agents. They complement `AGENTS.md`; if a command is
ambiguous, pause and ask the user.

## Forbidden commands

### Hard reset

- decision: forbid
- match:
  - `git reset --hard`
  - `git reset --hard HEAD`
- not_match:
  - `git reset --soft HEAD~1`
  - `git status --short`

### Git clean

- decision: forbid
- match:
  - `git clean -fd`
  - `git clean -fdx`
- not_match:
  - `git status --ignored`
  - `git ls-files --others --exclude-standard`

### Force push

- decision: forbid
- match:
  - `git push --force`
  - `git push --force-with-lease`
- not_match:
  - `git push -u origin main`
  - `git push origin feature/example`

## User confirmation required

### Push

- decision: ask
- match:
  - `git push`
  - `git push -u origin main`
- not_match:
  - `git status -sb`
  - `git diff --stat`

### Pull request creation

- decision: ask
- match:
  - `gh pr create`
  - `gh pr ready`
- not_match:
  - `gh pr view`
  - `gh pr checks`

