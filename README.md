# personal-ops

GitHub Issues を正本にした個人タスク管理基盤。
毎朝 Slack に今日のタスクを投稿し、毎晩完了・未完了を報告する。

## 仕組み

```
6:30 JST  recurring-tasks    → tasks/recurring.yml から Issue を自動作成
7:00 JST  daily-slack        → today ラベル付き open Issue を Slack に投稿
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

### 3. Slack Incoming Webhook を設定する

1. [Slack API](https://api.slack.com/apps) でアプリを作成する
2. **Incoming Webhooks** を有効にする
3. 投稿先チャンネルを選んで Webhook URL を取得する

### 4. GitHub Secrets を設定する

```bash
gh secret set SLACK_WEBHOOK_URL --body "https://hooks.slack.com/services/..."
```

> `GITHUB_TOKEN` は Actions が自動で提供するため設定不要。
> 複数リポジトリを横断する場合は `GH_PAT` (Personal Access Token) が追加で必要。

### 5. 動作確認

GitHub の Actions タブから各ワークフローを **Run workflow** で手動実行して確認する。

## ローカル実行

```bash
pip install requests PyYAML

export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..."
export GITHUB_TOKEN="ghp_..."

python scripts/post_daily_tasks_to_slack.py
python scripts/post_evening_report_to_slack.py
python scripts/create_recurring_tasks.py
```

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
