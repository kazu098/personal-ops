# CLAUDE.md

## このリポジトリの目的

GitHub Issues をタスクの正本として、Slack への自動投稿でデイリーの実行管理を回す。

- 朝: `today` ラベル付きの open Issue を Slack に投稿（7:00 JST）
- 夜: 当日 close された Issue と未完了 today Issue を Slack に報告（21:00 JST）
- 自動作成: `tasks/recurring.yml` から daily/weekly/monthly の Issue を生成（6:30 JST）

## ファイル構成

```
.github/
  ISSUE_TEMPLATE/task.yml     # Issue テンプレート
  workflows/
    daily-slack.yml            # 朝の投稿
    evening-report.yml         # 夜の報告
    recurring-tasks.yml        # 繰り返し Issue 作成
scripts/
  post_daily_tasks_to_slack.py
  post_evening_report_to_slack.py
  create_recurring_tasks.py
tasks/
  recurring.yml               # 繰り返しタスク定義
config/
  repos.yml                   # 対象リポジトリ一覧
docs/
  operating-rules.md          # 運用ルール
```

## 実装方針

- Python スクリプトは標準ライブラリ + `requests` + `PyYAML` のみ使う
- 外部サービスとの接続情報は環境変数から読む。ハードコード禁止
- GitHub API は REST v3 を使う。GraphQL は使わない
- スクリプトは `python scripts/xxx.py` で単体実行できるようにする
- エラー時は例外をそのまま raise して CI を失敗させる（握りつぶさない）

## ラベル設計

```
area:mia / area:ai-cooking / area:blog / area:study / area:research / area:admin
type:dev / type:writing / type:research / type:ops / type:learning
priority:p0 / priority:p1 / priority:p2
today / waiting
```

## 変更時の注意点

### `config/repos.yml` を変更するとき
- 追加したリポジトリに必要なラベルが作成されているか確認する
- `GITHUB_TOKEN` でそのリポジトリへのアクセス権があるか確認する
- 複数リポジトリを横断するようになったら Personal Access Token (GH_PAT) が必要になる

### `tasks/recurring.yml` を変更するとき
- タスクを増やしすぎない。1日のキャパを超える設定にしない
- `today` ラベルを付けるのは daily タスクのみ。weekly/monthly には付けない

### スクリプトを変更するとき
- `workflow_dispatch` で手動実行して動作を確認してから本番運用する
- Slack Webhook URL は `SLACK_WEBHOOK_URL` 環境変数から読む
- GitHub Token は `GITHUB_TOKEN` 環境変数から読む

## 破壊的変更を避けるルール

1. ラベル名を変更しない（変更する場合は既存 Issue のラベルも更新する）
2. `config/repos.yml` のスキーマを変えない
3. `tasks/recurring.yml` のスキーマを変えない
4. Slack メッセージのフォーマットを大きく変えない（目視で読めることが最優先）

## 今後追加する機能（まだ実装しない）

- SlackからのIssue作成（Slack Bot）
- Slackから `done` と送ると Issue を Close
- iPhoneショートカットからIssue作成
- 複数リポジトリ横断（GH_PAT 対応）
- 週次レビュー自動サマリー
- Notion同期
