あなたは DeskMate プロジェクトの実装担当です。
作業ディレクトリ: C:\Users\yusei\dev\DeskMate

# 移行タスク M03: 推定パイプラインを 3 状態化し、休憩促しを追加する

DeskMate は設計を版 1.0 から版 2.0 へ変更しました。
**Raspberry Pi 5 内で完結する構成**になり、状態が 7 種から 3 種へ減り、
共有画面が廃止され、キャラクターがドット絵 GIF になりました。
まず `docs/status-definition.md` の冒頭と §11（移行対応表）、
`docs/architecture.md` の冒頭の「版 2.0 の変更点」を読んでください。

## やること

`docs/status-definition.md` §6・§7・§3 に従う。

対象:
- `pipeline/rule_estimator.py`
  - ルールを 3 本にする（away → focused → idle のフォールバック）
  - `_rule_organizing` / `_rule_short_break` / `_rule_working` / `_rule_transition` を削除
  - `_transition_started_at` の抑止ロジックを削除
  - `_apply_noise_penalty` を削除（3 値では自然に idle に落ちるため不要）
  - 信頼度の式を §6.3 の 3 本に置き換える
- `pipeline/smoother.py`
  - **`TRANSITION_TABLE` と `is_transition_allowed` を削除**（3 状態では全遷移を許可）
  - `force_transition_exit` のロジックを削除
  - `force_no_motion` を `force_away` に改名する
  - `_PRIORITY` を §6.1 の 3 状態の順序にする
- `pipeline/history.py`: `change_score` の算出を削除
- **`pipeline/break_tracker.py` を新規作成**（`docs/architecture.md` §11 のシグネチャ）
- **`pipeline/approachability.py` を削除**
- `pipeline/duration.py`: `had_status_within()` を削除
- `pipeline/runner.py`
  - `ApproachabilityResolver` を `BreakTracker` に置き換える
  - `StatusSnapshot` の新フィールドを埋める
  - `snooze_break()` / `acknowledge_break()` スロットを追加する

テスト:
- `tests/test_approachability.py` を削除
- **`tests/test_break_tracker.py` を新規作成**。§3.3 の手順 1〜6 を個別に検証する
  （25 分で立つ / 3 分の非集中でリセット / スヌーズで 5 分後に再提示 /
  停止中は立たない / demo_scale が効く）
- `tests/test_rule_estimator.py` と `tests/test_smoother.py` を 3 状態向けに書き直す

## 守ること（全ステップ共通）

1. **設計書が唯一の正典。** 数値・クラス名・関数名・引数・戻り値・例外・設定キー・
   表示文字列はすべて docs/ にある。推測で決めない。
   - `docs/status-definition.md` … 状態・閾値・アニメーション・表示文字列（**最優先**）
   - `docs/status-definition.md` §11 … **版1.0→2.0 の移行対応表**
   - `docs/architecture.md` … 構造・シグネチャ・設定・入力インターフェース
   - `AGENTS.md` … 実装ルール
2. **削除するものは本当に削除する。** 使われなくなったクラスやファイルを
   「念のため」残さない。移行対応表で「廃止」「削除」とあるものは消す。
3. **閾値をハードコードしない。** すべて AppConfig 経由。
   `docs/status-definition.md` の値と `config/default.yaml` の値を一致させる。
4. **日本語リテラルは `src/deskmate/ui/labels.py` にのみ置く。**
4b. **ユーザに見せる画面はスマートに保つ。** 注意書き・免責・内部指標を常時表示しない。
   面白さはキャラクターの動きで出し、文章量では出さない
   （`docs/status-definition.md` §1-6）。
5. **依存ライブラリを増やさない。** Pillow は GIF 生成時のみで、実行時には使わない。
6. **numpy のベクトル演算で書く。** イベント配列を Python の for で回さない。
7. **git commit / git push をしない。** リポジトリ外を変更しない。
8. **docs/ を書き換えない。** 判断が必要なら `docs/decisions.md` に追記して続行する。
9. 変更後は必ず `pytest` を実行し、通ることを確認する（Windows では
   `set QT_QPA_PLATFORM=offscreen`）。**落ちているのに成功と報告しない。**

## プラットフォームの前提

- 本番実行環境は **Raspberry Pi 5**（Metavision SDK 入り）。
- 開発と UI 確認は **Windows**。ここには Metavision SDK が無い。
- **同じコード・同じ設定ファイルで両方が動くこと。** 差分は `input.source: auto` の
  解決結果だけに閉じ込める（`docs/architecture.md` §7.4）。
- Windows で `import metavision_core` を実行してはならない。存在確認は
  `importlib.util.find_spec` で行い、実 import は `open()` の中で遅延実行する。

## 完了したら報告すること

1. 作成・変更・**削除**したファイルの一覧
2. `pytest` の結果（件数と成否。失敗があれば出力をそのまま貼る）
3. 移行対応表のうち、このステップで対応した項目
4. 設計書との差異があれば内容と理由
5. `docs/decisions.md` に追記した判断があれば、その ID
