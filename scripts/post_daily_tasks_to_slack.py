#!/usr/bin/env python3
"""毎朝 today ラベル付きの open Issue を Slack に投稿する。"""

import os
import sys
from collections import defaultdict

import requests
import yaml

GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
SLACK_WEBHOOK_URL = os.environ["SLACK_WEBHOOK_URL"]

PRIORITY_ORDER = {"priority:p0": 0, "priority:p1": 1, "priority:p2": 2}

AREA_DISPLAY = {
    "area:mia": "Mia",
    "area:ai-cooking": "AI Cooking",
    "area:blog": "Blog",
    "area:study": "Study",
    "area:research": "Research",
    "area:admin": "Admin",
}


def load_repos() -> list[dict]:
    with open("config/repos.yml") as f:
        return yaml.safe_load(f)["repos"]


def fetch_today_issues(owner: str, repo: str) -> list[dict]:
    url = f"https://api.github.com/repos/{owner}/{repo}/issues"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    params = {"state": "open", "labels": "today", "per_page": 100}
    resp = requests.get(url, headers=headers, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def issue_priority(issue: dict) -> int:
    labels = {lb["name"] for lb in issue["labels"]}
    for p, order in PRIORITY_ORDER.items():
        if p in labels:
            return order
    return 99


def issue_area(issue: dict) -> str:
    labels = {lb["name"] for lb in issue["labels"]}
    for area in AREA_DISPLAY:
        if area in labels:
            return area
    return "area:admin"


def build_slack_message(grouped: dict[str, list[dict]]) -> str:
    lines = ["*今日のタスク*\n"]
    for area_key, display in AREA_DISPLAY.items():
        issues = grouped.get(area_key, [])
        if not issues:
            continue
        lines.append(f"*{display}*")
        for issue in sorted(issues, key=issue_priority):
            lines.append(f"・{issue['title']}")
        lines.append("")
    return "\n".join(lines).strip()


def post_to_slack(text: str) -> None:
    resp = requests.post(
        SLACK_WEBHOOK_URL,
        json={"text": text},
        timeout=30,
    )
    resp.raise_for_status()


def main() -> None:
    repos = load_repos()
    all_issues: list[dict] = []

    for repo in repos:
        issues = fetch_today_issues(repo["owner"], repo["name"])
        all_issues.extend(issues)

    if not all_issues:
        print("today ラベル付きの open Issue がありません。投稿をスキップします。")
        return

    grouped: dict[str, list[dict]] = defaultdict(list)
    for issue in all_issues:
        grouped[issue_area(issue)].append(issue)

    message = build_slack_message(grouped)
    post_to_slack(message)
    print(f"投稿完了: {len(all_issues)} 件")


if __name__ == "__main__":
    main()
