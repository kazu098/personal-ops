# Operating Rules

## タスクライフサイクル

```
収集 → 整理 → 実行 → 完了
```

1. **収集**: 思いついたらすぐ GitHub Issue を作る。タイトルだけでよい
2. **整理**: 毎朝 `today` ラベルを今日やるものに付ける（recurring は自動付与）
3. **実行**: Issue をみながら作業する
4. **完了**: Issue を Close する → 夜の報告に自動反映される

## ラベル運用ルール

### area ラベル（1つ必須）

| ラベル | 用途 |
|---|---|
| `area:mia` | Mia プロジェクト関連 |
| `area:ai-cooking` | AI Cooking アプリ関連 |
| `area:blog` | ブログ・note・LinkedIn |
| `area:study` | 英語・韓国語・資格 |
| `area:research` | 調査・情報収集 |
| `area:admin` | 管理・雑務・その他 |

### type ラベル（1つ必須）

| ラベル | 用途 |
|---|---|
| `type:dev` | コーディング・開発 |
| `type:writing` | 執筆・記事作成 |
| `type:research` | 調査・リサーチ |
| `type:ops` | 運用・手続き・雑務 |
| `type:learning` | 学習・インプット |

### priority ラベル（1つ必須）

| ラベル | 用途 |
|---|---|
| `priority:p0` | 今日中に必ずやる。ブロッカー |
| `priority:p1` | 今日やりたい |
| `priority:p2` | できればやる |

### フラグラベル（任意）

| ラベル | 用途 |
|---|---|
| `today` | 今日のタスクとして Slack に出す |
| `waiting` | 誰かの返答待ちでブロック中 |

## 禁止事項

- `today` ラベルを付けすぎない。1日 5〜8 件が上限の目安
- recurring.yml に毎日タスクを増やしすぎない。習慣化できているもののみ
- Issue を溜め込まない。週1回 `GitHubチケット整理` で棚卸しする

## 週次レビュー（毎週金曜）

1. open Issue をすべて確認する
2. 不要なものは Close する
3. 来週やるものに適切なラベルを付ける
4. recurring.yml を見直す

## リポジトリ追加手順

1. `config/repos.yml` に追加する
2. そのリポジトリで必要なラベルを作成する（GitHub CLI 推奨）
3. 動作確認: `workflow_dispatch` で `daily-slack` を手動実行する
