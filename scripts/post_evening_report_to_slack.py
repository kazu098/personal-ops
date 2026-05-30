#!/usr/bin/env python3
"""毎晩、当日 close された Issue と未完了 today Issue を Slack に報告する。"""

import os
from datetime import datetime, timezone, timedelta

import requests
import yaml

GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
SLACK_WEBHOOK_URL = os.environ["SLACK_WEBHOOK_URL"]

JST = timezone(timedelta(hours=9))

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


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def fetch_closed_today(owner: str, repo: str) -> list[dict]:
    """当日 (JST) にクローズされた Issue を返す。"""
    today_jst = datetime.now(JST).date()
    url = f"https://api.github.com/repos/{owner}/{repo}/issues"
    params = {"state": "closed", "per_page": 100}
    resp = requests.get(url, headers=_headers(), params=params, timeout=30)
    resp.raise_for_status()

    result = []
    for issue in resp.json():
        if issue.get("pull_request"):
            continue
        closed_at = datetime.fromisoformat(issue["closed_at"].replace("Z", "+00:00"))
        if closed_at.astimezone(JST).date() == today_jst:
            result.append(issue)
    return result


def fetch_open_today(owner: str, repo: str) -> list[dict]:
    """today ラベル付きの open Issue を返す。"""
    url = f"https://api.github.com/repos/{owner}/{repo}/issues"
    params = {"state": "open", "labels": "today", "per_page": 100}
    resp = requests.get(url, headers=_headers(), params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def area_prefix(issue: dict) -> str:
    labels = {lb["name"] for lb in issue["labels"]}
    for area, display in AREA_DISPLAY.items():
        if area in labels:
            return display
    return "その他"


def build_message(closed: list[dict], open_today: list[dict]) -> str:
    lines = ["*今日の完了報告*\n"]

    lines.append("*完了*")
    if closed:
        for issue in closed:
            lines.append(f"・{area_prefix(issue)}：{issue['title']}")
    else:
        lines.append("・なし")

    lines.append("")
    lines.append("*未完了*")
    if open_today:
        for issue in open_today:
            lines.append(f"・{area_prefix(issue)}：{issue['title']}")
    else:
        lines.append("・なし")

    return "\n".join(lines).strip()


def post_to_slack(text: str) -> None:
    resp = requests.post(SLACK_WEBHOOK_URL, json={"text": text}, timeout=30)
    resp.raise_for_status()


def main() -> None:
    repos = load_repos()
    all_closed: list[dict] = []
    all_open_today: list[dict] = []

    for repo in repos:
        all_closed.extend(fetch_closed_today(repo["owner"], repo["name"]))
        all_open_today.extend(fetch_open_today(repo["owner"], repo["name"]))

    message = build_message(all_closed, all_open_today)
    post_to_slack(message)
    print(f"投稿完了: 完了 {len(all_closed)} 件 / 未完了 {len(all_open_today)} 件")


if __name__ == "__main__":
    main()
