あなたは DeskMate プロジェクトの実装担当です。
作業ディレクトリ: C:\Users\yusei\dev\DeskMate

# 移行タスク M04: Raspberry Pi のライブ入力と source: auto を実装する

DeskMate は設計を版 1.0 から版 2.0 へ変更しました。
**Raspberry Pi 5 内で完結する構成**になり、状態が 7 種から 3 種へ減り、
共有画面が廃止され、キャラクターがドット絵 GIF になりました。
まず `docs/status-definition.md` の冒頭と §11（移行対応表）、
`docs/architecture.md` の冒頭の「版 2.0 の変更点」を読んでください。

## やること

`docs/architecture.md` §7.1・§7.4 に従う。**ここが版 2.0 の要。**

対象:
- **`src/deskmate/input/metavision_source.py` を新規作成**
  - `MetavisionEventSource(EventSource)`
  - `metavision_core` は**モジュール先頭で import しない**。`open()` 内で遅延 import し、
    失敗したら `SourceOpenError` にラップする。エラーメッセージには Pi 側の準備手順
    (`sudo dtoverlay genx320,cam0` / `./rp5_setup_v4l.sh` / `PSEE_VAR_V4L2_BSIZE=1`) を含める
  - `EventsIterator(input_path="", delta_t=...)` からライブ受信し、
    `EventBatch.from_structured()` へ渡す（EventCD は x,y,p,t 順、p は int16）
  - 解像度は `get_size()` から取得し、設定と違えば WARNING を出してイテレータ側を採用する
- `input/factory.py`
  - `resolve_source_kind(configured) -> tuple[SourceKind, str]` を追加
  - `AUTO` は `importlib.util.find_spec("metavision_core")` で判定し、
    無ければ `DUMMY` へフォールバックする。**実 import はしない**
  - 解決理由の文字列を `PipelineStats.source_name` に載せる
- `core/enums.py` の `SourceKind` から削除した種別の残骸を掃除する

テスト `tests/test_source_resolution.py` を新規作成:
- `find_spec` を monkeypatch して「ある/ない」両方で `resolve_source_kind` を検証
- `AUTO` 以外を指定したときは勝手に差し替えないこと
- Windows 環境（metavision なし）で `create_event_source` がダミーを返し、例外を出さないこと
- **`metavision_source.py` をモジュールとして import しても
  `metavision_core` を要求しないこと**（遅延 import の検証）

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
