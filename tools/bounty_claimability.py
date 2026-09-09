#!/usr/bin/env python3
"""Conservative GitHub bounty claimability audit.

Read-only, stdlib-only helper for deciding whether an issue is worth revisiting.
It intentionally minimizes requests, caches recent responses, honors Retry-After,
and never claims, comments on, or modifies remote issues.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

API = "https://api.github.com"
DEFAULT_TTL = 3600
CACHE_DIR = Path(os.environ.get("BOUNTY_AUDIT_CACHE", Path.home() / ".cache" / "bounty-audit"))
MONEY_RE = re.compile(r"(?i)(?:\$|USD\s*)(\d+(?:[.,]\d{1,2})?)|(?:\b(\d+(?:[.,]\d{1,2})?)\s*USD\b)")
BOUNTY_WORDS = ("bounty", "reward", "paid", "prize", "price:", "algora", "opire")


def parse_issue_url(value: str) -> tuple[str, str, int]:
    match = re.fullmatch(r"https?://github\.com/([^/]+)/([^/]+)/issues/(\d+)(?:/.*)?", value.strip())
    if not match:
        raise ValueError("Expected GitHub issue URL: https://github.com/OWNER/REPO/issues/123")
    return match.group(1), match.group(2), int(match.group(3))


def cache_path(url: str) -> Path:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
    return CACHE_DIR / f"{digest}.json"


def read_cache(url: str, ttl: int) -> Any | None:
    path = cache_path(url)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if time.time() - float(payload.get("saved_at", 0)) <= ttl:
        return payload.get("data")
    return None


def write_cache(url: str, data: Any) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = cache_path(url)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps({"saved_at": time.time(), "data": data}), encoding="utf-8")
    temp.replace(path)


def github_get(url: str, *, ttl: int, token: str | None) -> Any:
    cached = read_cache(url, ttl)
    if cached is not None:
        return cached

    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "bounty-claimability-audit/1.0",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=15) as response:
            remaining = response.headers.get("X-RateLimit-Remaining")
            reset = response.headers.get("X-RateLimit-Reset")
            if remaining == "0":
                raise RuntimeError(f"GitHub rate limit exhausted; reset={reset}. No retry attempted.")
            data = json.load(response)
            write_cache(url, data)
            return data
    except HTTPError as exc:
        retry_after = exc.headers.get("Retry-After") if exc.headers else None
        if exc.code in (403, 429):
            detail = f" Retry-After={retry_after}s." if retry_after else ""
            raise RuntimeError(f"GitHub throttled the request ({exc.code}).{detail} No retry attempted.") from exc
        raise RuntimeError(f"GitHub request failed with HTTP {exc.code}; no retry attempted.") from exc
    except URLError as exc:
        raise RuntimeError(f"Network error: {exc.reason}; no retry attempted.") from exc


def money_mentions(text: str) -> list[str]:
    values: list[str] = []
    for match in MONEY_RE.finditer(text or ""):
        raw = match.group(1) or match.group(2)
        if raw:
            values.append(raw.replace(",", "."))
    return values


def contains_bounty_signal(text: str) -> bool:
    lowered = (text or "").lower()
    return any(word in lowered for word in BOUNTY_WORDS)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("issue_url")
    parser.add_argument("--ttl", type=int, default=DEFAULT_TTL, help="Cache TTL seconds (default: 3600)")
    parser.add_argument("--max-comments", type=int, default=30, help="Maximum recent comments to inspect")
    args = parser.parse_args()

    if args.ttl < 300:
        parser.error("--ttl must be at least 300 seconds to keep request volume conservative")
    if not 0 <= args.max_comments <= 100:
        parser.error("--max-comments must be between 0 and 100")

    try:
        owner, repo, number = parse_issue_url(args.issue_url)
    except ValueError as exc:
        parser.error(str(exc))

    token = os.environ.get("GITHUB_TOKEN")
    repo_url = f"{API}/repos/{owner}/{repo}"
    issue_url = f"{repo_url}/issues/{number}"

    try:
        repo_data = github_get(repo_url, ttl=args.ttl, token=token)
        issue_data = github_get(issue_url, ttl=args.ttl, token=token)

        comments: list[dict[str, Any]] = []
        if args.max_comments and int(issue_data.get("comments", 0)):
            per_page = min(args.max_comments, 100)
            comments_url = f"{issue_url}/comments?per_page={per_page}&sort=created&direction=desc"
            comments = github_get(comments_url, ttl=args.ttl, token=token)

        query = quote(f'repo:{owner}/{repo} is:pr "#{number}"', safe="")
        prs_data = github_get(f"{API}/search/issues?q={query}&per_page=20", ttl=args.ttl, token=token)
    except RuntimeError as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)}, indent=2))
        return 2

    labels = [label.get("name", "") for label in issue_data.get("labels", []) if isinstance(label, dict)]
    body = issue_data.get("body") or ""
    title = issue_data.get("title") or ""
    comment_text = "\n".join(str(item.get("body") or "") for item in comments)
    all_text = "\n".join([title, body, " ".join(labels), comment_text])
    amounts = money_mentions(all_text)
    related_prs = prs_data.get("items", []) if isinstance(prs_data, dict) else []

    reasons: list[str] = []
    risk = 0
    if repo_data.get("archived"):
        reasons.append("repository is archived")
        risk += 5
    if issue_data.get("state") != "open":
        reasons.append(f"issue state is {issue_data.get('state')}")
        risk += 5
    if issue_data.get("locked"):
        reasons.append("issue conversation is locked")
        risk += 2
    if issue_data.get("assignees"):
        reasons.append("issue already has assignee(s)")
        risk += 1
    if not contains_bounty_signal(all_text):
        reasons.append("no clear bounty/reward signal found")
        risk += 2
    if not amounts:
        reasons.append("no explicit USD amount found")
        risk += 1
    if related_prs:
        reasons.append(f"{len(related_prs)} possibly related PR(s) found")
        risk += min(3, len(related_prs))

    status = "apparently-open"
    if risk >= 5:
        status = "resolved-or-stale"
    elif risk >= 3:
        status = "contested"
    elif risk >= 1:
        status = "needs-verification"

    output = {
        "status": status,
        "issue": args.issue_url,
        "repository_archived": bool(repo_data.get("archived")),
        "issue_state": issue_data.get("state"),
        "locked": bool(issue_data.get("locked")),
        "assignees": [a.get("login") for a in issue_data.get("assignees", []) if isinstance(a, dict)],
        "labels": labels,
        "usd_mentions": amounts[:10],
        "comments_inspected": len(comments),
        "possible_related_prs": [
            {"number": pr.get("number"), "title": pr.get("title"), "url": pr.get("html_url")}
            for pr in related_prs[:10]
        ],
        "reasons": reasons,
        "request_policy": {
            "cache_ttl_seconds": args.ttl,
            "no_rapid_retry": True,
            "max_remote_requests_per_uncached_audit": 4,
        },
    }
    print(json.dumps(output, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
