#!/usr/bin/env python3
"""毎朝 Notion の Today タスクを Slack に投稿する。繰り返しタスクの昇格・リセットも行う。"""

import calendar
import os
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

import requests

NOTION_API_KEY = os.environ["NOTION_API_KEY"]
NOTION_DATABASE_ID = os.environ["NOTION_DATABASE_ID"]
SLACK_WEBHOOK_URL = os.environ["SLACK_WEBHOOK_URL"]

NOTION_VERSION = "2022-06-28"

PRIORITY_ORDER = {"High 🔥": 0, "Medium": 1, "Low": 2}

PROJECT_ORDER = ["mia", "mia-kit", "Business", "ブログ", "その他"]

PROJECT_DISPLAY = {
    "mia": "Mia",
    "mia-kit": "Mia Kit",
    "Business": "Business",
    "ブログ": "ブログ",
    "その他": "その他",
}


def notion_headers() -> dict:
    return {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def query_notion(filter_body: dict) -> list[dict]:
    url = (
        f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query"
    )
    results = []
    payload: dict = {"filter": filter_body, "page_size": 100}
    while True:
        resp = requests.post(
            url, headers=notion_headers(), json=payload, timeout=30
        )
        resp.raise_for_status()
        data = resp.json()
        results.extend(data["results"])
        if not data.get("has_more"):
            break
        payload["start_cursor"] = data["next_cursor"]
    return results


def update_page(page_id: str, properties: dict) -> None:
    url = f"https://api.notion.com/v1/pages/{page_id}"
    resp = requests.patch(
        url,
        headers=notion_headers(),
        json={"properties": properties},
        timeout=30,
    )
    resp.raise_for_status()


def get_prop(page: dict, name: str):
    prop = page.get("properties", {}).get(name, {})
    ptype = prop.get("type")
    if ptype == "select":
        sel = prop.get("select")
        return sel["name"] if sel else None
    if ptype == "title":
        return "".join(t["plain_text"] for t in prop.get("title", []))
    if ptype == "date":
        d = prop.get("date")
        return d["start"] if d else None
    return None


def next_occurrence(recurrence: str, due_str: str) -> str:
    due = date.fromisoformat(due_str[:10])
    if recurrence == "Daily":
        return (due + timedelta(days=1)).isoformat()
    if recurrence == "Weekly":
        return (due + timedelta(weeks=1)).isoformat()
    if recurrence == "Monthly":
        month = due.month % 12 + 1
        year = due.year + (1 if due.month == 12 else 0)
        day = min(due.day, calendar.monthrange(year, month)[1])
        return date(year, month, day).isoformat()
    raise ValueError(f"Unknown recurrence: {recurrence}")


def reset_done_recurring(today: date) -> None:
    """Done になった繰り返しタスクを次回日程にリセットする。"""
    done = query_notion({
        "and": [
            {"property": "Recurrence", "select": {"is_not_empty": True}},
            {"property": "Status", "select": {"equals": "Done"}},
        ]
    })
    for task in done:
        recurrence = get_prop(task, "Recurrence")
        due_str = get_prop(task, "Due Date")
        if not due_str:
            continue
        due = date.fromisoformat(due_str[:10])
        # 既に次回日程が今日以降なら触らない（二重リセット防止）
        if due >= today:
            continue
        new_due = next_occurrence(recurrence, due_str)
        update_page(task["id"], {
            "Status": {"select": {"name": "To Do"}},
            "Due Date": {"date": {"start": new_due}},
        })
    if done:
        print(f"繰り返しリセット: {len(done)} 件")


def promote_recurring_to_today(today: date) -> None:
    """今日が実行日の繰り返しタスクを Today に昇格する。"""
    candidates = query_notion({
        "and": [
            {"property": "Recurrence", "select": {"is_not_empty": True}},
            {"property": "Status", "select": {"equals": "To Do"}},
        ]
    })
    promoted = 0
    for task in candidates:
        recurrence = get_prop(task, "Recurrence")
        due_str = get_prop(task, "Due Date")
        if not due_str:
            continue
        due = date.fromisoformat(due_str[:10])
        should_promote = (
            recurrence == "Daily"
            or (recurrence == "Weekly" and due.weekday() == today.weekday())
            or (recurrence == "Monthly" and due.day == today.day)
        )
        if should_promote:
            update_page(task["id"], {
                "Status": {"select": {"name": "Today"}},
            })
            promoted += 1
    if promoted:
        print(f"繰り返し昇格: {promoted} 件")


def fetch_today_tasks() -> list[dict]:
    return query_notion(
        {"property": "Status", "select": {"equals": "Today"}}
    )


def task_priority(page: dict) -> int:
    return PRIORITY_ORDER.get(get_prop(page, "Priority"), 99)


def task_project(page: dict) -> str:
    return get_prop(page, "Project") or "その他"


def build_slack_message(tasks: list[dict], date_str: str) -> str:
    grouped: dict[str, list] = defaultdict(list)
    for task in tasks:
        grouped[task_project(task)].append(task)

    lines = [f"*今日のタスク（{date_str}）*\n"]

    for key in PROJECT_ORDER:
        items = grouped.get(key, [])
        if not items:
            continue
        lines.append(f"*{PROJECT_DISPLAY.get(key, key)}*")
        for task in sorted(items, key=task_priority):
            lines.append(f"・{get_prop(task, 'Name') or '(無題)'}")
        lines.append("")

    for key, items in grouped.items():
        if key in PROJECT_ORDER:
            continue
        lines.append(f"*{key}*")
        for task in sorted(items, key=task_priority):
            lines.append(f"・{get_prop(task, 'Name') or '(無題)'}")
        lines.append("")

    return "\n".join(lines).strip()


def post_to_slack(text: str) -> None:
    resp = requests.post(
        SLACK_WEBHOOK_URL, json={"text": text}, timeout=30
    )
    resp.raise_for_status()


def main() -> None:
    jst = timezone(timedelta(hours=9))
    today = datetime.now(jst).date()
    date_str = datetime.now(jst).strftime("%-m/%-d")

    reset_done_recurring(today)
    promote_recurring_to_today(today)

    tasks = fetch_today_tasks()
    if not tasks:
        print("Today タスクがありません。投稿をスキップします。")
        return

    post_to_slack(build_slack_message(tasks, date_str))
    print(f"投稿完了: {len(tasks)} 件")


if __name__ == "__main__":
    main()
