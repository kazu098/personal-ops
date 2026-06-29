// Slack Bot: /task でモーダルを開いて GitHub Issue を作成、/done <番号> でクローズ

const REPO_OWNER = "kazu098";
const REPO_NAME = "personal-ops";
const GITHUB_API = "https://api.github.com";
const SLACK_API = "https://slack.com/api";
const NOTION_API = "https://api.notion.com/v1";
const NOTION_VERSION = "2022-06-28";

// ── Slack 署名検証 ─────────────────────────────────────────
async function verifySlackSignature(request, rawBody, signingSecret) {
  const timestamp = request.headers.get("X-Slack-Request-Timestamp");
  const signature = request.headers.get("X-Slack-Signature");
  if (!timestamp || !signature) return false;
  if (Math.abs(Date.now() / 1000 - parseInt(timestamp)) > 300) return false;

  const enc = new TextEncoder();
  const key = await crypto.subtle.importKey(
    "raw", enc.encode(signingSecret),
    { name: "HMAC", hash: "SHA-256" }, false, ["sign"]
  );
  const sig = await crypto.subtle.sign("HMAC", key, enc.encode(`v0:${timestamp}:${rawBody}`));
  const hex = Array.from(new Uint8Array(sig)).map(b => b.toString(16).padStart(2, "0")).join("");
  return signature === `v0=${hex}`;
}

// ── Slack モーダル定義 ──────────────────────────────────────
function buildTaskModal() {
  return {
    type: "modal",
    callback_id: "create_task",
    title: { type: "plain_text", text: "タスク登録" },
    submit: { type: "plain_text", text: "登録" },
    close: { type: "plain_text", text: "キャンセル" },
    blocks: [
      {
        type: "input",
        block_id: "title",
        label: { type: "plain_text", text: "タイトル" },
        element: {
          type: "plain_text_input",
          action_id: "value",
          placeholder: { type: "plain_text", text: "例: 西表島フェリー予約" }
        }
      },
      {
        type: "input",
        block_id: "area",
        label: { type: "plain_text", text: "エリア" },
        element: {
          type: "static_select",
          action_id: "value",
          options: [
            { text: { type: "plain_text", text: "mia" },        value: "area:mia" },
            { text: { type: "plain_text", text: "ai-cooking" }, value: "area:ai-cooking" },
            { text: { type: "plain_text", text: "blog" },       value: "area:blog" },
            { text: { type: "plain_text", text: "study" },      value: "area:study" },
            { text: { type: "plain_text", text: "research" },   value: "area:research" },
            { text: { type: "plain_text", text: "admin" },      value: "area:admin" },
          ]
        }
      },
      {
        type: "input",
        block_id: "type",
        label: { type: "plain_text", text: "タイプ" },
        element: {
          type: "static_select",
          action_id: "value",
          options: [
            { text: { type: "plain_text", text: "dev" },      value: "type:dev" },
            { text: { type: "plain_text", text: "writing" },  value: "type:writing" },
            { text: { type: "plain_text", text: "research" }, value: "type:research" },
            { text: { type: "plain_text", text: "ops" },      value: "type:ops" },
            { text: { type: "plain_text", text: "learning" }, value: "type:learning" },
          ]
        }
      },
      {
        type: "input",
        block_id: "priority",
        label: { type: "plain_text", text: "優先度" },
        element: {
          type: "static_select",
          action_id: "value",
          initial_option: { text: { type: "plain_text", text: "p1（通常）" }, value: "priority:p1" },
          options: [
            { text: { type: "plain_text", text: "p0（最優先）" }, value: "priority:p0" },
            { text: { type: "plain_text", text: "p1（通常）" },   value: "priority:p1" },
            { text: { type: "plain_text", text: "p2（低）" },     value: "priority:p2" },
          ]
        }
      },
      {
        type: "input",
        block_id: "flags",
        label: { type: "plain_text", text: "フラグ" },
        optional: true,
        element: {
          type: "checkboxes",
          action_id: "value",
          options: [
            { text: { type: "plain_text", text: "today（今日やる）" },     value: "today" },
            { text: { type: "plain_text", text: "this-week（今週やる）" }, value: "this-week" },
          ]
        }
      },
      {
        type: "input",
        block_id: "body",
        label: { type: "plain_text", text: "メモ（任意）" },
        optional: true,
        element: {
          type: "plain_text_input",
          action_id: "value",
          multiline: true,
          placeholder: { type: "plain_text", text: "補足、期日、リンクなど" }
        }
      }
    ]
  };
}

// ── GitHub API ─────────────────────────────────────────────
function githubHeaders(pat) {
  return {
    "Authorization": `Bearer ${pat}`,
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "Content-Type": "application/json",
  };
}

async function createIssue(title, labels, body, pat) {
  const resp = await fetch(`${GITHUB_API}/repos/${REPO_OWNER}/${REPO_NAME}/issues`, {
    method: "POST",
    headers: githubHeaders(pat),
    body: JSON.stringify({ title, labels, body: body || "" }),
  });
  return resp.json();
}

async function closeIssue(number, pat) {
  const resp = await fetch(`${GITHUB_API}/repos/${REPO_OWNER}/${REPO_NAME}/issues/${number}`, {
    method: "PATCH",
    headers: githubHeaders(pat),
    body: JSON.stringify({ state: "closed", state_reason: "completed" }),
  });
  return resp.json();
}

// ── Notion API ─────────────────────────────────────────────
function notionHeaders(apiKey) {
  return {
    "Authorization": `Bearer ${apiKey}`,
    "Notion-Version": NOTION_VERSION,
    "Content-Type": "application/json",
  };
}

async function markNotionDone(pageId, apiKey) {
  const resp = await fetch(`${NOTION_API}/pages/${pageId}`, {
    method: "PATCH",
    headers: notionHeaders(apiKey),
    body: JSON.stringify({ properties: { Status: { select: { name: "Done" } } } }),
  });
  return resp.json();
}

// ── Slack API ──────────────────────────────────────────────
async function slackPost(endpoint, body, token) {
  return fetch(`${SLACK_API}/${endpoint}`, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
}

// ── メインハンドラ ─────────────────────────────────────────
export default {
  async fetch(request, env) {
    if (request.method !== "POST") return new Response("Method Not Allowed", { status: 405 });

    const rawBody = await request.text();
    if (!await verifySlackSignature(request, rawBody, env.SLACK_SIGNING_SECRET)) {
      return new Response("Unauthorized", { status: 401 });
    }

    const contentType = request.headers.get("Content-Type") || "";

    // スラッシュコマンド
    if (contentType.includes("application/x-www-form-urlencoded") && !rawBody.startsWith("payload=")) {
      const data = Object.fromEntries(new URLSearchParams(rawBody));

      // /task → モーダルを開く
      if (data.command === "/task") {
        await slackPost("views.open", {
          trigger_id: data.trigger_id,
          view: buildTaskModal(),
        }, env.SLACK_BOT_TOKEN);
        return new Response("", { status: 200 });
      }

      // /done <番号> → Issue をクローズ
      if (data.command === "/done") {
        const num = data.text?.trim();
        if (!num || isNaN(num)) {
          return new Response(
            JSON.stringify({ response_type: "ephemeral", text: "使い方: `/done <Issue番号>`　例: `/done 13`" }),
            { headers: { "Content-Type": "application/json" } }
          );
        }
        const issue = await closeIssue(num, env.GITHUB_PAT);
        const text = issue.html_url
          ? `✅ #${num}「${issue.title}」をクローズしました`
          : `❌ Issue #${num} が見つかりません`;
        return new Response(
          JSON.stringify({ response_type: "ephemeral", text }),
          { headers: { "Content-Type": "application/json" } }
        );
      }

      return new Response("Unknown command", { status: 400 });
    }

    // モーダル送信（インタラクション）
    if (rawBody.startsWith("payload=")) {
      const payload = JSON.parse(decodeURIComponent(rawBody.slice(8)));

      if (payload.type === "block_actions") {
        const action = payload.actions?.[0];
        if (action?.action_id === "task_checked") {
          if (!env.NOTION_API_KEY) {
            return new Response("NOTION_API_KEY is not configured", { status: 200 });
          }

          const selected = action.selected_options || [];
          await Promise.all(selected.map(option => markNotionDone(option.value, env.NOTION_API_KEY)));
          return new Response("", { status: 200 });
        }
      }

      if (payload.type === "view_submission" && payload.view?.callback_id === "create_task") {
        const v = payload.view.state.values;
        const title    = v.title.value.value;
        const area     = v.area.value.selected_option.value;
        const type     = v.type.value.selected_option.value;
        const priority = v.priority.value.selected_option.value;
        const flags    = (v.flags?.value?.selected_options || []).map(o => o.value);
        const body     = v.body?.value?.value || "";
        const labels   = [area, type, priority, ...flags];

        const issue = await createIssue(title, labels, body, env.GITHUB_PAT);

        if (issue.html_url) {
          await slackPost("chat.postMessage", {
            channel: payload.user.id,
            text: `✅ Issue を登録しました: <${issue.html_url}|#${issue.number} ${title}>`,
          }, env.SLACK_BOT_TOKEN);
        }

        return new Response("", { status: 200 });
      }
    }

    return new Response("OK", { status: 200 });
  }
};
