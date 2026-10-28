"""Refresh the auto-generated sections of README.md from the GitHub API.

Sections are delimited by <!--START_SECTION:name--> / <!--END_SECTION:name-->.
"""
import datetime
import json
import os
import re
import urllib.request

USER = os.environ.get("GH_USER", "fajis")
TOKEN = os.environ.get("GITHUB_TOKEN")
README = os.path.join(os.path.dirname(__file__), "..", "README.md")


def api(path):
    req = urllib.request.Request(f"https://api.github.com{path}")
    req.add_header("Accept", "application/vnd.github+json")
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req) as resp:
        return json.load(resp)


def icon(name, size=16):
    return f'<img src="assets/icons/{name}.svg" width="{size}" height="{size}" align="top"/>'


def describe(event):
    # The events API trims payloads (e.g. PRs may lack html_url), so read everything defensively.
    repo = event["repo"]["name"]
    repo_url = f"https://github.com/{repo}"
    link = f"[{repo}]({repo_url})"
    p = event.get("payload") or {}
    kind = event["type"]
    if kind == "PushEvent":
        n = p.get("size") or len(p.get("commits") or []) or 1
        return f"{icon('git-commit-horizontal')} Pushed {n} commit{'s' if n != 1 else ''} to {link}"
    if kind == "CreateEvent":
        if p.get("ref_type") == "repository":
            return f"{icon('folder-plus')} Created repository {link}"
        return f"{icon('git-branch')} Created {p.get('ref_type', 'ref')} `{p.get('ref')}` in {link}"
    if kind == "PullRequestEvent":
        pr = p.get("pull_request") or {}
        num = pr.get("number") or p.get("number")
        url = pr.get("html_url") or f"{repo_url}/pull/{num}"
        action = (p.get("action") or "updated").capitalize()
        if action == "Closed" and pr.get("merged"):
            action = "Merged"
        return f"{icon('git-pull-request')} {action} PR [#{num}]({url}) in {link}"
    if kind == "IssuesEvent":
        issue = p.get("issue") or {}
        num = issue.get("number")
        url = issue.get("html_url") or f"{repo_url}/issues/{num}"
        return f"{icon('circle-dot')} {(p.get('action') or 'updated').capitalize()} issue [#{num}]({url}) in {link}"
    if kind == "IssueCommentEvent":
        issue = p.get("issue") or {}
        num = issue.get("number")
        url = (p.get("comment") or {}).get("html_url") or f"{repo_url}/issues/{num}"
        return f"{icon('message-square')} Commented on [#{num}]({url}) in {link}"
    if kind == "ReleaseEvent":
        rel = p.get("release") or {}
        tag = rel.get("tag_name", "a release")
        url = rel.get("html_url") or f"{repo_url}/releases"
        return f"{icon('tag')} Released [{tag}]({url}) in {link}"
    if kind == "WatchEvent":
        return f"{icon('star')} Starred {link}"
    if kind == "ForkEvent":
        return f"{icon('git-fork')} Forked {link}"
    if kind == "PublicEvent":
        return f"{icon('globe')} Open-sourced {link}"
    return None


def recent_activity(limit=6):
    lines = []
    for event in api(f"/users/{USER}/events/public?per_page=100"):
        if event["actor"]["login"].lower() != USER.lower():
            continue
        # Skip the bot commits this workflow makes to the profile repo.
        if event["type"] == "PushEvent" and event["repo"]["name"].lower() == f"{USER}/{USER}".lower():
            continue
        try:
            text = describe(event)
        except (KeyError, TypeError, AttributeError):
            continue
        if text and text not in lines:
            lines.append(text)
        if len(lines) == limit:
            break
    if not lines:
        return "_No recent public activity._"
    return "\n".join(f"{i}. {line}" for i, line in enumerate(lines, 1))


def latest_repos(limit=5):
    repos = api(f"/users/{USER}/repos?sort=pushed&per_page=30&type=owner")
    rows = []
    for r in repos:
        if r["fork"] or r["name"].lower() == USER.lower():
            continue
        desc = (r["description"] or "—").replace("|", "\\|")
        lang = r["language"] or "—"
        pushed = r["pushed_at"][:10]
        rows.append(f"| [{r['name']}]({r['html_url']}) | {desc} | {lang} | {r['stargazers_count']} | {pushed} |")
        if len(rows) == limit:
            break
    if not rows:
        return "_No public repositories yet._"
    header = "| Repository | Description | Language | Stars | Last push |\n| :-- | :-- | :-: | :-: | :-: |"
    return header + "\n" + "\n".join(rows)


def replace_section(text, name, body):
    pattern = re.compile(
        rf"(<!--START_SECTION:{name}-->\n).*?(\n<!--END_SECTION:{name}-->)", re.S
    )
    return pattern.sub(lambda m: m.group(1) + body + m.group(2), text)


def main():
    with open(README, encoding="utf-8") as f:
        text = f.read()
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%d %b %Y, %H:%M UTC")
    text = replace_section(text, "activity", recent_activity())
    text = replace_section(text, "repos", latest_repos())
    text = replace_section(
        text, "updated",
        f'<p align="center"><sub>{icon("bot", 14)} This profile updates itself daily · Last refreshed: {now}</sub></p>',
    )
    with open(README, "w", encoding="utf-8") as f:
        f.write(text)


if __name__ == "__main__":
    main()
