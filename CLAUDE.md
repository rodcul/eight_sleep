# rodcul/eight_sleep

A fork of [lukas-clarke/eight_sleep](https://github.com/lukas-clarke/eight_sleep).
Nobody here runs it as a Home Assistant integration. It is the **source of
truth for Eight Sleep API knowledge** for HF0's fleet app (private repo
`rodcul/hf0-8sleep`, which reimplements the client in TypeScript).

This repo is public: write API facts generically, with no account emails,
names, hub serials or HF0 internals.

## API knowledge

`docs/api-notes.md` is where API facts live. When you learn something about the
API, from upstream code, a live read, or the app, record it there with the date
and mark it Seen / In code / Unverified.

## Upstream

**At the start of a session, check upstream for new learning:**

1. `git fetch upstream`, then list open PRs and recent merges:
   `gh pr list --repo lukas-clarke/eight_sleep --state all --limit 20`.
2. Compare against the last dated section of `docs/upstream-log.md`.
3. For anything new, read it for endpoints, response fields and gotchas, and
   add them to `docs/api-notes.md`. If a change is worth carrying, cherry-pick it
   with `git cherry-pick -x` so the original author's commit is kept, and open a
   PR on this fork.
4. Add a dated section to `docs/upstream-log.md`: taken, skipped, and why.

Done when every upstream PR and merge since the last log entry has a line in
the log.

**Upstream is read-only.** All pushes, comments and PRs go to `rodcul/eight_sleep`.
`gh` defaults to the parent repo on a fork, so pass `--repo rodcul/eight_sleep`
on every `gh pr` / `gh issue` write.

If upstream changes the client id, client secret or user-agent in
`pyEight/constants.py`, raise it at once: the HF0 app uses the same pair and
breaks the same day.

## Tests

They need Home Assistant installed. Use a throwaway venv (Python 3.13) with
`homeassistant pytest pytest-asyncio`, then
`python -m pytest tests custom_components/eight_sleep/pyEight/tests`.
Four tests in `test_auth`, `test_eight` and `test_speaker` already fail on
upstream main.

## Agent skills

### Issue tracker

Issues live in GitHub Issues on the fork `rodcul/eight_sleep` (not upstream). See `docs/agents/issue-tracker.md`.

### Triage labels

Default five labels: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `GLOSSARY.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.
