#!/usr/bin/env python3
"""毎朝 Notion の Today / In Progress タスクを Slack Canvas にまとめ、リンクを TODO チャンネルに投稿する。繰り返しタスクの昇格・リセットも行う。"""

import calendar
import os
import requests
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

NOTION_API_KEY = os.environ["NOTION_API_KEY"]
NOTION_DATABASE_ID = os.environ["NOTION_DATABASE_ID"]
SLACK_BOT_TOKEN = os.environ["SLACK_BOT_TOKEN"]
SLACK_CHANNEL_ID = os.environ["SLACK_CHANNEL_ID"]
GITHUB_REPOSITORY = os.environ["GITHUB_REPOSITORY"]
GH_TOKEN = os.environ["GH_TOKEN"]

NOTION_VERSION = "2022-06-28"
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


def slack_headers() -> dict:
    return {
        "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
        "Content-Type": "application/json",
    }


def query_notion(filter_body: dict) -> list[dict]:
    url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query"
    results = []
    payload: dict = {"filter": filter_body, "page_size": 100}
    while True:
        resp = requests.post(url, headers=notion_headers(), json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        results.extend(data["results"])
        if not data.get("has_more"):
            break
        payload["start_cursor"] = data["next_cursor"]
    return results


def update_page(page_id: str, properties: dict) -> None:
    url = f"https://api.notion.com/v1/pages/{page_id}"
    resp = requests.patch(url, headers=notion_headers(), json={"properties": properties}, timeout=30)
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
    done = query_notion({
        "and": [
            {"property": "Recurrence", "select": {"is_not_empty": True}},
            {"property": "Status", "select": {"equals": "Done"}},
        ]
    })
    for task in done:
        recurrence = get_prop(task, "Recurrence")
        due_str = get_prop(task, "Due Date")
        if recurrence == "Daily":
            update_page(task["id"], {"Status": {"select": {"name": "To Do"}}})
        else:
            if not due_str:
                continue
            due = date.fromisoformat(due_str[:10])
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
        due = date.fromisoformat(due_str[:10]) if due_str else None
        should_promote = (
            recurrence == "Daily"
            or (recurrence == "Weekly" and due and due.weekday() == today.weekday())
            or (recurrence == "Monthly" and due and due.day == today.day)
        )
        if should_promote:
            update_page(task["id"], {"Status": {"select": {"name": "Today"}}})
            promoted += 1
    if promoted:
        print(f"繰り返し昇格: {promoted} 件")


def fetch_today_tasks() -> list[dict]:
    return query_notion({
        "or": [
            {"property": "Status", "select": {"equals": "Today"}},
            {"property": "Status", "select": {"equals": "In Progress"}},
        ]
    })


def task_project(page: dict) -> str:
    return get_prop(page, "Project") or "その他"


def build_canvas_markdown(tasks: list[dict], date_str: str) -> str:
    grouped: dict[str, list] = defaultdict(list)
    for task in tasks:
        grouped[task_project(task)].append(task)

    lines = [f"# 今日のタスク（{date_str}）", ""]

    for key in PROJECT_ORDER:
        items = grouped.get(key, [])
        if not items:
            continue
        lines.append(f"## {PROJECT_DISPLAY.get(key, key)}")
        for task in items:
            name = get_prop(task, "Name") or "(無題)"
            lines.append(f"- [ ] {name}")
        lines.append("")

    for key, items in grouped.items():
        if key in PROJECT_ORDER:
            continue
        lines.append(f"## {key}")
        for task in items:
            name = get_prop(task, "Name") or "(無題)"
            lines.append(f"- [ ] {name}")
        lines.append("")

    return "\n".join(lines).strip()


def create_canvas(title: str, markdown: str) -> str:
    """スタンドアロン Canvas を新規作成して canvas_id を返す。"""
    resp = requests.post(
        "https://slack.com/api/canvases.create",
        headers=slack_headers(),
        json={
            "title": title,
            "document_content": {"type": "markdown", "markdown": markdown},
        },
        timeout=30,
    )
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"Canvas creation failed: {data.get('error', data)}")
    canvas_id = data["canvas_id"]
    print(f"Canvas 作成: {canvas_id}")
    return canvas_id


def get_saved_canvas_id() -> str | None:
    """GitHub リポジトリ変数から保存済み Canvas ID を取得する。"""
    owner, repo = GITHUB_REPOSITORY.split("/")
    headers = {
        "Authorization": f"Bearer {GH_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    resp = requests.get(
        f"https://api.github.com/repos/{owner}/{repo}/actions/variables/DAILY_CANVAS_ID",
        headers=headers,
        timeout=30,
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json().get("value") or None


def get_canvas_sections(canvas_id: str) -> list[dict]:
    resp = requests.post(
        "https://slack.com/api/canvases.sections.lookup",
        headers=slack_headers(),
        json={
            "canvas_id": canvas_id,
            "criteria": {
                "section_types": [
                    "h1", "h2", "h3",
                    "bullet_list", "ordered_list", "task_list",
                    "paragraph", "quote", "code_block", "divider",
                ],
            },
        },
        timeout=30,
    )
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"canvases.sections.lookup failed: {data.get('error', data)}")
    return data.get("sections", [])


def update_canvas(canvas_id: str, markdown: str) -> None:
    """既存 Canvas の内容を全て置き換える。"""
    sections = get_canvas_sections(canvas_id)
    if sections:
        delete_changes = [{"operation": "delete", "section_id": s["id"]} for s in sections]
        resp = requests.post(
            "https://slack.com/api/canvases.edit",
            headers=slack_headers(),
            json={"canvas_id": canvas_id, "changes": delete_changes},
            timeout=30,
        )
        data = resp.json()
        if not data.get("ok"):
            raise RuntimeError(f"canvases.edit (delete) failed: {data.get('error', data)}")

    resp = requests.post(
        "https://slack.com/api/canvases.edit",
        headers=slack_headers(),
        json={
            "canvas_id": canvas_id,
            "changes": [{"operation": "insert_at_start", "document_content": {"type": "markdown", "markdown": markdown}}],
        },
        timeout=30,
    )
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"canvases.edit (insert) failed: {data.get('error', data)}")
    print(f"Canvas 更新: {canvas_id}")


def share_canvas(canvas_id: str) -> None:
    """TODO チャンネルのメンバーが閲覧・チェックできるよう書き込み権限を付与する。"""
    resp = requests.post(
        "https://slack.com/api/canvases.access.set",
        headers=slack_headers(),
        json={
            "canvas_id": canvas_id,
            "access_level": "write",
            "channel_ids": [SLACK_CHANNEL_ID],
        },
        timeout=30,
    )
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"canvases.access.set failed: {data.get('error', data)}")


def canvas_url(canvas_id: str) -> str:
    """auth.test からワークスペース URL を取得し Canvas の共有リンクを組み立てる。"""
    resp = requests.post("https://slack.com/api/auth.test", headers=slack_headers(), timeout=30)
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"auth.test failed: {data.get('error', data)}")
    return f"{data['url']}docs/{data['team_id']}/{canvas_id}"


def post_canvas_link(url: str, date_str: str, count: int) -> None:
    """TODO チャンネルに Canvas のリンクを投稿する。"""
    text = f"📋 今日のタスク（{date_str}）を Canvas にまとめました（{count}件）\n{url}"
    resp = requests.post(
        "https://slack.com/api/chat.postMessage",
        headers=slack_headers(),
        json={"channel": SLACK_CHANNEL_ID, "text": text, "unfurl_links": True},
        timeout=30,
    )
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"chat.postMessage failed: {data.get('error', data)}")
    print(f"リンク投稿: {url}")


def save_canvas_id(canvas_id: str) -> None:
    """Canvas ID を GitHub リポジトリ変数 DAILY_CANVAS_ID に保存する。"""
    owner, repo = GITHUB_REPOSITORY.split("/")
    headers = {
        "Authorization": f"Bearer {GH_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    base_url = f"https://api.github.com/repos/{owner}/{repo}/actions/variables"
    payload = {"name": "DAILY_CANVAS_ID", "value": canvas_id}

    resp = requests.patch(f"{base_url}/DAILY_CANVAS_ID", headers=headers, json=payload, timeout=30)
    if resp.status_code == 404:
        resp = requests.post(base_url, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    print(f"Canvas ID を保存しました: {canvas_id}")


def main() -> None:
    jst = timezone(timedelta(hours=9))
    today = datetime.now(jst).date()
    date_str = datetime.now(jst).strftime("%-m/%-d")

    reset_done_recurring(today)
    promote_recurring_to_today(today)

    tasks = fetch_today_tasks()
    if not tasks:
        print("対象タスク（Today / In Progress）がありません。Canvas 投稿をスキップします。")
        return

    markdown = build_canvas_markdown(tasks, date_str)

    existing_canvas_id = get_saved_canvas_id()
    if existing_canvas_id:
        try:
            update_canvas(existing_canvas_id, markdown)
            canvas_id = existing_canvas_id
        except Exception as e:
            print(f"既存 Canvas の更新失敗（{e}）。新規作成します。")
            canvas_id = create_canvas("今日のタスク", markdown)
            share_canvas(canvas_id)
            save_canvas_id(canvas_id)
    else:
        canvas_id = create_canvas("今日のタスク", markdown)
        share_canvas(canvas_id)
        save_canvas_id(canvas_id)

    post_canvas_link(canvas_url(canvas_id), date_str, len(tasks))
    print(f"投稿完了: {len(tasks)} 件")


if __name__ == "__main__":
    main()
