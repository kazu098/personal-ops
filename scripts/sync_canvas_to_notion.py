#!/usr/bin/env python3
"""夜 21:00: Slack Canvas のチェック済み項目を Notion の Done に反映する。"""

import json
import os
import requests

SLACK_BOT_TOKEN = os.environ["SLACK_BOT_TOKEN"]
NOTION_API_KEY = os.environ["NOTION_API_KEY"]
NOTION_DATABASE_ID = os.environ["NOTION_DATABASE_ID"]
DAILY_CANVAS_ID = os.environ.get("DAILY_CANVAS_ID", "")
SLACK_TASK_POST_MODE = os.environ.get("SLACK_TASK_POST_MODE", "auto").lower()

NOTION_VERSION = "2022-06-28"


def slack_headers() -> dict:
    return {
        "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
        "Content-Type": "application/json",
    }


def notion_headers() -> dict:
    return {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def get_canvas_sections(canvas_id: str) -> list[dict]:
    resp = requests.post(
        "https://slack.com/api/canvases.sections.lookup",
        headers=slack_headers(),
        json={"canvas_id": canvas_id, "criteria": {"contains_text": ""}},
        timeout=30,
    )
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"canvases.sections.lookup failed: {data.get('error')}")
    return data.get("sections", [])


def _extract_text(elements: list) -> str:
    text = ""
    for elem in elements:
        if elem.get("type") == "text":
            text += elem.get("text", "")
        elif "elements" in elem:
            text += _extract_text(elem["elements"])
    return text


def extract_checked_names(sections: list[dict]) -> list[str]:
    """チェックされたタスク名を返す。"""
    checked = []
    for section in sections:
        section_checked = section.get("checked", False)
        for block in section.get("content", []):
            for elem in block.get("elements", []):
                if elem.get("type") == "rich_text_list":
                    for item in elem.get("elements", []):
                        if section_checked or item.get("checked", False):
                            text = _extract_text(item.get("elements", []))
                            if text.strip():
                                checked.append(text.strip())
    return checked


def fetch_today_tasks() -> list[dict]:
    url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query"
    resp = requests.post(
        url,
        headers=notion_headers(),
        json={
            "filter": {
                "or": [
                    {"property": "Status", "select": {"equals": "Today"}},
                    {"property": "Status", "select": {"equals": "In Progress"}},
                ]
            },
            "page_size": 100,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json().get("results", [])


def get_task_name(page: dict) -> str:
    prop = page.get("properties", {}).get("Name", {})
    return "".join(t["plain_text"] for t in prop.get("title", []))


def mark_done(page_id: str) -> None:
    resp = requests.patch(
        f"https://api.notion.com/v1/pages/{page_id}",
        headers=notion_headers(),
        json={"properties": {"Status": {"select": {"name": "Done"}}}},
        timeout=30,
    )
    resp.raise_for_status()


def main() -> None:
    if SLACK_TASK_POST_MODE == "message":
        print("SLACK_TASK_POST_MODE=message のため Canvas 同期をスキップします。")
        return

    if not DAILY_CANVAS_ID:
        print("DAILY_CANVAS_ID が未設定のためスキップします。")
        return

    print(f"Canvas ID: {DAILY_CANVAS_ID}")
    sections = get_canvas_sections(DAILY_CANVAS_ID)
    print(f"セクション数: {len(sections)}")
    # 初回実行時の API レスポンス確認用
    print(json.dumps(sections, ensure_ascii=False, indent=2))

    checked_names = extract_checked_names(sections)
    print(f"チェック済み: {checked_names}")

    if not checked_names:
        print("チェックされた項目がありません。")
        return

    today_tasks = fetch_today_tasks()
    updated = 0
    for task in today_tasks:
        name = get_task_name(task)
        if name in checked_names:
            mark_done(task["id"])
            print(f"Done: {name}")
            updated += 1

    print(f"Notion 更新: {updated} 件")


if __name__ == "__main__":
    main()
