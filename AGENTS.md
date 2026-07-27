# AGENTS.md — 実装エージェント（Codex）向けルール

このリポジトリで実装作業を行うエージェントは、本書のルールに従うこと。
本書は実装者向けの規約であり、システムの内容は `docs/` の設計書が定義する。

---

## 0. 役割分担

| 担当 | 役割 | 書いてよいもの |
|------|------|--------------|
| Claude Code | 設計・レビュー担当 | `docs/` 配下、`README.md`、`AGENTS.md`、`CLAUDE.md`、`assets/`（キャラクター素材） |
| **Codex（あなた）** | **実装担当** | **`src/`、`tests/`、`config/`、`pyproject.toml`、`docs/decisions.md`（追記のみ）** |

境界が曖昧なものの扱い:

| ファイル | 担当 | 理由 |
|---------|------|------|
| `README.md` | Claude Code | 設計文書であり、プライバシーの記述を含む。Codex は**古くなった箇所を報告する**（修正はしない） |
| `assets/character/*.gif` | Claude Code | 素材は作成済み。Codex は**参照するだけ**で、再生成も編集もしない |
| `tools/make_character_gifs.py` | Claude Code | 素材生成ツール |
| `scripts/` | Claude Code | Codex へのプロンプト生成 |
| `config/default.yaml` | Codex | ただし値は `docs/status-definition.md` に従う |

Codex は設計を作り直さない。設計書に無い判断が必要になったら §5 の手順を踏む。

---

## 1. 最初に読む文書

実装を始める前に、次の順で読むこと。

1. `docs/requirements.md` — 何を作るか、MVP の完成条件
2. `docs/architecture.md` — 技術構成、ディレクトリ、クラス / 関数シグネチャ、データ型、設定
3. `docs/status-definition.md` — 状態・特徴量・閾値・表示文字列の**正典**
4. `docs/implementation-plan.md` — **実装順序とテスト項目。これに沿って進める**
5. `docs/privacy-design.md` — 守るべきプライバシー要件
6. `docs/demo-scenario.md` — ダミーシナリオとデモ構成

文書間で矛盾を見つけた場合の優先順位:

```
status-definition.md（数値・文字列）
  > architecture.md（構造・シグネチャ）
  > implementation-plan.md（順序・テスト）
  > requirements.md > demo-scenario.md > privacy-design.md
```

ただし**プライバシー要件は上書きされない**。他の文書と矛盾する場合は、
より制限的な方（データを出さない方）を選び、§5 で報告すること。

---

## 2. 実装の進め方

### 2.1 順序

`docs/implementation-plan.md` §1 の **M01 → M06** の順に移行する。**順序を飛ばさない。**
各ステップの完了条件を満たしてから次へ進む。
Codex 用のプロンプトは `scripts/prompts/migrate-01.md` 〜 `migrate-06.md` にある。

### 2.2 1 Step の手順

1. その Step で作るファイルを作成する。
2. `docs/architecture.md` §5（各ファイルの責務）と §6–§19（シグネチャ）どおりに実装する。
3. 対応するテストを `tests/` に書く（テスト項目は `implementation-plan.md` の表にすべて列挙してある）。
4. `pytest` を実行し、通ることを確認する。
5. 完了条件をチェックする。

### 2.3 やらないこと

- 設計書に無いファイルを勝手に作らない。
- 設計書に無いライブラリを追加しない（`docs/architecture.md` §1.4 の表が全部）。
- 「もっと良い設計」への作り替えをしない。改善案は §5 で提案する。
- 未実装機能を「とりあえず動く別実装」で埋めない。`NotImplementedError` を明示的に投げる。
- リファクタリングのための大規模な移動・改名をしない。

---

## 3. コーディング規約

### 3.1 基本

| 項目 | 規約 |
|------|------|
| Python | 3.11–3.13 で動くこと。3.11 に無い構文を使わない |
| 型注釈 | すべての public な関数・メソッド・dataclass フィールドに付ける。`Any` は避ける |
| 文字列 | ソースは UTF-8。日本語のリテラルは `src/deskmate/ui/labels.py` にのみ置く |
| 命名 | クラス `PascalCase`、関数・変数 `snake_case`、定数 `UPPER_SNAKE`、非公開 `_leading_underscore` |
| import | 標準ライブラリ → サードパーティ → 自パッケージの順。相対 import は同一サブパッケージ内のみ |
| dataclass | `@dataclass(frozen=True, slots=True)` を既定とする（可変が必要な場合のみ frozen を外す） |
| 行長 | 100 文字を目安 |
| docstring | クラスと public メソッドに 1 行以上。引数・戻り値・送出例外を書く |

### 3.2 数値計算

- イベント配列の処理は **numpy のベクトル演算**で書く。Python の `for` ループでイベントを回さない。
- 除算の前に必ずゼロ判定を行う。`event_count == 0` の窓は常に到来しうる。
- `float` の比較に `==` を使わない。テストでは `pytest.approx` を使う。
- 座標は `uint16`、時刻は `int64`（マイクロ秒）、極性は `int8`。dtype を勝手に変えない。

### 3.3 定数・閾値

- **閾値・係数をコードにハードコードしない。** すべて `AppConfig` から読む。
- `docs/status-definition.md` の数値と `config/default.yaml` の値は一致していなければならない。
  片方だけ変えない。
- 状態名・ラベル・アニメーション ID は `core/enums.py` と `ui/labels.py` にのみ書く。

### 3.4 Qt

- UI スレッドをブロックしない。重い処理はパイプラインスレッドで行う。
- パイプライン → UI は Qt シグナル（`Qt.QueuedConnection`）のみ。共有変数を直接読み書きしない。
- シグナルで渡すオブジェクトは immutable にする。渡した後に書き換えない。
- `QTimer` の interval は設定から取る（`ui.detail.refresh_hz` など）。ハードコードしない。
- ウィジェットの `deleteLater()` を忘れない。詳細画面を閉じたら購読を解除する。

### 3.5 例外

- 例外は `core/errors.py` の階層のみを使う。裸の `Exception` を投げない。
- `except Exception: pass` を書かない。必ずログを残す。
- **`PrivacyViolationError` を握り潰さない。** 上位へ伝播させる。
- ループ内の例外は捕捉してログ + 状態遷移で処理し、アプリを終了させない。

---

## 4. プライバシー実装ルール（違反は設計違反として扱う）

`docs/privacy-design.md` が正典。実装時に必ず守ること。

1. **生イベント配列を貯め込まない。** 窓化したら参照を切る。
2. **`StatusSnapshot` に座標・特徴量・イベント数のフィールドを追加しない。**
3. **常駐ウィジェットから `FeatureFrame` / `DetailFrame` / `EventWindow` を import しない。**
   詳細画面が閉じている間は `DetailFrame` を生成しない（PV-6）。
4. **ログに座標を出力しない。** `DEBUG` レベルでも禁止。
5. **保存・送信は `PrivacyGuard` を通す。** 直接 `open(path, "w")` でイベントを書かない。
6. **ネットワーク送信のコードを書かない。** `requests` / `httpx` / `socket` の送信を実装しない。
7. **画面キャプチャ・アクティブウィンドウ取得を実装しない。**
   `mss` / `pyautogui` / `win32gui` / `cv2` を import しない。
8. **既定値を `false` から変えない。**
   `privacy.save_raw_events` / `privacy.save_features` / `logging.log_features` /
   `debug.enabled`。

---

## 5. 判断が必要なとき

設計書に書かれていない判断が必要になった場合:

1. まず設計書を再確認する（`status-definition.md` に数値がある可能性が高い）。
2. それでも決まらない場合、**最も単純で、最も制限的（データを出さない）な選択肢**を取る。
3. その判断を `docs/decisions.md`（無ければ新規作成）に次の形式で記録する。

```markdown
## D-001: <決めたこと>
- 日付: YYYY-MM-DD
- 背景: 設計書のどこが不足していたか
- 選択肢: A / B
- 決定: A
- 理由: 
- 影響範囲: <ファイル名>
- 要確認: 設計担当（Claude Code）に確認が必要か（はい / いいえ）
```

4. 実装を続ける。設計書自体は書き換えない（設計書の更新は設計担当の役割）。

**変更してはならない決定事項**（提案は歓迎するが、独断で変えない）:

- 技術構成: Python + PySide6 の単一プロセス構成
- **Raspberry Pi 内で完結する構成**（外部送信を作らない）
- **`DeskStatus` の 3 種**（`away`=離席中 / `focused`=集中 / `idle`=非集中）と表示文言
- **「不在です」「席にいません」と人の所在を断定しない方針**
  （表示名としての「離席中」は採用する。`docs/status-definition.md` §10）
- **`source: auto` による Pi / Windows 両対応と、`metavision_core` の遅延 import**
- **GIF は最近傍補間・整数倍拡大**
- **UI に注意書き・免責・内部指標を常時表示しない方針**
- 保存の既定無効
- `EventSource` インターフェースの契約
- ディレクトリ構成とファイル名

---

## 6. 禁止事項

- `git commit` / `git push` を実行しない（ユーザが行う）。
- リポジトリ外のファイルを変更しない。特に `C:\Users\yusei\dev\` 配下の他プロジェクト、
  `EVENT_CAMERA`、`OpenEB` は**読み取りのみ**。編集・移動・削除をしない。
- 外部サービスへ接続しない（パッケージインストールを除く）。
- `docs/` 配下の設計書を書き換えない（`docs/decisions.md` の追記のみ可）。
- **`README.md` を書き換えない。** README は設計担当（Claude Code）が管理する。
  ただし、あなたの変更で README の記述が古くなった場合（起動コマンド・依存関係・
  ディレクトリ構成・対応プラットフォームが変わったとき）は、
  **作業報告で「README のここが古くなった」と指摘すること。** 修正は設計担当が行う。
- 実装に不要なファイル（サンプル、スクラッチ、メモ、生成物）をリポジトリに残さない。
- `data/` `logs/` に成果物をコミットしない（`.gitignore` 済み）。
- テストを削除・スキップして「通った」ことにしない。

---

## 7. コミットメッセージ（ユーザがコミットする際の推奨形式）

```
<type>: <Step 番号> <内容>

例:
feat: M03 休憩促し BreakTracker を実装
test: M04 source: auto の解決テストを追加
fix: M05 GIF の拡大が最近傍になっていない問題を修正
```

`type` は `feat` / `fix` / `test` / `docs` / `chore` のいずれか。

---

## 8. 作業報告の形式

1 つのステップを終えたら、次を報告すること。

1. 実装したステップ番号（M01 など）と内容
2. 作成・変更したファイルの一覧
3. `pytest` の結果（件数と成否。失敗があれば内容をそのまま貼る）
4. 完了条件のチェック結果
5. 設計書との差異があれば、その内容と理由
6. `docs/decisions.md` に追記した判断があれば、その ID
7. **`README.md` の記述が古くなったなら、その箇所**（修正はしない。報告のみ）
8. 次に着手するステップ

テストが失敗している場合、成功したとは報告しないこと。
