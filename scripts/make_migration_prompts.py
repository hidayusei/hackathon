"""Generate the v1 -> v2 migration prompts for Codex.

    python scripts/make_migration_prompts.py

Writes scripts/prompts/migrate-01.md .. migrate-06.md. The prompts intentionally do not
repeat any design values: they point at docs/ so the design documents stay the single
source of truth.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "scripts" / "prompts"

COMMON = """
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
"""

STEPS: list[tuple[str, str, str]] = [
    (
        "01",
        "core を 3 状態へ縮小する",
        """`docs/status-definition.md` §2・§11 に従って `src/deskmate/core/` を改修する。

対象:
- `core/enums.py`
  - `DeskStatus` を `AWAY` / `FOCUSED` / `IDLE` の 3 値にする
  - `AnimationId` を `RUNNING` / `SITTING` / `SLEEPING` / `BREAK` の 4 値にする
  - `SystemStatus` から `SHARING_OFF` を削除する
  - **`Approachability` を丸ごと削除する**
  - `SourceKind` に `AUTO` と `METAVISION` を追加し、`WEBSOCKET`/`TCP`/`UDP`/`HTTP` を削除する
- `core/types.py`
  - `StatusSnapshot` から `approachability` / `approachability_label` を削除し、
    `focus_streak_seconds: float` と `break_due: bool` を追加する
  - `to_public_dict()` を `docs/status-definition.md` §9 の 8 キーに合わせる
  - `SmoothedFeatures` から `change_score` を削除する

このステップではまだ他のモジュールは直さなくてよい。import エラーが残るのは想定内。
次のステップで順に直す。ただし `core` 単体の import は通ること。""",
    ),
    (
        "02",
        "config を版 2.0 のスキーマへ更新する",
        """`docs/architecture.md` §15 の YAML と `docs/status-definition.md` §6.2・§3.2 に従う。

対象:
- `src/deskmate/config/schema.py`
  - `EstimationConfig`: `away_seconds` を追加。`low_activity_eps` / `active_eps` /
    `no_motion_seconds` / `organizing_*` / `break_max_eps` / `break_decay_ratio` /
    `transition_*` / `noise_ratio_threshold` を削除
  - **`BreakConfig` を新規追加**（`enabled` / `after_seconds` / `reset_seconds` /
    `snooze_seconds` / `demo_scale`）
  - `SmoothingConfig`: `display_confidence_floor` を削除。`MinDwellConfig` を
    `default` と `away` の 2 つにする
  - **`ShareConfig` を削除**。`UiConfig` から `share` を削除
  - `CharacterConfig`: `renderer` の既定を `gif` にし、`scale: int`（既定 4）を追加。
    `loop_period_seconds` / `transition_ms` / `fps` を削除
  - `AppSectionConfig`: `show_share_window` を `fullscreen` に置き換える
  - `InputConfig`: `source` の既定を `auto` にし、`MetavisionInputConfig` を追加
- `config/default.yaml` を上記に合わせて全面更新する

**`docs/status-definition.md` の閾値表と `config/default.yaml` の値が
一字一句一致していること。** テストで期待値を直書きして検証する。""",
    ),
    (
        "03",
        "推定パイプラインを 3 状態化し、休憩促しを追加する",
        """`docs/status-definition.md` §6・§7・§3 に従う。

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
- `tests/test_rule_estimator.py` と `tests/test_smoother.py` を 3 状態向けに書き直す""",
    ),
    (
        "04",
        "Raspberry Pi のライブ入力と source: auto を実装する",
        """`docs/architecture.md` §7.1・§7.4 に従う。**ここが版 2.0 の要。**

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
  `metavision_core` を要求しないこと**（遅延 import の検証）""",
    ),
    (
        "05",
        "キャラクターを GIF 化し、UI を 2 画面構成にする",
        """`docs/status-definition.md` §4 と `docs/architecture.md` §13・§14 に従う。

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
- **右クリックで詳細画面が開くこと**を検証するテストを追加する""",
    ),
    (
        "06",
        "ダミーシナリオ・デモ・全体確認",
        """対象:
- `input/scenarios.py`
  - シナリオを 3 状態を再現できる構成に整理する
    （キーボード付近の安定した動き → 集中 / 散発的で広い動き → 非集中 /
      ほぼ無活動 → 離席中 / 入力途絶）
  - `DEMO_SEQUENCE` を 3 状態と休憩促しが一巡するように組み直す。
    休憩促しは `break.demo_scale` を下げて実演できるようにする
- 旧 7 状態前提のテスト（`test_demo_sequence.py` など）を 3 状態向けに更新する
- `python -m deskmate --demo` を Windows で起動し、
  離席中 / 集中 / 非集中 の 3 状態と休憩促しがすべて出ることを目視確認する
- 全テストを実行して通す

最後に次を報告すること:
1. Windows でダミー入力を使い、3 状態すべてとキャラクター 4 種が表示されたか
2. 休憩促しが `demo_scale` を下げた状態で出たか
3. `input.source: auto` が Windows でダミーに解決されたか（ログまたは詳細画面で確認）
4. Raspberry Pi で確認すべき残項目の一覧（あなたは Pi を持っていないので、
   実機確認は人間が行う。何を確認すべきか手順として書き出すこと）""",
    ),
]


def build() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    root = str(ROOT)
    for number, title, body in STEPS:
        text = (
            f"あなたは DeskMate プロジェクトの実装担当です。\n"
            f"作業ディレクトリ: {root}\n\n"
            f"# 移行タスク M{number}: {title}\n\n"
            "DeskMate は設計を版 1.0 から版 2.0 へ変更しました。\n"
            "**Raspberry Pi 5 内で完結する構成**になり、状態が 7 種から 3 種へ減り、\n"
            "共有画面が廃止され、キャラクターがドット絵 GIF になりました。\n"
            "まず `docs/status-definition.md` の冒頭と §11（移行対応表）、\n"
            "`docs/architecture.md` の冒頭の「版 2.0 の変更点」を読んでください。\n\n"
            "## やること\n\n"
            f"{body}\n"
            f"{COMMON}"
        )
        path = OUT / f"migrate-{number}.md"
        path.write_text(text, encoding="utf-8")
        print(f"migrate-{number}.md : {title}")


if __name__ == "__main__":
    build()
