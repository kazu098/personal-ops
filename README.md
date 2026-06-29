# personal-ops

GitHub Issues を正本にした個人タスク管理基盤。
毎朝 Slack に今日のタスクを投稿する。

## 仕組み

```
6:30 JST  recurring-tasks    → tasks/recurring.yml から Issue を自動作成
7:00 JST  daily-slack        → Notion の Today / In Progress タスクを Slack に投稿
           〜 作業 〜
21:00 JST evening-report     → 完了 / 未完了を Slack に報告
```

## セットアップ

### 1. リポジトリを作る

```bash
gh repo create kazu098/personal-ops --public
git clone https://github.com/kazu098/personal-ops
cd personal-ops
```

### 2. ラベルを作成する

```bash
# area ラベル
gh label create "area:mia"        --color "0075ca"
gh label create "area:ai-cooking" --color "e4e669"
gh label create "area:blog"       --color "d93f0b"
gh label create "area:study"      --color "0e8a16"
gh label create "area:research"   --color "1d76db"
gh label create "area:admin"      --color "bfd4f2"

# type ラベル
gh label create "type:dev"        --color "c5def5"
gh label create "type:writing"    --color "fef2c0"
gh label create "type:research"   --color "c2e0c6"
gh label create "type:ops"        --color "f9d0c4"
gh label create "type:learning"   --color "bfd4f2"

# priority ラベル
gh label create "priority:p0"     --color "b60205"
gh label create "priority:p1"     --color "e99695"
gh label create "priority:p2"     --color "f9d0c4"

# フラグ
gh label create "today"           --color "0052cc"
gh label create "waiting"         --color "ededed"
```

### 3. Slack アプリを設定する

1. [Slack API](https://api.slack.com/apps) でアプリを作成する
2. Bot Token Scopes に `chat:write` を追加する
3. アプリを投稿先チャンネルに追加する

### 4. GitHub Secrets を設定する

```bash
gh secret set SLACK_BOT_TOKEN --body "xoxb-..."
gh secret set SLACK_CHANNEL_ID --body "C..."
```

> `GITHUB_TOKEN` は Actions が自動で提供するため設定不要。
> Canvas モードで `DAILY_CANVAS_ID` を保存する場合は `GH_PAT` (Personal Access Token) が追加で必要。

### 5. 動作確認

GitHub の Actions タブから各ワークフローを **Run workflow** で手動実行して確認する。

## ローカル実行

```bash
pip install requests PyYAML

export SLACK_BOT_TOKEN="xoxb-..."
export SLACK_CHANNEL_ID="C..."
export GITHUB_TOKEN="ghp_..."
export SLACK_TASK_POST_MODE="message"

python scripts/post_daily_tasks_to_slack.py
```

Slack のフリープランでは Canvas が使えないため、Actions は `SLACK_TASK_POST_MODE=message` で通常のチャンネル投稿を使う。Pro 以上で Canvas を使う場合は `auto` または `canvas` に戻すと、保存済み `DAILY_CANVAS_ID` があれば既存 Canvas を上書きする。

## 対象リポジトリの追加

`config/repos.yml` に追加する:

```yaml
repos:
  - owner: kazu098
    name: personal-ops
    default_area: area:admin

  - owner: kazu098
    name: ai-cooking-app       # ← 追加
    default_area: area:ai-cooking
```

追加したリポジトリにも同じラベルセットを作成すること。

## ラベル運用ルール

詳細は [docs/operating-rules.md](docs/operating-rules.md) を参照。

| ルール | 内容 |
|---|---|
| `today` は毎朝付ける | recurring タスクは自動付与。単発は手動で付ける |
| 1日 5〜8 件まで | `today` の付けすぎ禁止 |
| 完了したら Close | ラベルを外すのではなく Issue を Close する |
| 週1回棚卸し | 毎週金曜に open Issue を確認して整理する |

## ファイル構成

```
.github/
  ISSUE_TEMPLATE/task.yml
  workflows/
    daily-slack.yml
    evening-report.yml
    recurring-tasks.yml
scripts/
  post_daily_tasks_to_slack.py
  post_evening_report_to_slack.py
  create_recurring_tasks.py
tasks/
  recurring.yml          # 繰り返しタスク定義
config/
  repos.yml              # 対象リポジトリ
docs/
  operating-rules.md     # 運用ルール詳細
CLAUDE.md                # Claude Code 向けガイド
```
