# DeskMate 実装計画書

版: 1.0 / 最終更新: 2026-07-26 / 実装担当: Codex

本書は実装の順序・各ステップの成果物・テスト項目・完了条件を定義する。
**上から順に実装すること。** 各ステップの完了条件を満たしてから次へ進む。

- 技術構成・シグネチャ: [architecture.md](architecture.md)
- 状態・閾値・文字列の具体値: [status-definition.md](status-definition.md)
- プライバシー要件: [privacy-design.md](privacy-design.md)
- シナリオ・デモ: [demo-scenario.md](demo-scenario.md)
- 実装ルール: [../AGENTS.md](../AGENTS.md)

---

## 1. 環境構築（Step 0）

```bash
cd C:/Users/yusei/dev/DeskMate
py -3.13 -m venv .venv
.venv/Scripts/python -m pip install --upgrade pip
.venv/Scripts/pip install -e ".[dev]"
```

### 作成するファイル

**`pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=69"]
build-backend = "setuptools.build_meta"

[project]
name = "deskmate"
version = "0.1.0"
requires-python = ">=3.11,<3.14"
dependencies = [
    "PySide6>=6.8,<7",
    "numpy>=1.26",
    "pyqtgraph>=0.13.7",
    "pydantic>=2.7,<3",
    "PyYAML>=6.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-qt>=4.4"]
hdf5 = ["h5py>=3.11"]
ml = ["scikit-learn>=1.5"]

[project.scripts]
deskmate = "deskmate.__main__:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q"
```

**`requirements.txt`**: `pyproject.toml` の `dependencies` + `dev` をピン留めなしで列挙。

**`.gitignore`**

```
.venv/
__pycache__/
*.py[cod]
*.egg-info/
.pytest_cache/
data/raw/
data/features/
data/recordings/
logs/
config/local.yaml
scripts/logs/
scripts/.codex-progress.json
```

**`assets/character/README.md`**: 素材の置き方（`<animation_id>.gif` または `.png`、
推奨サイズ 256×256、透過 PNG。素材が無い AnimationId は自動的に図形描画にフォールバックする旨）。

**`data/.gitkeep`**

### 完了条件

- [ ] `.venv/Scripts/python -c "import PySide6, numpy, pyqtgraph, pydantic, yaml; print('ok')"` が成功する
- [ ] `pytest` が「テスト 0 件」で正常終了する

---

## 2. 実装順序の全体像

| Step | 内容 | 依存 | 目安 | 検証手段 |
|:----:|------|------|:----:|---------|
| 0 | 環境構築・雛形 | – | 0.5 h | import 確認 |
| 1 | core（enums / types / errors / clock） | 0 | 1 h | 型チェック・import |
| 2 | config（schema / loader / default.yaml） | 1 | 1.5 h | `test_config.py` |
| 3 | input（base / dummy / scenarios / factory） | 1,2 | 3 h | `test_dummy_source.py` |
| 4 | pipeline 前半（windower / regions / features / history） | 1,2,3 | 4 h | `test_windower/regions/features/history.py` |
| 5 | pipeline 後半（estimator / rule / smoother / duration / approachability） | 4 | 3 h | `test_rule_estimator/smoother/duration/approachability.py` |
| 6 | runner（スレッド統合・CLI 動作確認） | 5 | 2 h | `test_runner.py`、コンソール実行 |
| 7 | character（mapping / renderer） | 1 | 1.5 h | `test_character_mapping.py` |
| 8 | ui 基盤（labels / theme / bridge / character_view） | 6,7 | 2 h | `test_labels.py` |
| 9 | **常駐ウィジェット** | 8 | 2.5 h | 目視・`test_ui_smoke.py` |
| 10 | **共有画面** | 8 | 1.5 h | 目視・`test_ui_smoke.py` |
| 11 | **詳細画面** | 8 | 4 h | 目視・チェックリスト |
| 12 | privacy / logging / トレイ / 異常系 | 9,10,11 | 2 h | `test_privacy_guard.py`、`test_source_failure.py` |
| 13 | file_source・デモ通し確認・調整 | 12 | 2 h | `test_file_source.py`、`test_demo_sequence.py` |
| 14 | 骨組み（hdf5_source / ml_estimator / voxel） | 13 | 1 h | import できること |

合計目安 **31.5 時間**。Step 9 → 10 → 11 の順は変更しないこと
（時間が足りない場合、詳細画面のパネル数を削ることで調整する。共有画面と常駐ウィジェットは必須）。

---

## 3. 各ステップの詳細

### Step 1: core

**作成**: `src/deskmate/__init__.py`, `core/__init__.py`, `core/enums.py`, `core/types.py`,
`core/errors.py`, `core/clock.py`

**内容**:

- `enums.py`: `DeskStatus` / `SystemStatus` / `RegionId` / `AnimationId` / `Approachability` /
  `SourceStatus` / `SourceKind`。すべて `str, Enum`。値は [status-definition.md](status-definition.md) のとおり。
- `types.py`: [architecture.md](architecture.md) §6 の全 dataclass。`EVENT_DTYPE` も定義。
  `EventBatch.from_records()` のバリデーション（キー欠落 → `DecodeError`、
  `t` が非単調 → `DecodeError`、座標が `sensor` 範囲外 → `DecodeError`）。
- `errors.py`: [architecture.md](architecture.md) §16.1 の例外階層。
- `clock.py`:

```python
class Clock(Protocol):
    def monotonic(self) -> float: ...
    def now(self) -> datetime: ...

class SystemClock:
    def monotonic(self) -> float: return time.monotonic()
    def now(self) -> datetime: return datetime.now().astimezone()

def us_to_seconds(us: int) -> float: ...
def seconds_to_us(s: float) -> int: ...
```

**完了条件**: `python -c "from deskmate.core import types, enums, errors, clock"` が通る。
`StatusSnapshot` のフィールドが座標・特徴量を含まない。

---

### Step 2: config

**作成**: `config/default.yaml`, `config/regions.sample.yaml`,
`src/deskmate/config/__init__.py`, `schema.py`, `loader.py`

**内容**: [architecture.md](architecture.md) §15 の YAML をそのまま `config/default.yaml` に置く。
`schema.py` は §15.1 の pydantic モデル。`extra="forbid"`。
`loader.py` は default → ユーザ設定 → CLI の深いマージ。

**テスト `tests/test_config.py`**:

| # | 項目 | 期待 |
|---|------|------|
| 1 | `load_config()` が既定値で成功する | `AppConfig` が返る |
| 2 | `window.stride_ms > window_ms` | `ConfigError` |
| 3 | `window.window_ms = 50` | `ConfigError`（範囲外） |
| 4 | 未知のキーを含む YAML | `ConfigError`（extra forbid） |
| 5 | `regions` に `other` を明示指定 | `ConfigError` |
| 6 | `regions` の矩形が `[0,1]` 外 / `x0>=x1` | `ConfigError` |
| 7 | `regions` の `id` 重複 | `ConfigError` |
| 8 | `deep_merge` がネストした辞書を正しくマージする | 部分上書きが効く |
| 9 | **既定値の検証**: `privacy.save_raw_events`, `privacy.save_features`, `logging.log_features`, `debug.enabled`, `privacy.allow_external_send` がすべて `False` | PV-10 |
| 10 | `estimation` の全閾値が [status-definition.md](status-definition.md) §5.2 の既定値と一致する | 定数の取り違え防止 |

**完了条件**: 上記 10 項目が通る。

---

### Step 3: input

**作成**: `input/__init__.py`, `base.py`, `scenarios.py`, `dummy_source.py`, `factory.py`

**内容**: [architecture.md](architecture.md) §7・§17、[demo-scenario.md](demo-scenario.md) §1・§3。

**テスト `tests/test_dummy_source.py`**:

| # | 項目 | 期待 |
|---|------|------|
| 1 | 同一 seed で 2 回生成し、同じイベント列になる | 再現性 |
| 2 | `keyboard_steady` を 5 秒分生成 | 平均 eps が `base_rate_eps` の ±20% 以内 |
| 3 | 同上 | イベントの 80% 以上が keyboard 領域の矩形内にある |
| 4 | `desk_wide_active` を 5 秒分生成 | x, y の標準偏差が `keyboard_steady` の 2 倍以上 |
| 5 | `activity_decay` を 20 秒分生成 | 後半 5 秒の eps が前半 5 秒の 30% 未満 |
| 6 | `mouse_intermittent` を 10 秒分生成 | eps がゼロに近い区間が周期的に現れる（`burst_duty` 相当） |
| 7 | `noise_burst` を 3 秒分生成 | 活性グリッドセル比率が 0.8 以上 |
| 8 | `dropout` シナリオ | `read()` が常に `None` を返す |
| 9 | 生成された `EventBatch` の `t` が昇順、`x < width`, `y < height`, `p in {0,1}` | 形式検証 |
| 10 | `set_scenario("unknown_id")` | `ValueError` |
| 11 | デモモードで 340 秒進めると 10 ステップすべてを通過する | `DEMO_SEQUENCE` の走査 |
| 12 | `EventBatch.from_records()` に不正データ（`t` 逆順・キー欠落・範囲外座標） | `DecodeError` |

**完了条件**: 上記が通る。`input.source: websocket` を設定した `InputConfig` を
`create_event_source()` に渡すと `ConfigError` が送出される。

---

### Step 4: pipeline 前半

**作成**: `pipeline/__init__.py`, `windower.py`, `regions.py`, `features.py`, `history.py`

**テスト `tests/test_windower.py`**:

| # | 項目 | 期待 |
|---|------|------|
| 1 | 1 秒分のイベントを 200 ms 窓で処理 | 5 窓が出る |
| 2 | バッチ境界をまたぐイベント | 正しい窓に振り分けられる。総イベント数が保存される |
| 3 | `stride_ms < window_ms` | 窓が重複し、窓数が増える |
| 4 | `flush_idle()` | 空窓（`event_count == 0`）が生成される |
| 5 | `t` が後退したバッチ | `PipelineError` |
| 6 | `max_events_per_window` 超過 | 出力配列長が上限、`truncated=True`、`window.x.size <= limit` |
| 7 | `window_ms=50` で初期化 | `ConfigError` |
| 8 | `reset()` 後 | `window_index` が 0 に戻る |

**テスト `tests/test_regions.py`**:

| # | 項目 | 期待 |
|---|------|------|
| 1 | 既定領域で keyboard 矩形の中心座標を `assign` | `KEYBOARD` のインデックス |
| 2 | どの矩形にも入らない座標 | `OTHER` |
| 3 | 重なる矩形 | 設定の並び順で先のものが勝つ |
| 4 | 矩形が範囲外 / `x0>=x1` / `id` 重複 | `ConfigError` |
| 5 | `lookup_table` の shape | `(height, width)`、dtype `int8` |

**テスト `tests/test_features.py`**:

| # | 項目 | 期待 |
|---|------|------|
| 1 | 空窓 | `event_count=0`, `positive_ratio=0.5`, `bbox_area_ratio=0.0`, 例外なし |
| 2 | 単一点に 1000 イベント | `centroid` がその座標、`var=0`, `bbox≈0`, `active_cell_ratio≈1/256`（16×16） |
| 3 | 全面一様分布 | `active_cell_ratio > 0.9`, `bbox_area_ratio > 0.8` |
| 4 | 極性の内訳 | `positive_count + negative_count == event_count`、`positive_ratio` が一致 |
| 5 | 2 窓連続で重心が移動 | `centroid_shift` が実距離と一致、`centroid_speed = shift / duration` |
| 6 | `event_rate_eps` | `event_count / duration_s` と一致 |
| 7 | 領域別 `share` の総和 | 1.0（`N > 0` のとき、`pytest.approx`） |
| 8 | 領域が常に 6 件返る | イベント 0 件の領域も含む |
| 9 | `idle_seconds` / `active_seconds` | 低活動窓が続くと `idle_seconds` が窓長ずつ増え、活動窓で 0 にリセット |
| 10 | 100,000 イベントの窓 | 処理時間 30 ms 未満（NFR-1） |
| 11 | 範囲外座標を含む窓 | `PipelineError` |

**テスト `tests/test_history.py`**:

| # | 項目 | 期待 |
|---|------|------|
| 1 | 一定 eps を長時間投入 | `rate_short` と `rate_long` がともにその値へ収束 |
| 2 | eps を階段状に上げる | `rate_short` が `rate_long` より速く追従する |
| 3 | 同じ特徴量が続く | `change_score` が 0 に近づく |
| 4 | 重心と活動量を急変させる | `change_score` が 0.55 を超える |
| 5 | `rate_cv_10s` | 一定入力で 0 近傍、変動入力で大きくなる |
| 6 | EMA 係数 | 窓長を 200 ms → 400 ms に変えても、同じ実時間で同じ収束具合になる |
| 7 | `is_warm` | `warmup_seconds` 経過前は `False` |

**完了条件**: 上記すべてが通る。テスト 4-10（性能）が通ること。

---

### Step 5: pipeline 後半

**作成**: `estimator.py`, `rule_estimator.py`, `smoother.py`, `duration.py`, `approachability.py`

**テスト `tests/test_rule_estimator.py`**（`SmoothedFeatures` を直接組み立てて渡す）:

| # | 入力 | 期待 |
|---|------|------|
| 1 | `idle_seconds=25` | `no_motion` |
| 2 | `change_score=0.7`, `rate_short=5000` | `transition` |
| 3 | `rate_short=4000`, `area_short=0.5`, `cell_short=0.4`, `speed_short=70` | `organizing` |
| 4 | `rate_short=1400`, `share[keyboard]=0.9`, `area_short=0.05`, `rate_cv_10s=0.2`, `active_seconds=10` | `focused` |
| 5 | `rate_short=300`, `rate_long=3000` | `short_break` |
| 6 | `rate_short=1200`, `share` が分散、`area_short=0.30`（< 0.35） | `working` |
| 7 | `rate_short=200`, `rate_long=250`, 他条件外 | `unknown`（`working` の下限 400 未満、`short_break` の減衰条件も不成立） |
| 8 | 評価順序: `idle_seconds=25` かつ `change_score=0.9` | `no_motion`（順位 1 が勝つ） |
| 9 | 評価順序: `organizing` と `focused` の条件を同時に満たす入力 | `organizing`（順位 3 が勝つ） |
| 10 | `focused` の条件を満たすが `active_seconds=2`（< 5） | `focused` にならない（`working`） |
| 11 | `noise_ratio=0.95` で `organizing` 条件 | `confidence` が補正なしの 0.6 倍 |
| 12 | `margin_confidence(v, th, span)` | `v=th` で 0.5、`v=th+span` で 0.95、`v<th` で 0.30 にクリップ |
| 13 | すべてのルールで `confidence` が 0.0–1.0 の範囲 | 範囲検証 |
| 14 | 各 `StatusEstimate.rule_id` がユニークで空でない | 詳細画面表示用 |

**テスト `tests/test_smoother.py`**（`FakeClock` で時間を進める）:

| # | 項目 | 期待 |
|---|------|------|
| 1 | 同じ候補を 5 回投入 | 現状態がその候補になる |
| 2 | 状態確定直後に別候補を 5 回投入（経過 1 秒） | `min_dwell_seconds`(3.0) 未満なので遷移しない |
| 3 | 同上を経過 4 秒後 | 遷移する |
| 4 | 候補が 3:2 で割れる（多数派の平均信頼度 0.6） | 多数派へ遷移 |
| 5 | 候補が 2:3 で割れる（`vote_min_count=3` 未達） | 遷移しない |
| 6 | 多数派の平均信頼度 0.4（< `enter_confidence`） | 遷移しない |
| 7 | 現状態の信頼度が `exit_confidence` 未満のとき 2 票 | 遷移する（緩和ルール） |
| 8 | `organizing` → `focused` を直接狙う | 遷移しない（遷移表で禁止） |
| 9 | `organizing` → `working` → `focused` | 遷移する |
| 10 | `force_no_motion=True` | `min_dwell` と多数決を無視して即座に `no_motion` |
| 11 | `transition` が 7 秒継続 | 強制再評価で `transition` 以外へ移る |
| 12 | 候補が同数のとき | 評価順位が上の状態が選ばれる |
| 13 | 100 窓の入力で状態変化が 3 秒未満の間隔で起きない | DoD-6 |
| 14 | `reset()` | `current` が `unknown` に戻り、バッファが空になる |

**テスト `tests/test_duration.py`**:

| # | 項目 | 期待 |
|---|------|------|
| 1 | 状態継続 10 秒 | `current_duration ≈ 10.0` |
| 2 | `changed=True` | 0 にリセット |
| 3 | 履歴に前状態が `ended_monotonic` 付きで残る | エントリの整合 |
| 4 | `had_status_within({FOCUSED}, 120, now)` | 120 秒以内に `focused` があれば `True` |
| 5 | 同上、130 秒前の `focused` のみ | `False` |
| 6 | `exclude_current=True` で現在が `focused` | 現在の分は数えない |
| 7 | `history_retention_minutes` 超過エントリ | 破棄される（PV-9） |
| 8 | 履歴が `history_limit` を超える | 古いものから捨てられ、件数が上限以内 |

**テスト `tests/test_approachability.py`**:

| # | 入力 | 期待 |
|---|------|------|
| 1 | `short_break`, duration=15, conf=0.8 | `likely_ok` |
| 2 | `short_break`, duration=5 | `undetermined`（10 秒未満） |
| 3 | `working`, 直近 60 秒に `focused` 履歴あり | `likely_ok` |
| 4 | `working`, 直近履歴なし | `undetermined` |
| 5 | `focused`, duration=60 | `prefer_later` |
| 6 | `focused`, duration=10 | `undetermined` |
| 7 | `no_motion` | `undetermined` |
| 8 | `transition` | `undetermined` |
| 9 | conf=0.3（< 0.50） | `undetermined`（状態によらず） |
| 10 | `system_status != running` | `undetermined` |
| 11 | `likely_ok` → `prefer_later` に変わる入力を 3 秒後に与える | `min_hold_seconds`(5.0) 以内なので `likely_ok` を維持 |
| 12 | 同上を 6 秒後 | `prefer_later` に変わる |
| 13 | `likely_ok` → `undetermined` を 1 秒後に与える | 即時に `undetermined`（安全側） |
| 14 | `ApproachabilityResolver` が `FeatureFrame` を引数に取らない | シグネチャ検証（PV-6 の担保） |

**完了条件**: 上記すべてが通る。

---

### Step 6: runner

**作成**: `pipeline/runner.py`, `app.py`, `__main__.py`, `logging_setup.py`（簡易版）

**内容**: [architecture.md](architecture.md) §12.2。この時点では UI を作らず、
`--headless` オプションでコンソールに状態変化を出力できるようにする
（`python -m deskmate --headless --demo`）。

**テスト `tests/test_runner.py`**（`FakeClock` + 同期駆動。QThread は使わず `_process_window()` を直接呼ぶ）:

| # | 項目 | 期待 |
|---|------|------|
| 1 | `keyboard_steady` を 30 秒分流す | 最終状態が `focused` |
| 2 | `desk_wide_active` を 30 秒分 | 最終状態が `organizing` |
| 3 | `quiet` を 40 秒分 | 最終状態が `no_motion` |
| 4 | `activity_decay` を 20 秒分 | 途中で `short_break` を経由する |
| 5 | `rapid_change` を 15 秒分 | 途中で `transition` を経由する |
| 6 | `noise_burst` を 15 秒分 | 表示ラベルが「状態不明」になる窓が存在する |
| 7 | `DEMO_SEQUENCE` を 340 秒分通す | 7 つの `DeskStatus` すべてが少なくとも 1 回確定する（DoD-2） |
| 8 | 全窓で `snapshot.duration_seconds >= 0` かつ単調増加（変化時のみリセット） | 継続時間の整合 |
| 9 | `set_detail_subscription(False)` のとき | `detail_ready` が 1 回も発火しない（PV-6） |
| 10 | `set_paused(True)` | 以後 `snapshot_ready` の `system_status` が `PAUSED` |
| 11 | 1 窓あたりの処理時間 | 平均 30 ms 未満 |
| 12 | **`set_paused(True)` → `set_paused(False)`** | 再開後に窓処理が再び進む。**アプリの再起動を必要としない**（`_loop` は一時停止中も生存し、`start()` の再呼び出しに依存しない） |
| 13 | 同上 | 再開時に全コンポーネントが reset され、`SystemStatus.STARTING` からウォームアップし直す |
| 14 | `stats_updated` | 1 秒間隔で発火する。1 秒以内の連続呼び出しでは発火しない |
| 15 | `stats_updated` / `detail_ready` の `PipelineStats` | runner 内部の実体とは別オブジェクト（後続の更新が受信側に見えない） |
| 16 | 窓内イベント数が `max_preview_points` を超える場合 | `DetailFrame` の点群が窓全体から間引かれている（先頭 N 件の切り出しではない） |
| 17 | 想定外の例外が 1 回発生 | ログを残してループが継続する |
| 18 | 想定外の例外が 1 分間に 4 回発生 | `SystemStatus.ERROR` になりループを停止する |
| 19 | 再接続 | `reconnect_interval_ms` の待機を挟む（失敗が続いてもビジーループにならない） |
| 20 | `max_open_retries` 超過 | `SystemStatus.ERROR` になるが、待機付きの再試行は継続する（恒久的に諦めない） |

テスト 12〜20 は `tests/test_runner_control.py` に置く。

**完了条件**: `python -m deskmate --headless --demo` で状態変化がコンソールに流れる。上記テストが通る。

---

### Step 7: character

**作成**: `character/__init__.py`, `mapping.py`, `renderer.py`

**テスト `tests/test_character_mapping.py`**:

| # | 入力 | 期待 |
|---|------|------|
| 1 | `(FOCUSED, 10)` | `TYPING` |
| 2 | `(FOCUSED, 700)` | `WORKING_AT_DESK` |
| 3 | `(SHORT_BREAK, 5)` | `DRINKING_TEA` |
| 4 | `(SHORT_BREAK, 90)` | `RESTING` |
| 5 | `(NO_MOTION, 10)` | `LOOKING_AROUND` |
| 6 | `(NO_MOTION, 200)` | `SLEEPING` |
| 7 | `(ORGANIZING, 0)` | `ORGANIZING_DESK` |
| 8 | `(TRANSITION, 0)` | `TRANSITIONING` |
| 9 | `(UNKNOWN, 0)` | `UNKNOWN` |
| 10 | `system_status=PAUSED` | `RESTING`（DeskStatus によらず） |
| 11 | `system_status=NO_SIGNAL` | `UNKNOWN` |
| 12 | 全 `DeskStatus` × duration 0 | 例外なく何らかの `AnimationId` を返す（網羅性） |
| 13 | `ShapeCharacterRenderer.available_animations` | 全 9 種の `AnimationId` を含む |

**完了条件**: 上記が通る。`ShapeCharacterRenderer` が素材なしで全アニメーションを描ける。

---

### Step 8: ui 基盤

**作成**: `ui/__init__.py`, `labels.py`, `theme.py`, `bridge.py`, `character_view.py`

**テスト `tests/test_labels.py`**:

| # | 項目 | 期待 |
|---|------|------|
| 1 | `format_duration(42)` | `"42秒"` |
| 2 | `format_duration(312)` | `"5分12秒"` |
| 3 | `format_duration(3780)` | `"1時間03分"` |
| 4 | `format_duration(0)` | `"0秒"` |
| 5 | `resolve_label(FOCUSED, conf=0.8)` | `"集中傾向"` |
| 6 | `resolve_label(FOCUSED, conf=0.3)` | `"状態不明"`（`display_confidence_floor` 未満） |
| 7 | `resolve_label(NO_MOTION, conf=0.3)` | `"一定時間、動きを検出していません"`（降格しない） |
| 8 | `resolve_label(NO_MOTION, conf=0.9, duration=200)` | `"静かな状態が続いています"` |
| 9 | 全 `DeskStatus` にラベルがある | 辞書の網羅性 |
| 10 | 全 `Approachability` / `SystemStatus` にラベルがある | 同上 |
| 11 | 全ラベル文字列に禁止語（「離席」「不在」「完全に安全」「匿名」）が含まれない | [privacy-design.md](privacy-design.md) §5.1 |

**完了条件**: 上記が通る。文字列がすべて `labels.py` に集約されている。

---

### Step 9: 常駐ウィジェット

**作成**: `ui/widget_window.py`

**内容**: [architecture.md](architecture.md) §14.1。

**確認項目（手動）**:

- [ ] 枠なし・半透明・最前面で表示される
- [ ] ドラッグで移動できる。位置が設定に保存され、再起動で復元される
- [ ] 最小化（64×64、キャラクターのみ）→ 復元ができる
- [ ] 状態ラベルと継続時間が 1 秒ごとに更新される
- [ ] 状態変化時のみ 350 ms の遷移アニメーションが走る
- [ ] 詳細ボタンで詳細画面が開く
- [ ] 停止ボタンで `PAUSED` になり、表示が「推定を停止しています」になる
- [ ] 右クリックメニューが出る
- [ ] 他のアプリを最大化しても前面に残る

**完了条件**: 上記すべて。`python -m deskmate --demo` で常駐ウィジェットのみが動く。

---

### Step 10: 共有画面

**作成**: `ui/share_window.py`

**内容**: [architecture.md](architecture.md) §14.3、[privacy-design.md](privacy-design.md) §3.3。

**確認項目**:

- [ ] キャラクター・抽象状態・継続時間・話しかけやすさ・最終更新時刻の 5 要素のみ
- [ ] 禁止項目が一切表示されない
- [ ] `import` に `FeatureFrame` / `DetailFrame` / `EventWindow` が無い
- [ ] `detail_updated` シグナルに接続していない
- [ ] 共有停止で「共有を停止しています」になり、直前の状態が残らない
- [ ] フルスクリーン切替ができる（F11）

**完了条件**: 上記すべて。デモモード 1 周で `likely_ok` / `prefer_later` / `undetermined` の 3 つが出る。

---

### Step 11: 詳細画面

**作成**: `ui/detail_window.py`, `ui/panels/*.py`

**内容**: [architecture.md](architecture.md) §14.2、[demo-scenario.md](demo-scenario.md) §2。

**実装順序（時間切れ時はこの逆順で削る）**:

1. `StatusHeader`（項目 8, 10）+ `CharacterView`（項目 9）+ プライバシー注記
2. `EventScatterPanel`（項目 1, 2）
3. `RegionPanel`（項目 6）
4. `FeatureTablePanel`（項目 7）
5. `MotionPanel`（項目 3, 4, 5）
6. `HistoryPanel`（項目 10 の帯グラフ）
7. デバッグ操作 UI

**確認項目**: [demo-scenario.md](demo-scenario.md) §5 の「詳細画面（10 項目）」チェックリスト。

**完了条件**: 10 項目すべてが表示され、10 Hz で更新される。詳細画面を閉じると
`detail_ready` の発火が止まる（ログか `PipelineStats` で確認）。

---

### Step 12: privacy / logging / トレイ / 異常系

**作成**: `privacy/__init__.py`, `privacy/guard.py`, `ui/tray.py`、`logging_setup.py` の完成、
`runner.py` の異常系処理の完成

**テスト `tests/test_privacy_guard.py`**:

| # | 項目 | 期待 |
|---|------|------|
| 1 | 既定設定で `can_save_raw_events()` | `False` |
| 2 | 既定設定で `assert_can_save_raw_events()` | `PrivacyViolationError` |
| 3 | `can_send_external()` | 設定によらず常に `False` |
| 4 | `assert_no_external_send("http://example.com")` | `PrivacyViolationError` |
| 5 | `StatusSnapshot` のフィールド集合 | [privacy-design.md](privacy-design.md) §9 の 10 項目と完全一致（`dataclasses.fields` で検証） |
| 6 | `StatusSnapshot.to_public_dict()` のキー | [status-definition.md](status-definition.md) §10 の 9 キーと完全一致 |
| 7 | 既定設定で 60 秒相当のパイプラインを回す | `data/` 配下にファイルが生成されない（DoD-9） |
| 8 | `src/deskmate` 全体の import 走査 | `mss` / `pyautogui` / `win32gui` / `requests` / `httpx` / `cv2` が現れない |
| 9 | `share_window.py` のソース走査 | `FeatureFrame` / `DetailFrame` / `EventWindow` が現れない |
| 10 | `retention_cutoff()` | `history_retention_minutes` に対応した値を返す |

**テスト `tests/test_source_failure.py`**（例外を注入する `FlakyEventSource` を用意）:

| # | 項目 | 期待 |
|---|------|------|
| 1 | `read()` が常に `None` | 1.5 秒後に `STALLED`、5 秒後に `NO_SIGNAL` |
| 2 | `NO_SIGNAL` 後 | 空窓の生成が止まる（`windows_processed` が増えない） |
| 3 | `read()` が `SourceDisconnectedError` | `reset()` → `open()` が呼ばれる |
| 4 | `read()` が `DecodeError` | そのバッチのみ破棄され、ループが継続する |
| 5 | `open()` が 10 回連続で失敗 | `SystemStatus.ERROR`、アプリは落ちない |
| 6 | 復帰後 | `STARTING` を経て通常状態に戻る（DoD-7） |
| 7 | `PipelineError` 発生 | 各コンポーネントが reset され、状態が `unknown` から再開する |
| 8 | キューが満杯 | 最も古いバッチが捨てられ、`dropped_batches` が増える |

**完了条件**: 上記が通る。トレイメニューの全項目が動作する。

---

### Step 13: file_source・通し確認

**作成**: `input/file_source.py`、テストデータ生成スクリプトは作らず、テスト内で一時ファイルを作る

**テスト `tests/test_file_source.py`**:

| # | 項目 | 期待 |
|---|------|------|
| 1 | `.jsonl` を読み込んで再生 | イベント総数が一致する |
| 2 | `.npz`（`EVENT_DTYPE`）を読み込む | 同上 |
| 3 | 存在しないパス | `SourceOpenError` |
| 4 | 未対応の拡張子（`.txt`） | `SourceOpenError` |
| 5 | スキーマ不一致の `.npz` | `SourceOpenError` |
| 6 | `loop: true` | 末尾到達後に先頭へ戻る |
| 7 | `loop: false` | 末尾で `SourceStatus.CLOSED` になり、`read()` が `None` を返し続ける |
| 8 | `speed: 2.0` | 同じ実時間で 2 倍のイベントが流れる |
| 9 | `seek(0.5)` | 中間位置から再生される |

**テスト `tests/test_demo_sequence.py`**:

| # | 項目 | 期待 |
|---|------|------|
| 1 | `DEMO_SEQUENCE` の合計時間 | 340.0 秒 |
| 2 | すべての `scenario_id` が `SCENARIOS` に存在する | 参照整合 |
| 3 | 各ステップの長さ | `min_dwell_seconds.default` の 5 倍（15 秒）以上 |
| 4 | 340 秒通した結果 | 7 状態すべてが確定する（DoD-2） |
| 5 | 同上 | 状態変化の間隔がすべて 3 秒以上（DoD-6） |
| 6 | 同上 | `likely_ok` / `prefer_later` / `undetermined` がすべて出現する |

**テスト `tests/test_ui_smoke.py`**（`QT_QPA_PLATFORM=offscreen`）:

| # | 項目 | 期待 |
|---|------|------|
| 1 | 3 ウィンドウを生成 | 例外が出ない |
| 2 | 各 `DeskStatus` の `StatusSnapshot` を流す | 例外なく描画される |
| 3 | `ShareWindow` の接続シグナル一覧 | `detail_updated` が含まれない |
| 4 | `WidgetWindow` の window flags | `WindowStaysOnTopHint` と `FramelessWindowHint` が立っている |
| 5 | 共有停止時の `ShareWindow` の表示テキスト | 「共有を停止しています」のみ。状態ラベルが含まれない |
| 6 | 詳細画面の open/close | `bridge.open_detail()` / `close_detail()` が呼ばれる |

**完了条件**: 全テストが通る。[demo-scenario.md](demo-scenario.md) §5 のチェックリストが全部埋まる。

---

### Step 14: 骨組み

**作成**: `input/hdf5_source.py`, `pipeline/ml_estimator.py`, `pipeline/voxel.py`

**内容**:

- `hdf5_source.py`: `EventSource` を継承し、`open()` で
  `NotImplementedError("EXT-1: HDF5 入力は未実装です")`。クラス定義とシグネチャは完成させる。
- `ml_estimator.py`: `StatusEstimator` を継承。`load()` で `NotImplementedError("EXT-6")`。
  ただし `feature_vector()` と `FEATURE_NAMES` は**実装する**（後の学習データ収集に必要）。
- `voxel.py`: [architecture.md](architecture.md) §9.3 の 4 関数を**実装する**。
  参照リポジトリ `EVENT_CAMERA/minimal_voxel_analysis.py` の数式に一致させること
  （コードはコピーせず、[status-definition.md](status-definition.md) §4.6 の数式から実装する）。
  ただし `features.voxel.enabled: false` の間は `FeatureExtractor` から呼ばない。

**テスト `tests/test_voxel.py`**:

| # | 項目 | 期待 |
|---|------|------|
| 1 | イベント 0 件 | ゼロ配列。`VoxelFeatures` の全項目が 0.0 |
| 2 | 全イベントが同一時刻（`t0 == tN`） | ゼロ配列（ゼロ除算しない） |
| 3 | 極性の変換 | `p=1` → `+1`、`p=0` → `-1` として加算されている |
| 4 | Bilinear kernel | 単一イベントを `t* = 1.5` の位置に置くと、ビン 1 と 2 に 0.5 ずつ分配される |
| 5 | `compute_diff_voxels` の形状 | `(num_bins - 1, h, w)` |
| 6 | 重心の正規化 | 画像中央に集中したイベントで `cx ≈ 0.5`, `cy ≈ 0.5` |
| 7 | 戻り値の順序 | `compute_centroid_trajectory` が `(cx, cy)` の順で返す（参照実装は逆順なので取り違え検出） |
| 8 | `spatial_scale=1` と `spatial_scale=4` | 重心（正規化座標）がおおよそ一致する（許容 ±0.05） |
| 9 | `num_bins=1` | `VoxelFeatures` の全項目が 0.0（差分が作れない） |
| 10 | `diff_centroid_shift` | 中心が一方向へ動く合成イベントで、静止時より大きくなる |
| 11 | 320×320・10 ビン・`spatial_scale=1` で 20,000 イベント | 処理時間 50 ms 未満（`np.bincount` 実装であること） |

`ml_estimator.feature_vector()` が `FEATURE_NAMES` と同じ長さの配列を返すこと。

**完了条件**: すべて import でき、`estimator: ml` を設定した `EstimationConfig` を
`create_estimator()` に渡すと `NotImplementedError`（`model_path` が未設定なら `ConfigError`）が
明示的に送出される。

---

## 4. テスト実行

```bash
.venv/Scripts/python -m pytest
```

GUI テストのみ:

```bash
.venv/Scripts/python -m pytest tests/test_ui_smoke.py
```

`tests/conftest.py` に用意するもの:

- `FakeClock`: `monotonic()` を手動で進められる `Clock` 実装
- `default_config`: `AppConfig` を返す fixture
- `make_window(...)`: `EventWindow` を組み立てるヘルパ
- `make_smoothed(...)`: `SmoothedFeatures` を既定値付きで組み立てるヘルパ（テストの記述量を減らす）
- `FlakyEventSource`: 任意の例外・`None` を返すテスト用ソース
- `qt_app`: `QApplication` の fixture（`QT_QPA_PLATFORM=offscreen` を設定）

---

## 5. MVP 完了条件（DoD）

[requirements.md](requirements.md) §9 の DoD-1〜DoD-12 をすべて満たすこと。
各 DoD と検証手段の対応:

| DoD | 検証 | 対応 Step |
|-----|------|:--------:|
| DoD-1 起動・常駐 | 手動 | 9 |
| DoD-2 7 状態が出る | `test_demo_sequence.py` #4 | 13 |
| DoD-3 詳細画面 10 項目 | [demo-scenario.md](demo-scenario.md) §5 | 11 |
| DoD-4 共有画面の禁止項目なし | `test_privacy_guard.py` #9、`test_ui_smoke.py` #3 | 10, 12 |
| DoD-5 話しかけやすさの導出 | `test_approachability.py` | 5 |
| DoD-6 最小継続時間 | `test_smoother.py` #13、`test_demo_sequence.py` #5 | 5, 13 |
| DoD-7 切断時の挙動 | `test_source_failure.py` | 12 |
| DoD-8 停止ボタン | 手動 | 9, 12 |
| DoD-9 保存が既定無効 | `test_privacy_guard.py` #7 | 12 |
| DoD-10 テスト全通過 | `pytest` | 13 |
| DoD-11 入力ソース切替 | 手動（`--source file`） | 13 |
| DoD-12 文言ルール適合 | `test_labels.py` #11 + レビュー | 8 |

---

## 6. 実装時の判断が必要になったら

設計書に書かれていない判断が必要になった場合、[../AGENTS.md](../AGENTS.md) の
「判断が必要なとき」の手順に従うこと。勝手に別の設計へ変えない。
特に以下は**設計書に従い、変更しないこと**:

- 技術構成（PySide6 単一プロセス）
- 状態の 7 種と表示文言
- 「離席中」と表示しない方針
- 共有画面の表示項目
- 保存・送信の既定無効
- `EventSource` インターフェースの契約
