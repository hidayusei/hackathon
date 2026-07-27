# DeskMate 実装計画書（版 1.0 → 版 2.0 移行）

版: 2.0 / 最終更新: 2026-07-27 / 実装担当: Codex

**版 1.0 の実装は既に存在し、233 個のテストが通っている。**
本書はそれを版 2.0（Raspberry Pi 内完結・3 状態構成）へ作り替える手順を定義する。

- 状態・閾値・文字列の具体値: [status-definition.md](status-definition.md)（**正典**）
- **版 1.0 → 2.0 の対応表**: [status-definition.md](status-definition.md) §11
- 構造・シグネチャ・設定: [architecture.md](architecture.md)
- 目的と完成条件: [requirements.md](requirements.md)
- プライバシー要件: [privacy-design.md](privacy-design.md)
- シナリオ・デモ: [demo-scenario.md](demo-scenario.md)
- 実装ルール: [../AGENTS.md](../AGENTS.md)

Codex 用のプロンプトは `scripts/prompts/migrate-01.md` 〜 `migrate-06.md` にある。

---

## 1. 移行の全体像

| Step | 内容 | 依存 | 目安 | プロンプト |
|:----:|------|------|:----:|-----------|
| M01 | core を 3 状態へ縮小 | – | 1.0 h | `migrate-01.md` |
| M02 | config を版 2.0 スキーマへ | M01 | 1.5 h | `migrate-02.md` |
| M03 | 推定パイプライン 3 状態化 + 休憩促し | M02 | 3.0 h | `migrate-03.md` |
| M04 | Pi ライブ入力 + `source: auto` | M01 | 2.0 h | `migrate-04.md` |
| M05 | GIF キャラクター + UI 2 画面化 | M03 | 3.0 h | `migrate-05.md` |
| M06 | ダミーシナリオ・デモ・全体確認 | M05 | 2.0 h | `migrate-06.md` |

合計目安 **12.5 時間**。M01 → M02 → M03 の順は変更しないこと。
M04 は M01 の後ならいつでも実施できる。

**各ステップの後に `pytest` を実行し、通ってから次へ進む。**
移行の途中では既存テストが壊れる。壊れたテストは「削除」ではなく
「版 2.0 の仕様に合わせて書き直す」こと。

---

## 2. 環境

版 1.0 から変更なし。Windows 側:

```bash
.venv\Scripts\python -m pip install -e ".[dev]"
```

テスト実行（Windows では offscreen が必要）:

```bash
set QT_QPA_PLATFORM=offscreen && .venv\Scripts\python -m pytest -q
```

Raspberry Pi 側の導入は [architecture.md](architecture.md) §26 を参照。
`python3 -m venv --system-site-packages .venv` が必須（`metavision_core` を見せるため）。

**Pillow は GIF 生成時のみ必要。実行時依存には入れない。**

---

## 3. 各ステップの詳細

### M01: core を 3 状態へ縮小

**変更**: `core/enums.py`, `core/types.py`

| 対象 | 内容 |
|------|------|
| `DeskStatus` | `AWAY` / `FOCUSED` / `IDLE` の 3 値に |
| `AnimationId` | `RUNNING` / `SITTING` / `SLEEPING` / `BREAK` の 4 値に |
| `SystemStatus` | `SHARING_OFF` を削除 |
| `Approachability` | **削除** |
| `SourceKind` | `AUTO` / `METAVISION` を追加、`WEBSOCKET` / `TCP` / `UDP` / `HTTP` を削除 |
| `StatusSnapshot` | `approachability` / `approachability_label` を削除、`focus_streak_seconds` / `break_due` を追加 |
| `to_public_dict()` | [status-definition.md](status-definition.md) §9 の 8 キーに |
| `SmoothedFeatures` | `change_score` を削除 |

**完了条件**: `python -c "from deskmate.core import enums, types"` が通る。
他モジュールの import エラーは M02 以降で解消するので、この時点では残ってよい。

**テスト**: `tests/test_core.py` を 3 状態向けに更新。

---

### M02: config を版 2.0 スキーマへ

**変更**: `config/schema.py`, `config/default.yaml`

| 対象 | 内容 |
|------|------|
| `EstimationConfig` | `away_seconds` を追加。`low_activity_eps` / `active_eps` / `no_motion_seconds` / `organizing_*` / `break_max_eps` / `break_decay_ratio` / `transition_*` / `noise_ratio_threshold` を削除 |
| `BreakConfig` | **新規**。`enabled` / `after_seconds` / `reset_seconds` / `snooze_seconds` / `demo_scale` |
| `SmoothingConfig` | `display_confidence_floor` を削除。`MinDwellConfig` を `default` / `away` の 2 つに |
| `ShareConfig` | **削除**。`UiConfig.share` も削除 |
| `CharacterConfig` | `renderer` 既定を `gif`、`scale: int`（既定 4）を追加。`loop_period_seconds` / `transition_ms` / `fps` を削除 |
| `AppSectionConfig` | `show_share_window` → `fullscreen` |
| `InputConfig` | `source` 既定を `auto`、`MetavisionInputConfig` を追加 |

**テスト `tests/test_config.py`**:

| # | 項目 | 期待 |
|---|------|------|
| 1 | `load_config()` が既定値で成功する | `AppConfig` |
| 2 | `estimation` の全閾値が [status-definition.md](status-definition.md) §6.2 と一致 | 期待値を直書きして比較 |
| 3 | `break` の全値が §3.2 と一致 | 同上 |
| 4 | 既定値がすべて `false`: `privacy.save_raw_events` / `save_features` / `logging.log_features` / `debug.enabled` | PV-9 |
| 5 | `input.source` の既定が `auto` | |
| 6 | `character.renderer` の既定が `gif`、`scale` が整数 | |
| 7 | 未知のキーを含む YAML | `ConfigError` |
| 8 | 削除したキー（`share` など）を書くと拒否される | `ConfigError` |

---

### M03: 推定パイプライン 3 状態化 + 休憩促し

**変更**: `rule_estimator.py`, `smoother.py`, `history.py`, `duration.py`, `runner.py`
**新規**: `break_tracker.py`
**削除**: `approachability.py`, `tests/test_approachability.py`

| 対象 | 内容 |
|------|------|
| `rule_estimator.py` | ルールを 3 本に（away → focused → idle）。`_rule_organizing` / `_rule_short_break` / `_rule_working` / `_rule_transition` / `_transition_started_at` / `_apply_noise_penalty` を削除 |
| `smoother.py` | `TRANSITION_TABLE` / `is_transition_allowed` / `force_transition_exit` を削除。`force_no_motion` → `force_away`。`_PRIORITY` を 3 状態に |
| `history.py` | `change_score` の算出を削除 |
| `duration.py` | `had_status_within()` を削除 |
| `break_tracker.py` | **新規**。[status-definition.md](status-definition.md) §3.3 のアルゴリズム |
| `runner.py` | `ApproachabilityResolver` → `BreakTracker`。`snooze_break()` / `acknowledge_break()` スロットを追加 |

**テスト `tests/test_break_tracker.py`（新規）**:

| # | 項目 | 期待 |
|---|------|------|
| 1 | `focused` を `after_seconds` 分投入 | `break_due` が `True` |
| 2 | `after_seconds` 未満 | `break_due` が `False` |
| 3 | `focused` 継続中に `idle` を 1 窓挟む | 連続集中は途切れない（`non_focus_seconds` のみ増える） |
| 4 | `idle` を `reset_seconds` 分投入 | `focus_streak_seconds` が 0、`break_due` が `False` |
| 5 | `snooze()` 後 | `break_due` が `False` になり、`snooze_seconds` 後に再び `True` |
| 6 | `acknowledge()` 後 | `focus_streak_seconds` が 0 |
| 7 | `system_status != RUNNING` | `break_due` を立てない |
| 8 | `demo_scale = 0.02` | `after_seconds` が 1/50 になる |
| 9 | `break.enabled = false` | 常に `break_due` が `False` |
| 10 | `reset()` | すべて初期化される |

**テスト `tests/test_rule_estimator.py`（書き直し）**:

| # | 入力 | 期待 |
|---|------|------|
| 1 | `idle_seconds = 35`（>= 30） | `away` |
| 2 | `rate_short=1400`, `share[keyboard]=0.9`, `area_short=0.06`, `rate_cv_10s=0.2`, `active_seconds=10` | `focused` |
| 3 | 上記だが `active_seconds=2`（< 5） | `idle` |
| 4 | 上記だが `share[keyboard]=0.3`（< 0.6） | `idle` |
| 5 | 上記だが `area_short=0.4`（> 0.20） | `idle` |
| 6 | 上記だが `rate_cv_10s=0.9`（> 0.60） | `idle` |
| 7 | `rate_short=50`, `idle_seconds=10` | `idle`（まだ `away` ではない） |
| 8 | 評価順序: `idle_seconds=35` かつ集中の条件も満たす | `away`（順位 1 が勝つ） |
| 9 | どの条件にも当てはまらない入力 | 必ず `idle`（例外を出さない） |
| 10 | 全状態で `confidence` が 0.0–1.0 | 範囲検証 |

**テスト `tests/test_smoother.py`（書き直し）**: 3 状態向けに。
最小継続時間・多数決・`force_away` の即時遷移を検証する。遷移表のテストは削除。

---

### M04: Pi ライブ入力 + `source: auto`

**新規**: `input/metavision_source.py`, `tests/test_source_resolution.py`
**変更**: `input/factory.py`

**ここが版 2.0 の要。** 詳細は [architecture.md](architecture.md) §7.1・§7.4。

| 対象 | 内容 |
|------|------|
| `metavision_source.py` | `MetavisionEventSource`。`metavision_core` は `open()` 内で遅延 import。失敗時は Pi の準備手順を含めた `SourceOpenError` |
| `factory.py` | `resolve_source_kind()` を追加。`AUTO` は `find_spec("metavision_core")` で判定し、無ければ `DUMMY` へ |

**テスト `tests/test_source_resolution.py`（新規）**:

| # | 項目 | 期待 |
|---|------|------|
| 1 | `find_spec` が値を返すとき `AUTO` | `METAVISION` に解決 |
| 2 | `find_spec` が `None` のとき `AUTO` | `DUMMY` に解決 + 理由の文字列 |
| 3 | `DUMMY` を明示指定 | そのまま `DUMMY`（勝手に差し替えない） |
| 4 | `METAVISION` を明示指定 | そのまま（環境に無くても差し替えない。`open()` で失敗させる） |
| 5 | metavision なしで `create_event_source` | 例外を出さずダミーを返す |
| 6 | **`import deskmate.input.metavision_source`** | `metavision_core` が無くても成功する（遅延 import の検証） |
| 7 | `MetavisionEventSource.open()` を metavision なしで呼ぶ | `SourceOpenError`。メッセージに `rp5_setup_v4l.sh` を含む |

---

### M05: GIF キャラクター + UI 2 画面化

**変更**: `character/mapping.py`, `character/renderer.py`, `ui/labels.py`, `ui/theme.py`,
`ui/widget_window.py`, `ui/tray.py`, `app.py`, `__main__.py`
**新規**: `ui/break_banner.py`
**削除**: `ui/share_window.py`

**GIF アセットは作成済み。** `assets/character/` の 4 ファイルを使う。新しく作らない。

| 対象 | 内容 |
|------|------|
| `mapping.py` | `resolve_animation(status, break_due, system_status)` を §4.2 の 5 段で実装 |
| `renderer.py` | `GifCharacterRenderer` を新規実装（QMovie）。**最近傍補間・整数倍拡大**。`ImageCharacterRenderer` を削除 |
| `labels.py` | §8 の文字列に総入れ替え。`QUIET_VARIANTS_JA` / `STATUS_LABELS_SHORT_JA` / `APPROACHABILITY_LABELS_JA` / `SHARE_*` / `AWAY_CAVEAT_JA` を削除 |
| `theme.py` | `STATUS_COLORS` を 3 状態 + 休憩色に |
| `break_banner.py` | **新規**。[architecture.md](architecture.md) §14.3 |
| `widget_window.py` | 見た目・サイズ・ドラッグ・最小化・**右クリックメニューは維持**。キャラクターを GIF に。**信頼度バーを削除**。共有ボタンを削除。バナーを重ねられるように |
| `share_window.py` | **削除** |
| `tray.py` | 共有画面のメニュー項目を削除 |
| `app.py` / `__main__.py` | 共有画面の生成を削除。`--fullscreen` / `--break-demo` を追加 |

**テスト**:

| ファイル | 内容 |
|---------|------|
| `tests/test_character_mapping.py` | §4.2 の 5 段の順序を全網羅（`break_due` が `away` より優先されること、`system_status != RUNNING` が最優先であること） |
| `tests/test_widget_ui.py` | 3 状態・GIF 構成に更新。**信頼度が表示されないこと**、**右クリックで詳細が開くこと**を検証 |
| `tests/test_ui_smoke.py` | 共有画面のテストを削除し 2 画面構成に |
| 新規 | GIF アセット 4 種が存在し、`loop=0` で 10 フレームであることを検証 |

---

### M06: ダミーシナリオ・デモ・全体確認

**変更**: `input/scenarios.py`, `tests/test_demo_sequence.py`

| 対象 | 内容 |
|------|------|
| `scenarios.py` | [demo-scenario.md](demo-scenario.md) §1 の 5 シナリオに。`DEMO_SEQUENCE` を §3 の 210 秒に |
| `test_demo_sequence.py` | 3 状態がすべて出ること、状態変化が 3 秒以上間隔を空けることを検証 |

**最終確認（Windows）**:

- [ ] `python -m deskmate --demo` で 3 状態とキャラクター 4 種が出る
- [ ] `--break-demo` で休憩促しが 30 秒で出る
- [ ] `source: auto` がダミーに解決される
- [ ] `pytest` が全通過

**報告すること**: Raspberry Pi で人間が確認すべき項目の一覧
（[demo-scenario.md](demo-scenario.md) §5 の「Raspberry Pi 実機」節）。

---

## 4. MVP 完了条件

[requirements.md](requirements.md) §9 の DoD-1〜DoD-15。

| DoD | 検証 | 対応 Step |
|-----|------|:--------:|
| DoD-1 起動・常駐 | 手動 | M05 |
| DoD-2 3 状態が出る | `test_demo_sequence.py` | M06 |
| DoD-3 キャラクター切替 | 手動 | M05 |
| DoD-4 日本語表示・継続時間 | 手動 + `test_widget_ui.py` | M05 |
| DoD-5 休憩促し | `test_break_tracker.py` + 手動 | M03, M05 |
| DoD-6 スヌーズ・リセット | `test_break_tracker.py` | M03 |
| DoD-7 右クリックで詳細 | `test_widget_ui.py` | M05 |
| DoD-8 最小継続時間 | `test_smoother.py` | M03 |
| DoD-9 切断時の挙動 | `test_source_failure.py` | 既存 |
| DoD-10 停止 / 再開 | `test_runner_control.py` | 既存 |
| DoD-11 `auto` がダミーへ解決 | `test_source_resolution.py` | M04 |
| DoD-12 遅延 import | `test_source_resolution.py` | M04 |
| DoD-13 保存が既定無効 | `test_privacy_guard.py` | 既存 |
| DoD-14 テスト全通過 | `pytest` | M06 |
| DoD-15 実機でライブ入力 | **人間が実施** | – |

---

## 5. 変更しないもの

移行で触らないこと。版 1.0 のまま動く。

- `pipeline/windower.py`（時間窓分割）
- `pipeline/features.py`（特徴量抽出。`voxel` の配線も含む）
- `pipeline/regions.py`（領域マップ）
- `pipeline/voxel.py`（Voxel Grid。既定 OFF のまま）
- `input/dummy_source.py` の生成ロジック（シナリオ定義だけ M06 で変える）
- `input/file_source.py`
- `privacy/guard.py`
- `logging_setup.py`
- `ui/detail_window.py` と `ui/panels/*`（状態名の表示だけ M05 で追随）
- `ui/status_stripe.py`（3 色になるだけ）
- `core/clock.py` / `core/errors.py`

---

## 6. 実装時の判断

設計書に無い判断が必要になったら [../AGENTS.md](../AGENTS.md) §5 に従い、
`docs/decisions.md` に記録して続行する。

**変更してはならない決定事項**:

- Raspberry Pi 内で完結する構成（外部送信を作らない）
- 3 状態（離席中 / 集中 / 非集中）と表示名
- `source: auto` による Pi / Windows 両対応
- `metavision_core` の遅延 import
- GIF は最近傍補間・整数倍拡大
- UI に注意書き・免責・内部指標を常時表示しない
- 保存の既定無効
