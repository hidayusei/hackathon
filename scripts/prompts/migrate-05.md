あなたは DeskMate プロジェクトの実装担当です。
作業ディレクトリ: C:\Users\yusei\dev\DeskMate

# 移行タスク M05: キャラクターを GIF 化し、UI を 2 画面構成にする

DeskMate は設計を版 1.0 から版 2.0 へ変更しました。
**Raspberry Pi 5 内で完結する構成**になり、状態が 7 種から 3 種へ減り、
共有画面が廃止され、キャラクターがドット絵 GIF になりました。
まず `docs/status-definition.md` の冒頭と §11（移行対応表）、
`docs/architecture.md` の冒頭の「版 2.0 の変更点」を読んでください。

## やること

`docs/status-definition.md` §4 と `docs/architecture.md` §13・§14 に従う。

**GIF アセットは作成済みで `assets/character/` にある。新しく作らないこと。**
`running.gif` / `sitting.gif` / `sleeping.gif` / `break.gif`（各 30×30、10 フレーム、無限ループ）。

対象:
- `character/mapping.py`
  - `resolve_animation(status, break_due, system_status)` を §4.2 の 5 段の順序で実装する
  - `ANIMATION_RULES` / `SYSTEM_ANIMATION` の旧テーブルを削除する
- `character/renderer.py`
  - **`GifCharacterRenderer` を新規実装**。`QMovie` で GIF を再生する
  - **必ず最近傍補間で整数倍拡大する**（`Qt.TransformationMode.FastTransformation`）。
    滑らかな補間を使わないこと
  - `ShapeCharacterRenderer` は素材が無い場合の保険として残すが、既定は `gif`
  - `ImageCharacterRenderer` は削除する（`GifCharacterRenderer` が置き換える）
- `ui/labels.py`: §8 の文字列に総入れ替え。
  `QUIET_VARIANTS_JA` / `STATUS_LABELS_SHORT_JA` / `APPROACHABILITY_LABELS_JA` /
  `SHARE_*` / `AWAY_CAVEAT_JA` を削除。`resolve_label(status, system_status)` に簡略化
- `ui/theme.py`: `STATUS_COLORS` を §4.5 の 3 状態 + 休憩色にする
- **`ui/share_window.py` を削除**
- **`ui/break_banner.py` を新規作成**（`docs/architecture.md` §14.3）
- `ui/widget_window.py`
  - 見た目とサイズ、ドラッグ・最小化・**右クリックメニュー**はそのまま維持する
  - キャラクターを GIF 表示に差し替える
  - **日本語の状態ラベルを大きく表示する**（現状どおり）
  - **信頼度バーを削除する**（3 値では意味が薄い。§6.3）
  - **注意書き・免責・内部指標をウィジェットに出さない。**
    「離席中は推定です」のような注記は**表示しない**
    （`docs/status-definition.md` §1-6・§10.1、`docs/privacy-design.md` §3.3）。
    見せるのは「キャラクター・状態名・継続時間」だけ。スマートに保つこと
  - 共有ボタンを削除し、休憩促しバナーを重ねられるようにする
  - 状態履歴ストライプは 3 色になるので、そのまま活かす
- `ui/tray.py`: 共有画面のメニュー項目を削除する
- `app.py` / `__main__.py`: 共有画面の生成を削除。`--fullscreen` を追加する

テスト:
- `tests/test_ui_smoke.py` から共有画面のテストを削除し、2 画面構成に直す
- `tests/test_widget_ui.py` を 3 状態・GIF 構成に合わせて更新する
- **右クリックで詳細画面が開くこと**を検証するテストを追加する

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
