#!/usr/bin/env python3
"""tasks/recurring.yml を読み、daily/weekly/monthly の Issue を自動作成する。
同タイトルの open Issue が既に存在する場合はスキップする。"""

import os
import sys
from datetime import datetime, timezone, timedelta

import requests
import yaml

GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
JST = timezone(timedelta(hours=9))

WEEKDAYS = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}

REPO_OWNER = "kazu098"
REPO_NAME = "personal-ops"


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def existing_open_titles(owner: str, repo: str) -> set[str]:
    url = f"https://api.github.com/repos/{owner}/{repo}/issues"
    params = {"state": "open", "per_page": 100}
    resp = requests.get(url, headers=_headers(), params=params, timeout=30)
    resp.raise_for_status()
    return {issue["title"] for issue in resp.json()}


def create_issue(owner: str, repo: str, title: str, labels: list[str]) -> None:
    url = f"https://api.github.com/repos/{owner}/{repo}/issues"
    payload = {"title": title, "labels": labels}
    resp = requests.post(url, headers=_headers(), json=payload, timeout=30)
    resp.raise_for_status()
    print(f"  作成: {title}")


def should_run_weekly(day_str: str) -> bool:
    today = datetime.now(JST).weekday()
    return WEEKDAYS.get(day_str.lower(), -1) == today


def should_run_monthly(day_of_month: int) -> bool:
    return datetime.now(JST).day == day_of_month


def main() -> None:
    with open("tasks/recurring.yml") as f:
        config = yaml.safe_load(f)

    owner = REPO_OWNER
    repo = REPO_NAME
    existing = existing_open_titles(owner, repo)
    created = 0

    # daily
    for task in config.get("daily") or []:
        title = task["title"]
        if title in existing:
            print(f"  スキップ (既存): {title}")
            continue
        create_issue(owner, repo, title, task.get("labels", []))
        created += 1

    # weekly
    for task in config.get("weekly") or []:
        if not should_run_weekly(task.get("day", "")):
            continue
        title = task["title"]
        if title in existing:
            print(f"  スキップ (既存): {title}")
            continue
        create_issue(owner, repo, title, task.get("labels", []))
        created += 1

    # monthly
    for task in config.get("monthly") or []:
        if not should_run_monthly(int(task.get("day_of_month", 1))):
            continue
        title = task["title"]
        if title in existing:
            print(f"  スキップ (既存): {title}")
            continue
        create_issue(owner, repo, title, task.get("labels", []))
        created += 1

    print(f"完了: {created} 件作成")


if __name__ == "__main__":
    main()
