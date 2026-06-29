// Slack Bot: /task でモーダルを開いて GitHub Issue を作成、/done <番号> でクローズ

const REPO_OWNER = "kazu098";
const REPO_NAME = "personal-ops";
const GITHUB_API = "https://api.github.com";
const SLACK_API = "https://slack.com/api";

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

function truncateOptionText(text, limit = 75) {
  return text.length <= limit ? text : `${text.slice(0, limit - 1)}…`;
}

function buildDailyTaskBlocks(title, tasks, edited = false) {
  const blocks = [
    {
      type: "header",
      text: { type: "plain_text", text: title, emoji: true },
    },
    {
      type: "context",
      elements: [{ type: "mrkdwn", text: `${tasks.length}件 / Slack通常投稿${edited ? "（編集済み）" : ""}` }],
    },
    {
      type: "actions",
      block_id: "task_controls",
      elements: [
        {
          type: "button",
          action_id: "daily_tasks_edit",
          text: { type: "plain_text", text: "編集", emoji: true },
          value: "edit",
        },
      ],
    },
  ];

  for (let offset = 0; offset < tasks.length; offset += 10) {
    const chunk = tasks.slice(offset, offset + 10);
    blocks.push({
      type: "actions",
      block_id: `tasks_${offset / 10}`,
      elements: [
        {
          type: "checkboxes",
          action_id: "task_checked",
          options: chunk.map((task, index) => ({
            text: { type: "plain_text", text: truncateOptionText(task), emoji: true },
            value: `task_${offset + index}`,
          })),
        },
      ],
    });
  }

  return blocks;
}

function extractDailyTaskTitle(message) {
  const header = message?.blocks?.find(block => block.type === "header");
  return header?.text?.text || "今日のタスク";
}

function extractDailyTasks(message) {
  const tasks = [];
  for (const block of message?.blocks || []) {
    for (const element of block.elements || []) {
      if (element.type !== "checkboxes" || element.action_id !== "task_checked") continue;
      for (const option of element.options || []) {
        const text = option.text?.text?.trim();
        if (text) tasks.push(text);
      }
    }
  }
  return tasks;
}

function buildDailyTasksEditModal(channel, ts, title, tasks) {
  return {
    type: "modal",
    callback_id: "edit_daily_tasks",
    private_metadata: JSON.stringify({ channel, ts, title }),
    title: { type: "plain_text", text: "To Do編集" },
    submit: { type: "plain_text", text: "保存" },
    close: { type: "plain_text", text: "キャンセル" },
    blocks: [
      {
        type: "input",
        block_id: "tasks",
        label: { type: "plain_text", text: "1行につき1件" },
        element: {
          type: "plain_text_input",
          action_id: "value",
          multiline: true,
          initial_value: tasks.join("\n").slice(0, 3000),
        },
      },
    ],
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
        if (action?.action_id === "daily_tasks_edit") {
          const title = extractDailyTaskTitle(payload.message);
          const tasks = extractDailyTasks(payload.message);
          await slackPost("views.open", {
            trigger_id: payload.trigger_id,
            view: buildDailyTasksEditModal(payload.channel.id, payload.message.ts, title, tasks),
          }, env.SLACK_BOT_TOKEN);
          return new Response("", { status: 200 });
        }

        if (action?.action_id === "task_checked") {
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

      if (payload.type === "view_submission" && payload.view?.callback_id === "edit_daily_tasks") {
        const meta = JSON.parse(payload.view.private_metadata || "{}");
        const rawTasks = payload.view.state.values.tasks.value.value || "";
        const tasks = rawTasks
          .split("\n")
          .map(line => line.replace(/^\s*[-*]?\s*(\[ \]|\[x\])?\s*/i, "").trim())
          .filter(Boolean);
        const title = meta.title || "今日のタスク";

        await slackPost("chat.update", {
          channel: meta.channel,
          ts: meta.ts,
          text: `${title}: ${tasks.length}件`,
          blocks: buildDailyTaskBlocks(title, tasks, true),
        }, env.SLACK_BOT_TOKEN);

        return new Response("", { status: 200 });
      }
    }

    return new Response("OK", { status: 200 });
  }
};
