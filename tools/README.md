# Opportunity tools

## `bounty_claimability.py`

Read-only preflight for GitHub bounty issues. It helps decide whether an issue is worth spending another request or implementation cycle on before claiming it.

```bash
python tools/bounty_claimability.py https://github.com/OWNER/REPO/issues/123
```

Optional authenticated requests use `GITHUB_TOKEN`; the token is never written to disk. The helper uses a one-hour cache by default, performs at most four uncached GitHub API reads per audit, does not retry throttled requests, and reports `Retry-After`/rate-limit blockers instead of trying to evade them.

The result is intentionally conservative: `apparently-open`, `needs-verification`, `contested`, `resolved-or-stale`, or `blocked`. Treat it as a triage signal, not proof that a bounty is funded. Before implementation, verify the canonical issue, current payout mechanism, acceptance criteria, competing work, and maintainer activity.
