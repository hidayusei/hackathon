# DeskMate アーキテクチャ設計書

版: 2.0（Raspberry Pi 内完結・3 状態構成）/ 最終更新: 2026-07-27

> ## 版 2.0 の変更点（必読）
>
> | # | 変更 | 影響する節 |
> |---|------|-----------|
> | 1 | **Raspberry Pi 5 内で完結**する。撮像・処理・UI をすべて Pi 上で動かし、PC への送信をしない | §1, §2, §7 |
> | 2 | 入力は **Metavision SDK からのライブ受信**（`MetavisionEventSource`）。Windows では import できないので `source: auto` でダミーへ自動フォールバックする | §7 |
> | 3 | 状態を **7 種から 3 種**へ（離席中 / 集中 / 非集中） | [status-definition.md](status-definition.md) §2 |
> | 4 | **共有画面を廃止**。画面は常駐ウィジェットと詳細画面の 2 つ | §14 |
> | 5 | キャラクターを **30×30 ドット絵の GIF** に変更（作成済み） | §13 |
> | 6 | **休憩促し**（連続集中 25 分）を追加 | §11 |
>
> 版 1.0 の記述のうち、共有画面・話しかけやすさ・7 状態に関する部分は無効。
> 移行対応表は [status-definition.md](status-definition.md) §11 にある。

本書は実装担当（Codex）が追加判断なしに実装できる粒度で、技術構成・モジュール構成・
クラス / 関数シグネチャ・データ形式・設定項目を定義する。

- 状態・特徴量・閾値・表示文字列の**具体値**は [status-definition.md](status-definition.md) が正典。
- 実装順序とテスト項目は [implementation-plan.md](implementation-plan.md)。
- プライバシー要件は [privacy-design.md](privacy-design.md)。

---

## 1. 技術構成の比較と決定

### 1.1 評価条件

Windows で開発 / イベント処理は Python / 常駐ウィジェットが必要 / デモ画面が分かりやすい /
ハッカソン期間内に完成 / 後から Raspberry Pi 入力を追加 / キャラクター素材を後から差し替え。

### 1.2 候補比較

| 案 | 構成 | 常駐ウィジェット | 点群描画 | 実装コスト | Windows 相性 | 素材差し替え |
|----|------|:---------------:|:--------:|:---------:|:-----------:|:-----------:|
| A | Python バックエンド + Web フロント（FastAPI + ブラウザ） | ×（ブラウザは最前面固定・枠なし表示が困難） | △（WebSocket で毎窓 5,000 点を転送、帯域と遅延） | 中 | ○ | ◎ |
| B | **Python + PySide6 デスクトップアプリ** | ◎（`Qt.WindowStaysOnTopHint` + `FramelessWindowHint`） | ◎（pyqtgraph の `ScatterPlotItem` はネイティブ描画） | **小**（単一プロセス・単一言語・IPC 不要） | ◎ | ○（QMovie / QSvg / QLabel 差し替え、Live2D は WebEngine 埋め込みで対応可） |
| C | Python + Electron | ○ | △ | 大（Node + Python の二重管理、IPC、配布） | ○ | ◎ |
| D | Python + Tauri | ○ | △ | 大（Rust ツールチェーン、学習コスト） | △ | ◎ |
| E | Python のみの簡易 GUI（Tkinter） | △（最前面は可能だが描画性能が低い） | ×（数千点の毎秒更新に耐えない） | 小 | ○ | × |

### 1.3 決定：**案 B（Python / PySide6 デスクトップアプリ）を Raspberry Pi 5 上で実行**

**版 2.0 で実行環境が変わった。** アプリは Raspberry Pi 5 の画面上で動く常駐ウィジェットになる。
Windows は「開発と UI 確認のための環境」であり、本番実行環境ではない。

| 項目 | Raspberry Pi 5（本番） | Windows（開発） |
|------|----------------------|----------------|
| 入力 | `MetavisionEventSource`（ライブ） | `DummyEventSource` / `FileEventSource` |
| Metavision SDK | あり（Prophesee 公式イメージ） | **なし**（Linux 専用） |
| Python | Raspberry Pi OS のシステム Python | 3.11–3.13 |
| PySide6 | `pip install PySide6`（aarch64 wheel あり） | 同左 |
| 画面 | Pi に接続したディスプレイ | 開発機のデスクトップ |

**同一のコードベース・同一の設定ファイルで両方が動くこと**を要件とする。
差分は `input.source` の解決結果だけに閉じ込める（§7.4）。

理由:

1. **IPC が不要**。推定パイプラインと UI が同一プロセスで動くため、通信プロトコル設計・
   シリアライズ・接続断のハンドリングを作らずに済む。ハッカソン期間では最大の短縮要因。
2. **常駐ウィジェットが素直に作れる**。枠なし・最前面・ドラッグ移動・システムトレイ常駐が
   Qt の標準機能で完結する。案 A / E はここが最大の障壁になる。
3. **点群描画が速い**。pyqtgraph は 5,000 点の毎 100 ms 更新を CPU 数 % で処理できる。
4. **入力層の差し替えに影響しない**。`EventSource` はプロセス内インターフェースなので、
   後から WebSocket 受信スレッドを追加しても UI 側の変更が発生しない。
5. **キャラクター差し替え**は `CharacterRenderer` インターフェースで吸収する。
   版 2.0 の既定は `GifCharacterRenderer`（QMovie で 30×30 のドット絵 GIF を再生）。
   素材を差し替えたい場合は同じファイル名の GIF を置くだけでよい。

**この決定は確定であり、実装時に他案へ戻らないこと。**

### 1.4 使用技術・ライブラリ（確定）

| 用途 | ライブラリ | バージョン | 必須 |
|------|-----------|-----------|:----:|
| 言語 | Python | 3.11 – 3.13（開発機は 3.13.5） | ○ |
| GUI | PySide6 | >= 6.8, < 7 | ○ |
| 数値計算 | numpy | >= 1.26 | ○ |
| 可視化（点群・グラフ） | pyqtgraph | >= 0.13.7 | ○ |
| 設定検証 | pydantic | >= 2.7, < 3 | ○ |
| 設定ファイル | PyYAML | >= 6.0 | ○ |
| テスト | pytest | >= 8.0 | ○ |
| GUI テスト | pytest-qt | >= 4.4 | ○ |
| HDF5 入力（EXT-1） | h5py | >= 3.11 | × |
| 軽量学習モデル（EXT-6） | scikit-learn | >= 1.5 | × |

使ってはならないもの（MVP）: OpenCV、PyTorch、TensorFlow、FastAPI、Flask、requests、
外部サービス用ネットワークライブラリ。§7.5 の UDP は標準ライブラリ `socket` のみ使う。

---

## 2. システム全体構成

```
                    ┌─────────────────────────── DeskMate プロセス ───────────────────────────┐
                    │                                                                          │
 (将来) Raspberry Pi │  ┌──── AcquisitionThread (QThread) ────┐                                │
   + イベントカメラ  │  │  EventSource (ABC)                   │                                │
        ──────────► │  │   ├ DummyEventSource   [MVP]         │                                │
        (未実装)     │  │   ├ FileEventSource    [MVP]         │  EventBatch                    │
                    │  │   ├ Hdf5EventSource    [EXT-1]       │  ──────────┐                   │
                    │  │   └ UdpEventSource      [M07]       │            │                   │
                    │  └──────────────────────────────────────┘            ▼                   │
                    │                                         ┌─── PipelineThread (QThread) ──┐ │
                    │                                         │  EventWindower                │ │
                    │                                         │      ▼ EventWindow            │ │
                    │                                         │  FeatureExtractor             │ │
                    │                                         │      ▼ FeatureFrame           │ │
                    │                                         │  FeatureHistory (EMA/履歴)     │ │
                    │                                         │      ▼ SmoothedFeatures        │ │
                    │                                         │  StatusEstimator (ABC)         │ │
                    │                                         │   ├ RuleStatusEstimator [MVP]  │ │
                    │                                         │   └ MlStatusEstimator  [EXT-6] │ │
                    │                                         │      ▼ StatusEstimate          │ │
                    │                                         │  StatusSmoother                │ │
                    │                                         │  DurationTracker               │ │
                    │                                         │  BreakTracker                  │ │
                    │                                         │      ▼ StatusSnapshot          │ │
                    │                                         └───────────┬────────────────────┘ │
                    │                                                     │ Qt Signal (queued)   │
                    │                                    ┌────────────────▼──────────────────┐   │
                    │                                    │  UiBridge (QObject, UI スレッド)   │   │
                    │                                    └──┬──────────┬──────────┬──────────┘   │
                    │                                       ▼          ▼          ▼              │
                    │                              WidgetWindow  DetailWindow  ShareWindow        │
                    │                              (常駐)        (本人用)      (共有用)            │
                    │                                       └── CharacterView (Renderer 差替可) ──│
                    └──────────────────────────────────────────────────────────────────────────┘
```

スレッド構成は 3 本のみ。

| スレッド | 役割 | 生存期間 |
|---------|------|---------|
| メイン（UI） | Qt イベントループ、3 ウィンドウ、システムトレイ | アプリ全体 |
| Acquisition | `EventSource.read()` のポーリング、`EventBatch` をキューへ投入 | 推定中のみ |
| Pipeline | キューから取り出し、窓化 → 特徴量 → 推定 → 平滑化 → シグナル発火 | 推定中のみ |

Acquisition と Pipeline の間は `queue.Queue(maxsize=config.pipeline.queue_size)`（既定 64）。
満杯時は**最も古いバッチを捨てる**（`drop_oldest`）。捨てた件数は `PipelineStats.dropped_batches` に加算し、詳細画面に表示する。

---

## 3. データフロー

```
EventBatch(x,y,t,p 配列, t_start_us, t_end_us, seq)
    │  EventWindower.push() … センサ時刻 t を基準に window_ms ごとに切り出す
    ▼
EventWindow(x,y,t,p, window_index, t_start_us, t_end_us, duration_s)
    │  FeatureExtractor.extract()
    ▼
FeatureFrame(global: GlobalFeatures, regions: dict[RegionId, RegionFeatures], voxel: VoxelFeatures|None)
    │  FeatureHistory.update() … EMA・履歴・idle/active 秒数・change_score
    ▼
SmoothedFeatures
    │  StatusEstimator.estimate()
    ▼
StatusEstimate(status, confidence, reason, rule_id)
    │  StatusSmoother.update()
    ▼
(DeskStatus 確定, changed: bool)
    │  DurationTracker.update() → duration_seconds
    │  BreakTracker.update() → BreakState (focus_streak_seconds, break_due)
    ▼
StatusSnapshot  ──(Qt signal: snapshot_ready)──►  UiBridge  ──►  3 ウィンドウ
    │
    └─(詳細画面が開いているときだけ)─► DetailFrame(features + 間引き点群 + 履歴) ──(detail_ready)──► DetailWindow
```

**重要**: `StatusSnapshot` には座標も特徴量も含めない。詳細画面用の情報は `DetailFrame` に分離し、
詳細画面が開いている間だけ生成・送出する（[privacy-design.md](privacy-design.md) PV-6）。

---

## 4. ディレクトリ構成

```
DeskMate/
├─ README.md
├─ AGENTS.md
├─ CLAUDE.md
├─ pyproject.toml
├─ requirements.txt
├─ .gitignore
├─ tools/
│   └─ make_character_gifs.py  # 版2.0: GIF 再生成（Pillow 必要、実行時は不要）
├─ docs/
│   ├─ requirements.md
│   ├─ architecture.md
│   ├─ implementation-plan.md
│   ├─ status-definition.md
│   ├─ privacy-design.md
│   └─ demo-scenario.md
├─ config/
│   ├─ default.yaml            # 既定設定（リポジトリ管理）
│   └─ regions.sample.yaml     # 領域定義の記入例
├─ assets/
│   └─ character/              # 版2.0: 作成済みの GIF が入っている
│       ├─ running.gif         # 集中
│       ├─ sitting.gif         # 非集中
│       ├─ sleeping.gif        # 離席中
│       ├─ break.gif           # 休憩促し
│       ├─ frames/<action>/NN.png
│       └─ README.md
├─ data/                       # .gitignore 済み。録画データの置き場
│   └─ .gitkeep
├─ src/
│   └─ deskmate/
│       ├─ __init__.py
│       ├─ __main__.py
│       ├─ app.py
│       ├─ core/
│       │   ├─ __init__.py
│       │   ├─ enums.py
│       │   ├─ types.py
│       │   ├─ errors.py
│       │   └─ clock.py
│       ├─ config/
│       │   ├─ __init__.py
│       │   ├─ schema.py
│       │   └─ loader.py
│       ├─ input/
│       │   ├─ __init__.py
│       │   ├─ base.py
│       │   ├─ factory.py
│       │   ├─ dummy_source.py
│       │   ├─ scenarios.py
│       │   ├─ file_source.py
│       │   ├─ metavision_source.py  # 版2.0: Pi のライブ入力
│       │   └─ hdf5_source.py        # EXT-1: 骨組みのみ
│       ├─ pipeline/
│       │   ├─ __init__.py
│       │   ├─ windower.py
│       │   ├─ regions.py
│       │   ├─ features.py
│       │   ├─ voxel.py
│       │   ├─ history.py
│       │   ├─ estimator.py
│       │   ├─ rule_estimator.py
│       │   ├─ ml_estimator.py       # EXT-6: 骨組みのみ
│       │   ├─ smoother.py
│       │   ├─ duration.py
│       │   ├─ break_tracker.py      # 版2.0: 休憩促し
│       │   └─ runner.py
│       ├─ character/
│       │   ├─ __init__.py
│       │   ├─ mapping.py
│       │   └─ renderer.py
│       ├─ ui/
│       │   ├─ __init__.py
│       │   ├─ bridge.py
│       │   ├─ labels.py
│       │   ├─ theme.py
│       │   ├─ character_view.py
│       │   ├─ status_stripe.py
│       │   ├─ widget_window.py
│       │   ├─ detail_window.py
│       │   ├─ break_banner.py       # 版2.0: 休憩促しバナー
│       │   ├─ tray.py
│       │   └─ panels/
│       │       ├─ __init__.py
│       │       ├─ event_scatter_panel.py
│       │       ├─ motion_panel.py
│       │       ├─ region_panel.py
│       │       ├─ feature_table_panel.py
│       │       └─ history_panel.py
│       ├─ privacy/
│       │   ├─ __init__.py
│       │   └─ guard.py
│       └─ logging_setup.py
└─ tests/
    ├─ conftest.py
    ├─ test_config.py
    ├─ test_windower.py
    ├─ test_regions.py
    ├─ test_features.py
    ├─ test_voxel.py
    ├─ test_history.py
    ├─ test_rule_estimator.py
    ├─ test_smoother.py
    ├─ test_duration.py
    ├─ test_break_tracker.py
    ├─ test_character_mapping.py
    ├─ test_dummy_source.py
    ├─ test_file_source.py
    ├─ test_source_failure.py
    ├─ test_runner.py
    ├─ test_privacy_guard.py
    ├─ test_labels.py
    ├─ test_demo_sequence.py
    └─ test_ui_smoke.py
```

パッケージは `src` レイアウト。`pip install -e .` 後に `python -m deskmate` で起動する。

---

## 5. 各ファイルの責務

### 5.1 core

| ファイル | 責務 |
|---------|------|
| `core/enums.py` | `DeskStatus`(3値) / `SystemStatus` / `RegionId` / `AnimationId`(4値) / `SourceStatus` / `SourceKind` の定義のみ。他モジュールに依存しない。**`Approachability` は版2.0 で削除** |
| `core/types.py` | `EventBatch` / `EventWindow` / `GlobalFeatures` / `RegionFeatures` / `FeatureFrame` / `VoxelFeatures` / `SmoothedFeatures` / `StatusEstimate` / `StatusSnapshot` / `DetailFrame` / `HistoryEntry` / `PipelineStats` の dataclass 定義。すべて frozen（`DetailFrame` を除く） |
| `core/errors.py` | 例外階層 |
| `core/clock.py` | 単調時刻の取得と、センサ時刻（µs）↔ 経過秒の変換。テストで差し替えられるよう `Clock` プロトコルを用意 |

### 5.2 config

| ファイル | 責務 |
|---------|------|
| `config/schema.py` | pydantic モデルで全設定項目と既定値・バリデーションを定義 |
| `config/loader.py` | `config/default.yaml` → ユーザ設定（`%APPDATA%/DeskMate/config.yaml`）→ CLI 引数の順にマージして `AppConfig` を返す。ユーザ設定の雛形出力も担当 |

### 5.3 input

| ファイル | 責務 |
|---------|------|
| `input/base.py` | `EventSource` 抽象基底クラスと `SourceStatus`。**すべての入力実装が守る唯一の契約** |
| `input/factory.py` | `SourceKind` から具体クラスを生成する。ここ以外で具体クラスを直接 import しない |
| `input/dummy_source.py` | シナリオ定義に従って合成イベントを生成する。デモモードとデバッグモードを持つ |
| `input/scenarios.py` | 8 シナリオのパラメータ定義と、デモ用の時系列シーケンス |
| `input/file_source.py` | JSONL / NPZ ファイルからイベントを読み、指定速度で再生する |
| `input/metavision_source.py` | **版2.0**。Metavision SDK からライブ受信する。`metavision_core` は Raspberry Pi にしか無いので、import はメソッド内で遅延実行する |
| `input/hdf5_source.py` | EXT-1。MVP では `open()` で `NotImplementedError` を投げる骨組みのみ |

### 5.4 pipeline

| ファイル | 責務 |
|---------|------|
| `pipeline/windower.py` | `EventBatch` を受け取り、センサ時刻基準で `EventWindow` に切り出す。バッチ境界をまたぐイベントを保持する |
| `pipeline/regions.py` | 領域矩形の保持と、イベント座標 → `RegionId` の割り当て（ベクトル化） |
| `pipeline/features.py` | `EventWindow` → `FeatureFrame`。全体特徴量と領域別特徴量を numpy で算出 |
| `pipeline/voxel.py` | EXT-5。Voxel Grid 変換・時間ビン差分・差分重心・変化量。既定では呼ばれない |
| `pipeline/history.py` | 特徴量の EMA・リングバッファ・`idle_seconds`/`active_seconds`・`change_score`・`rate_cv_10s` を管理し `SmoothedFeatures` を返す |
| `pipeline/estimator.py` | `StatusEstimator` 抽象基底クラス |
| `pipeline/rule_estimator.py` | ルールベース推定。[status-definition.md](status-definition.md) §5 をそのまま実装 |
| `pipeline/ml_estimator.py` | EXT-6。同じ ABC を実装する骨組み。MVP では `load()` で `NotImplementedError` |
| `pipeline/smoother.py` | 多数決・最小継続時間・ヒステリシス・遷移表 |
| `pipeline/duration.py` | 確定状態の継続時間と、直近の確定履歴（`HistoryEntry` のリング）を管理 |
| `pipeline/break_tracker.py` | **版2.0**。連続集中時間を数え、25 分で `break_due` を立てる。スヌーズとリセットを管理する |
| `pipeline/runner.py` | 上記を束ねる `PipelineRunner`（QObject）。スレッドで動き、Qt シグナルを発火 |

### 5.5 character / ui / privacy

| ファイル | 責務 |
|---------|------|
| `character/mapping.py` | `DeskStatus` + 継続時間 + `SystemStatus` → `AnimationId` の決定的変換 |
| `character/renderer.py` | `CharacterRenderer` ABC と `GifCharacterRenderer`（**版2.0 の既定**。QMovie で GIF を再生し最近傍で整数倍拡大する） |
| `ui/bridge.py` | パイプラインのシグナルを受け、UI 用に保持・再配信する。UI からの制御コマンド（停止・再開・詳細購読）をパイプラインへ送る唯一の窓口 |
| `ui/labels.py` | 表示文字列と `resolve_label()` / `format_duration()`。文字列のハードコードはここだけ |
| `ui/theme.py` | 色・フォント・サイズ定数 |
| `ui/character_view.py` | `CharacterRenderer` を載せる QWidget。状態変化時の遷移アニメーション |
| `ui/status_stripe.py` | 常駐ウィジェット下部の状態履歴ストライプ。`StatusSnapshot` のみを自前で蓄積し、同じ状態が続く区間を 1 つの矩形にまとめて描く |
| `ui/widget_window.py` | 常駐ウィジェット |
| `ui/detail_window.py` | 本人向け詳細画面。パネルを配置し `DetailFrame` を配る |
| `ui/break_banner.py` | **版2.0**。`break_due` のときウィジェット内に出る休憩促しバナー。「あとで」「休憩する」ボタンを持つ |
| `ui/tray.py` | システムトレイアイコンとメニュー |
| `ui/panels/*.py` | 詳細画面の各パネル |
| `privacy/guard.py` | 保存・送信の可否を一元管理する `PrivacyGuard`。保存系 API はここを通す |
| `logging_setup.py` | ロガー初期化。座標・特徴量を既定でログに書かない |
| `app.py` | `DeskMateApp`。QApplication 生成、設定読込、スレッド起動、ウィンドウ生成、終了処理 |
| `__main__.py` | CLI 引数のパースと `DeskMateApp` の起動 |

---

## 6. 内部データ形式

`src/deskmate/core/types.py`。すべて `@dataclass(frozen=True, slots=True)`（`DetailFrame`, `PipelineStats` を除く）。

### 6.1 イベント

```python
import numpy as np
from dataclasses import dataclass, field

EVENT_DTYPE = np.dtype([("x", "<u2"), ("y", "<u2"), ("t", "<i8"), ("p", "i1")])
# x, y: uint16 (px)  /  t: int64 (センサ基準マイクロ秒, 単調増加)  /  p: int8 (0 or 1)

# Metavision SDK の EventCD と互換。フィールドの並びと p の型が異なるので変換が必要。
# 出典: Metavision SDK 公式ドキュメント「HDF5 Event File Format」の /CD/events の定義。
EVENT_DTYPE_METAVISION = np.dtype([("x", "<u2"), ("y", "<u2"), ("p", "<i2"), ("t", "<i8")])

@dataclass(frozen=True, slots=True)
class EventBatch:
    """入力ソースが 1 回の read() で返すイベント列。"""
    x: np.ndarray          # shape (n,), dtype uint16
    y: np.ndarray          # shape (n,), dtype uint16
    t: np.ndarray          # shape (n,), dtype int64, 昇順ソート済みであること
    p: np.ndarray          # shape (n,), dtype int8, 値は 0 or 1
    t_start_us: int        # このバッチが表す区間の開始（センサ時刻）
    t_end_us: int          # 終了（排他）
    seq: int               # 0 起点の連番。欠落検出に使う
    received_monotonic: float  # PC 側の受信時刻（time.monotonic()）

    @property
    def size(self) -> int: ...

    @staticmethod
    def empty(t_start_us: int, t_end_us: int, seq: int) -> "EventBatch": ...

    @staticmethod
    def from_records(records: list[dict], seq: int) -> "EventBatch":
        """[{"x":125,"y":210,"t":123456789,"p":1}, ...] から生成する。
        Raises: DecodeError（キー欠落・型不正・座標範囲外）"""

    @staticmethod
    def from_structured(arr: np.ndarray, seq: int) -> "EventBatch":
        """構造化配列から生成する。EVENT_DTYPE と EVENT_DTYPE_METAVISION の
        どちらも受け付ける（フィールド名 x/y/t/p の有無で判定し、p は int8 へキャストする）。
        p が -1/+1 で入っている場合は 0/1 に正規化する（p = (p > 0).astype(int8)）。
        Raises: DecodeError（必要なフィールドが無い・t が非単調）"""
```

- `t` は昇順であることを `from_records` で検証する（違反時 `DecodeError`）。
- 空バッチは許容する（「入力はあるが動きがない」を表現するため）。

```python
@dataclass(frozen=True, slots=True)
class EventWindow:
    x: np.ndarray
    y: np.ndarray
    t: np.ndarray
    p: np.ndarray
    window_index: int      # 0 起点の窓連番
    t_start_us: int
    t_end_us: int
    duration_s: float      # (t_end_us - t_start_us) / 1e6
    truncated: bool        # max_events_per_window で間引いたか
```

### 6.2 特徴量

```python
@dataclass(frozen=True, slots=True)
class GlobalFeatures:
    event_count: int
    positive_count: int
    negative_count: int
    positive_ratio: float
    event_rate_eps: float
    centroid_x: float
    centroid_y: float
    centroid_shift: float
    centroid_speed: float
    var_x: float
    var_y: float
    spatial_std: float
    bbox_width: float
    bbox_height: float
    bbox_area_ratio: float
    active_cell_ratio: float
    event_count_delta: int
    event_rate_delta: float
    activity_ratio_10s: float
    idle_seconds: float
    active_seconds: float
    noise_ratio: float

@dataclass(frozen=True, slots=True)
class RegionFeatures:
    region_id: RegionId
    event_count: int
    event_rate_eps: float
    share: float
    centroid_x: float
    centroid_y: float
    active_cell_ratio: float

@dataclass(frozen=True, slots=True)
class VoxelFeatures:
    diff_l1: float                # mean(|ΔV|) の全ステップ平均
    diff_centroid_x: float        # 0.0–1.0 正規化
    diff_centroid_y: float        # 0.0–1.0 正規化
    diff_energy: float            # Σ ΔV²
    diff_centroid_shift: float    # 重心軌跡の総移動量（正規化座標）

@dataclass(frozen=True, slots=True)
class FeatureFrame:
    window_index: int
    t_start_us: int
    t_end_us: int
    duration_s: float
    global_features: GlobalFeatures
    regions: dict[RegionId, RegionFeatures]   # 常に 6 領域すべてを含む
    voxel: VoxelFeatures | None               # 既定 None
    grid_counts: np.ndarray                   # shape (grid_rows, grid_cols), int32。詳細画面のヒートマップ用
    compute_ms: float

@dataclass(frozen=True, slots=True)
class SmoothedFeatures:
    rate_short: float
    rate_long: float
    centroid_short_x: float
    centroid_short_y: float
    centroid_long_x: float
    centroid_long_y: float
    area_short: float
    area_long: float
    speed_short: float
    cell_short: float
    share_short: dict[RegionId, float]
    share_long: dict[RegionId, float]
    rate_cv_10s: float
    change_score: float
    idle_seconds: float
    active_seconds: float
    activity_ratio_10s: float
    noise_ratio: float
    elapsed_seconds: float     # パイプライン開始からの経過秒
```

`FeatureFrame.to_display_dict() -> dict[str, str]` を用意し、詳細画面の特徴量テーブルはこれを使う
（表示順・桁数をここで固定する）。

### 6.3 推定結果

```python
@dataclass(frozen=True, slots=True)
class StatusEstimate:
    status: DeskStatus
    confidence: float          # 0.0–1.0
    rule_id: str               # 例 "R2_focused"。詳細画面に表示
    reason: str                # 例 "rate_short=7321 >= 6000, area=0.41 >= 0.35"（日本語不要）

@dataclass(frozen=True, slots=True)
class HistoryEntry:
    status: DeskStatus
    started_monotonic: float
    ended_monotonic: float | None    # 継続中は None
    peak_confidence: float

@dataclass(frozen=True, slots=True)
class StatusSnapshot:
    """UI へ渡す確定結果。座標・特徴量を含まないこと。"""
    status: DeskStatus
    system_status: SystemStatus
    label: str                   # 表示済み文字列（resolve_label 適用後）
    animation: AnimationId
    duration_seconds: float
    confidence: float
    focus_streak_seconds: float  # 連続集中秒数（休憩促しの根拠）
    break_due: bool              # 休憩を促すべきか
    changed: bool                # この更新で状態が切り替わったか
    updated_at: datetime         # ローカルタイムゾーン付き

    def to_public_dict(self) -> dict:
        """[status-definition.md] §10 の JSON 表現を返す。共有目的で外に出せる唯一の形。"""
```

```python
@dataclass(slots=True)          # frozen ではない（点群配列を差し替えるため）
class DetailFrame:
    """詳細画面が開いているときだけ生成される。プロセス外に出してはならない。"""
    snapshot: StatusSnapshot
    features: FeatureFrame
    smoothed: SmoothedFeatures
    estimate: StatusEstimate
    preview_x: np.ndarray        # 間引き後の点群 x（最大 ui.detail.max_preview_points 点）
    preview_y: np.ndarray
    preview_p: np.ndarray
    history: list[HistoryEntry]  # 直近 ui.detail.history_seconds 秒
    rate_series: np.ndarray      # 直近 60 秒の event_rate_eps（float32）
    stats: PipelineStats

@dataclass(slots=True)
class PipelineStats:
    windows_processed: int
    dropped_batches: int
    last_compute_ms: float
    avg_compute_ms: float
    source_status: SourceStatus
    source_name: str
    queue_depth: int
```

---

## 7. 入力インターフェース

`src/deskmate/input/base.py`

```python
class SourceStatus(str, Enum):
    IDLE         = "idle"
    CONNECTING   = "connecting"
    STREAMING    = "streaming"
    STALLED      = "stalled"        # 接続はあるがデータが来ない
    DISCONNECTED = "disconnected"
    ERROR        = "error"
    CLOSED       = "closed"

class EventSource(abc.ABC):
    """イベント入力の唯一の契約。
    実装は通信方式・ファイル形式を隠蔽し、EventBatch のみを返す。
    スレッド安全性: open/read/close は同一スレッド（AcquisitionThread）からのみ呼ばれる。
    request_stop() だけは他スレッドから呼ばれてよい。
    """

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """UI 表示用の名前。例 'dummy(scenario)'。"""

    @property
    @abc.abstractmethod
    def status(self) -> SourceStatus: ...

    @abc.abstractmethod
    def open(self) -> None:
        """接続・ファイルオープン。冪等。
        Raises: SourceOpenError"""

    @abc.abstractmethod
    def read(self, timeout_s: float) -> EventBatch | None:
        """最大 timeout_s だけ待って 1 バッチ返す。
        Returns:
            EventBatch: 取得できた場合（イベント 0 件の空バッチもありうる）
            None: timeout_s 内にデータが到着しなかった場合（エラーではない）
        Raises:
            SourceDisconnectedError: 接続が切れた（呼び出し側が再接続を試みる）
            DecodeError: 受信データが仕様に合わない（該当バッチのみ破棄して継続）
            SourceError: その他
        """

    @abc.abstractmethod
    def close(self) -> None:
        """解放。冪等。例外を投げないこと（内部でログのみ）。"""

    def request_stop(self) -> None:
        """他スレッドから read() のブロックを解除する。既定は no-op。"""

    def reset(self) -> None:
        """再接続前の内部状態リセット。既定は close() + open()。"""

    @property
    def supports_seek(self) -> bool:
        """ファイル系ソースが True。UI の再生位置操作の可否に使う。既定 False。"""
```

### 7.1 実装クラス

```python
class DummyEventSource(EventSource):
    def __init__(self, config: DummyInputConfig, sensor: SensorConfig,
                 clock: Clock | None = None) -> None: ...
    def set_scenario(self, scenario_id: str) -> None:
        """デバッグモードでシナリオを手動固定する。
        Raises: ValueError（未知の scenario_id）"""
    @property
    def current_scenario(self) -> str: ...

class FileEventSource(EventSource):
    """.jsonl（1 行 1 イベントの JSON）または .npz（EVENT_DTYPE の構造化配列）を再生する。
    Raises: SourceOpenError（ファイルなし・拡張子不明・スキーマ不一致）"""
    def __init__(self, config: FileInputConfig, sensor: SensorConfig) -> None: ...
    @property
    def supports_seek(self) -> bool: return True
    def seek(self, position_ratio: float) -> None: ...

class MetavisionEventSource(EventSource):
    """版2.0。Raspberry Pi 上の Metavision SDK からライブでイベントを受け取る。

    metavision_core は Raspberry Pi にしか存在しないため、**モジュール先頭で import しない**。
    open() の中で遅延 import し、失敗したら SourceOpenError にラップして投げる。

    open():
        from metavision_core.event_io import EventsIterator
        self._iterator = EventsIterator(
            input_path="",                       # 空文字 = 接続中の最初のカメラ
            delta_t=config.delta_t_us,           # 既定 20000 (=20ms)
            relative_timestamps=False,
        )
        self._stream = iter(self._iterator)
        センサ解像度は self._iterator.get_size() -> (height, width) から取得し、
        AppConfig.sensor と食い違う場合は WARNING を出して**イテレータ側の値を採用する**。

    read(timeout_s):
        next(self._stream) で EventCD の構造化配列を 1 個取り出し、
        EventBatch.from_structured() へ渡す（フィールド順 x,y,p,t / p は int16）。
        StopIteration -> SourceDisconnectedError
        イテレータは delta_t ごとにブロックするので、timeout_s は目安としてのみ使う。

    close():
        イテレータを解放する。例外は握ってログのみ。

    前提（GitHub の EVENT_CAMERA/RaspberryPi.md で確認済み）:
        sudo dtoverlay genx320,cam0
        ./rp5_setup_v4l.sh              # /home/eventcamera/rpi-sensor-drivers/
        export PSEE_VAR_V4L2_BSIZE=1
    これらは DeskMate では実行しない。起動前に済ませておく前提とし、
    open() が失敗したときのエラーメッセージにこの手順を出す。
    """

    def __init__(self, config: MetavisionInputConfig, sensor: SensorConfig) -> None: ...


class Hdf5EventSource(EventSource):
    """EXT-1。Metavision SDK が書き出した HDF5（/CD/events）を再生する。
    MVP では open() が NotImplementedError を投げる骨組みのみ。

    重要な制約（§7.3 参照）: Metavision の HDF5 は ECF コーデックで圧縮されており、
    素の h5py では読めない。open() は h5py で開けなかった場合に、
    変換ツールの使用を促す明確なメッセージを付けて SourceOpenError を投げること。
    """
```

### 7.2 ファクトリ

```python
# input/factory.py
def create_event_source(config: InputConfig, sensor: SensorConfig) -> EventSource:
    """config.source (SourceKind) に応じた EventSource を生成する。
    Raises: ConfigError（未対応の SourceKind、必須項目欠落）"""

SOURCE_REGISTRY: dict[SourceKind, Callable[[InputConfig, SensorConfig], EventSource]]
```

```python
class SourceKind(str, Enum):
    AUTO       = "auto"        # 版2.0 の既定。metavision -> dummy の順に試す
    METAVISION = "metavision"  # 版2.0。Raspberry Pi のライブ入力
    DUMMY      = "dummy"
    FILE       = "file"
    HDF5       = "hdf5"        # EXT-1
```

`websocket` / `tcp` / `http` は削除する。`udp` は §7.5 の同一 LAN 生イベント転送に限り、
PC 側の受信 `EventSource` として追加する。

未実装の `SourceKind` を指定した場合、`create_event_source` は `ConfigError` を投げる。

### 7.4 `source: auto` の解決（Pi と Windows を同じ設定で動かす仕組み）

**これが版 2.0 の要。** 同じ `config/default.yaml` で Pi でも Windows でも起動できるようにする。

```python
def resolve_source_kind(configured: SourceKind) -> tuple[SourceKind, str]:
    """AUTO を実際に使えるソースへ解決する。

    Returns: (実際に使う SourceKind, UI に出す理由の説明)
    AUTO 以外はそのまま返す（明示指定を尊重し、勝手に差し替えない）。
    """
```

`AUTO` の解決順序:

| 順 | 試すもの | 判定方法 |
|:--:|---------|---------|
| 1 | `METAVISION` | `importlib.util.find_spec("metavision_core")` が None でないこと |
| 2 | `DUMMY` | 常に成功 |

- 判定に**実際の import を使わない**（`find_spec` のみ）。import は `open()` の中で遅延実行する。
  こうしないと Windows で起動時に例外が出る。
- 解決結果は `PipelineStats.source_name` と詳細画面に表示する。
  例: `metavision(live)` / `dummy(demo) — metavision_core が見つかりません`。
- **Windows で開発しているとき、自動的にダミーになる**ので、設定を書き換えずに UI を確認できる。
- Pi 上で意図せずダミーになっていないか判別できるよう、ウィジェットのツールチップにも入力ソース名を出す。

### 7.5 同一 LAN UDP 生イベント転送

Pi は `MetavisionEventSource` から得た `EventBatch` を通常どおり処理し、送信が明示的に
有効な場合だけ `UdpEventSender.send(batch)` へ複製する。PC は `input.source: udp` で
`UdpEventSource` を選び、再構成した `EventBatch` を既存パイプラインへ渡す。

実装ファイル:

- `src/deskmate/network/udp_protocol.py`: wire dtype、header、分割・再構成
- `src/deskmate/network/udp_sender.py`: `UdpEventSender`
- `src/deskmate/input/udp_source.py`: `EventSource` 実装

header は network byte order の `!4sBBHIIHHqq` とする。magic=`DMEV`、version=1、
stream_id、batch_seq、fragment_index、fragment_count、t_start_us、t_end_us を持つ。
payload は 1 event 13 byte の `x: >u2, y: >u2, t: >i8, p: i1`。datagram は
`udp.output.max_datagram_bytes`（既定 1200）以下に分割する。空 batch は header のみ送る。

`UdpReassembler` は `(sender address, stream_id, batch_seq)` ごとに fragment を保持し、
全 fragment が揃った場合だけ時刻順を検証して immutable `EventBatch` を返す。重複 fragment
は無視し、不整合・上限超過・タイムアウトした batch は全体を破棄する。保持時間は
`input.udp.reassembly_timeout_ms`、イベント上限は `input.udp.max_batch_events`、未完成 batch
の保持上限は `input.udp.max_pending_batches` とする。

設定:

```yaml
input:
  source: auto
  udp: {bind_host: "0.0.0.0", allowed_host: "127.0.0.1", port: 5005, reassembly_timeout_ms: 500, max_batch_events: 200000, max_pending_batches: 64}
udp:
  output:
    enabled: false
    destination_host: "127.0.0.1"
    destination_port: 5005
    max_datagram_bytes: 1200
    stream_id: 1
privacy:
  allow_external_send: false
```

送信先は数値 IPv4 の private/loopback unicast のみ。`PrivacyGuard.assert_can_send_external()`
が二重許可と宛先を検証する。送信エラーは座標を含めずログに残し、推定処理は継続する。
UDP は暗号化・認証・再送を提供しないため、信頼できる同一 LAN 専用とする。

### 7.3 実機データを Windows で読むための経路（重要）

参照リポジトリ `EVENT_CAMERA` と Metavision SDK 公式ドキュメントの確認により、
次の 2 つの制約が判明した。**これは設計上の前提であり、回避できない。**

| # | 制約 | 出典 |
|---|------|------|
| C-1 | `metavision_core` / OpenEB は **Linux 専用**。Windows では WSL2 Ubuntu 上でしか動かない | `EVENT_CAMERA/WSL2(Ubuntu).md`（Ubuntu へ `metavision-openeb` を apt install する手順） |
| C-2 | Metavision の HDF5 は **ECF（Event Compression Format）コーデック**で圧縮されている。素の h5py では読めず、`hdf5_ecf` フィルタプラグインと `HDF5_PLUGIN_PATH` の設定が必要。公式も「性能が落ちるので試作用途に限る」としている | Metavision SDK Docs「HDF5 Event File Format」 |

DeskMate は **Windows ネイティブの PySide6 アプリ**である。したがって:

**DeskMate 本体は `metavision_core` に依存しない。ECF プラグインにも依存しない。**

実機データを扱う経路は次のとおりとする。

```
[Raspberry Pi 5 + GenX320]
   metavision_viewer -o rec.raw
        │
        ▼  （Pi または WSL2 Ubuntu 上。Metavision SDK が動く環境）
   metavision_file_to_hdf5 -i rec.raw -o rec.hdf5
        │
        ▼  ★ ここで素の形式へ変換する（tools/convert_events.py。WSL2 側で実行）
   rec.npz   ... EVENT_DTYPE の構造化配列 1 本
        │
        ▼  Windows へコピー（scp / エクスプローラ）
[DeskMate on Windows]  FileEventSource が .npz を読む
```

`tools/convert_events.py`（EXT-1 で作成。**MVP では作らない**）の仕様:

```python
"""Metavision HDF5 / RAW を DeskMate の .npz へ変換する。
metavision_core が使える環境（WSL2 Ubuntu / Raspberry Pi）で実行すること。
Windows では動かない。DeskMate 本体はこのスクリプトに依存しない。

使い方:
    python tools/convert_events.py -i rec.hdf5 -o rec.npz [--start 5.0] [--duration 30.0]

出力: np.savez_compressed(out, events=<EVENT_DTYPE の構造化配列>,
                          width=<int>, height=<int>)
"""
```

MVP のテストは `DummyEventSource` と、`.npz` / `.jsonl` を読む `FileEventSource` で完結する。
`Hdf5EventSource`（EXT-1）は「ECF プラグインが導入済みの環境」でのみ動く補助経路と位置づけ、
利用できない場合は上記の変換経路を案内するエラーメッセージを出す。

---

## 8. 時間窓処理

`src/deskmate/pipeline/windower.py`

```python
class EventWindower:
    """センサ時刻 t を基準に、固定長の時間窓へ切り出す。

    - 最初のイベントの t を原点 t0 とし、窓 k は [t0 + k*stride, t0 + k*stride + window] とする。
    - stride < window のときは重複窓（スライディング）になる。既定は stride == window（タンブリング）。
    - バッチ境界をまたぐイベントは内部バッファに保持し、窓が閉じられるまで出力しない。
    - 入力が途切れた場合、flush_idle() を呼ぶと「イベント 0 件の窓」を生成できる。
      これにより、動きがない間も窓が刻まれ、idle_seconds が進む。
    """

    def __init__(self, window_ms: int, stride_ms: int, max_events_per_window: int) -> None:
        """Raises: ConfigError（window_ms が 50–2000 の範囲外、stride_ms > window_ms、
        stride_ms <= 0）"""

    def push(self, batch: EventBatch) -> list[EventWindow]:
        """バッチを取り込み、確定した窓をすべて返す（0 件以上）。
        Raises: PipelineError（t が後退した = センサ時刻の巻き戻り）
                → 呼び出し側は reset() して継続する。"""

    def flush_idle(self, now_sensor_us: int) -> list[EventWindow]:
        """now_sensor_us までの区間について、未確定の窓を空窓として確定させる。
        入力途絶時に AcquisitionThread の推定時刻（受信間隔から外挿）で呼ぶ。"""

    def reset(self) -> None:
        """内部バッファと窓カウンタを初期化する。"""

    @property
    def window_index(self) -> int: ...
    @property
    def buffered_events(self) -> int: ...
```

`max_events_per_window` を超えた窓は、**先頭から等間隔に間引いて**上限件数にし、`truncated=True` を立てる。
`event_count` は間引き前の実数を保持する（活動量の指標を壊さないため）。

---

## 9. 領域と特徴量抽出

### 9.1 領域

```python
# pipeline/regions.py
@dataclass(frozen=True, slots=True)
class RegionRect:
    region_id: RegionId
    x0: float; y0: float; x1: float; y1: float   # 0.0–1.0 正規化

class RegionMap:
    """正規化矩形を px 矩形へ展開し、イベント座標を領域 ID へ割り当てる。"""

    def __init__(self, rects: list[RegionRect], width: int, height: int) -> None:
        """Raises: ConfigError（矩形が [0,1] を外れる、x0>=x1、y0>=y1、region_id 重複、
        RegionId.OTHER を明示指定）"""

    def assign(self, x: np.ndarray, y: np.ndarray) -> np.ndarray:
        """Returns: shape (n,) の int8 配列。値は REGION_ORDER のインデックス。
        どの矩形にも入らないものは OTHER のインデックス。
        実装: 事前計算した (height, width) の int8 ルックアップテーブルを引くだけ。"""

    @property
    def lookup_table(self) -> np.ndarray: ...   # shape (height, width), int8

REGION_ORDER: tuple[RegionId, ...] = (
    RegionId.KEYBOARD, RegionId.MOUSE, RegionId.CENTER,
    RegionId.LEFT, RegionId.RIGHT, RegionId.OTHER,
)
```

ルックアップテーブルは初期化時に 1 回だけ構築する（320×320 = 102,400 バイト）。
矩形の**優先順位は設定の並び順**で、先に書かれたものが勝つ。

### 9.2 特徴量抽出

```python
# pipeline/features.py
class FeatureExtractor:
    def __init__(self, config: FeatureConfig, sensor: SensorConfig,
                 region_map: RegionMap) -> None: ...

    def extract(self, window: EventWindow) -> FeatureFrame:
        """[status-definition.md] §4.2–4.3 のとおり算出する。
        - 内部で直前窓の centroid / event_count / event_rate を保持し、差分系を算出する。
        - idle_seconds / active_seconds もここで更新する。
        - すべて numpy のベクトル演算で行い、Python ループを使わないこと。
        Raises: PipelineError（sensor 範囲外の座標が含まれる）"""

    def reset(self) -> None: ...

    @property
    def last_frame(self) -> FeatureFrame | None: ...
```

実装上の注意（性能要件 NFR-1 を満たすため）:

- グリッド集計は `np.bincount(row * grid_cols + col, minlength=cells)` を使う。
- 領域別集計も `np.bincount(region_index, minlength=6)` を使う。
- 重心は `np.mean` を 1 回だけ呼ぶ。領域別重心は `np.bincount(..., weights=x)` で一括算出する。
- パーセンタイルは `np.percentile(x, [2, 98])` を x, y それぞれ 1 回ずつ。

### 9.3 Voxel（EXT-5、既定 OFF）

参照リポジトリ `EVENT_CAMERA/minimal_voxel_analysis.py` の数式に一致させる。
数式と相違点は [status-definition.md](status-definition.md) §4.6 に定義済み。
**参照リポジトリのコードをコピーせず、数式に基づいて独立に実装すること**（同リポジトリは読み取りのみ）。

```python
# pipeline/voxel.py
def events_to_voxel_grid(x: np.ndarray, y: np.ndarray, t: np.ndarray, p: np.ndarray,
                         num_bins: int, height: int, width: int) -> np.ndarray:
    """Bilinear temporal interpolation による Voxel Grid 変換。

    t* = (num_bins - 1) * (t - t0) / (tN - t0)
    pol = p * 2 - 1                     （0/1 → -1/+1）
    w(b) = max(0, 1 - |b - t*|)
    V[b, y, x] = Σ pol * w(b)

    実装: np.add.at ではなく np.bincount(y*width + x, weights=..., minlength=h*w)
          を各ビンで呼び、reshape する（数値結果は同一、速度は 10 倍以上）。
    Returns: shape (num_bins, height, width) の float32。
    イベント 0 件、または t0 == tN のときはゼロ配列を返す。
    """

def compute_diff_voxels(voxel: np.ndarray) -> np.ndarray:
    """ΔV[b] = V[b+1] - V[b]。Returns: shape (num_bins - 1, height, width)。"""

def compute_centroid_trajectory(diff_voxels: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """各差分ステップの重心を 0.0–1.0 の正規化座標で返す。
    cy[b] = Σ|ΔV[b]| * y / (Σ|ΔV[b]| + 1e-9) / height
    cx[b] = Σ|ΔV[b]| * x / (Σ|ΔV[b]| + 1e-9) / width
    Returns: (cx_seq, cy_seq)。どちらも shape (num_bins - 1,) の float32。
    ★ 戻り値の順序は (cx, cy) である。参照実装の compute_centroid_trajectories() は
      (cy, cx) の順で返すので、移植時に取り違えないこと。
    """

def voxel_features(window: EventWindow, config: VoxelConfig,
                   sensor: SensorConfig) -> VoxelFeatures:
    """上記を束ねて VoxelFeatures を作る。
    spatial_scale > 1 のときは x, y を // spatial_scale してから変換する。
    diff_l1        = mean over b of mean(|ΔV[b]|)
    diff_energy    = sum over b of sum(ΔV[b] ** 2)
    diff_centroid_x / y = 最終ステップの cx / cy（正規化 0–1）
    diff_centroid_shift = Σ hypot(cx[b+1]-cx[b], cy[b+1]-cy[b])
    num_bins < 2 のときは全項目 0.0 を返す。
    """
```

`VoxelFeatures` の定義は §6.2 を、`VoxelConfig`（`enabled` / `time_bins` / `spatial_scale`）は
§15 を参照。

### 9.4 履歴

```python
# pipeline/history.py
class FeatureHistory:
    def __init__(self, config: FeatureConfig, estimation: EstimationConfig,
                 sensor: SensorConfig) -> None: ...

    def update(self, frame: FeatureFrame) -> SmoothedFeatures:
        """EMA・変動係数・change_score を更新して返す。"""

    def reset(self) -> None: ...

    def rate_series(self, seconds: float) -> np.ndarray:
        """直近 seconds 秒の event_rate_eps 系列（詳細画面のグラフ用、float32）。"""

    @property
    def is_warm(self) -> bool:
        """elapsed_seconds >= estimation.warmup_seconds"""
```

EMA 係数は `alpha = 1 - exp(-duration_s / tau)`。窓長が変わっても時定数が保たれる。

---

## 10. 状態推定

```python
# pipeline/estimator.py
class StatusEstimator(abc.ABC):
    @abc.abstractmethod
    def estimate(self, frame: FeatureFrame, smoothed: SmoothedFeatures) -> StatusEstimate: ...

    @abc.abstractmethod
    def reset(self) -> None: ...

    @property
    def name(self) -> str: ...

def create_estimator(config: EstimationConfig) -> StatusEstimator:
    """config.estimator ('rule' | 'ml') に応じて生成する。
    Raises: ConfigError"""
```

```python
# pipeline/rule_estimator.py
class RuleStatusEstimator(StatusEstimator):
    """[status-definition.md] §5 の評価順序・閾値・信頼度式をそのまま実装する。
    メソッドはルール 1 つにつき 1 つ用意し、順に呼ぶ。"""

    def __init__(self, config: EstimationConfig) -> None: ...

    def estimate(self, frame: FeatureFrame, smoothed: SmoothedFeatures) -> StatusEstimate: ...

    # 各ルール: 条件を満たせば StatusEstimate、満たさなければ None
    def _rule_away(self, s: SmoothedFeatures) -> StatusEstimate | None: ...
    def _rule_focused(self, s: SmoothedFeatures) -> StatusEstimate | None: ...
    # idle は必ず成立するフォールバックなので、判定メソッドを持たない

    def _focus_share(self, s: SmoothedFeatures) -> float: ...
    def _apply_noise_penalty(self, estimate: StatusEstimate,
                             s: SmoothedFeatures) -> StatusEstimate: ...

def margin_confidence(value: float, threshold: float, span: float) -> float:
    """[status-definition.md] §5.3 の _margin_conf。モジュール関数として公開しテストする。"""
```

```python
# pipeline/ml_estimator.py  （EXT-6・骨組みのみ）
class MlStatusEstimator(StatusEstimator):
    """RandomForest 等への差し替え口。特徴量 → 状態の写像だけを置き換え、
    平滑化・継続時間・共有ロジックは共通のまま使う。"""
    def __init__(self, model_path: Path, config: EstimationConfig) -> None: ...
    def load(self) -> None:
        raise NotImplementedError("EXT-6")
    @staticmethod
    def feature_vector(frame: FeatureFrame, smoothed: SmoothedFeatures) -> np.ndarray:
        """学習・推論で共通の特徴ベクトル化。MVP でもこの関数だけは実装し、
        後の学習データ収集に使えるようにする。順序は FEATURE_NAMES で固定。"""

FEATURE_NAMES: tuple[str, ...]   # 特徴ベクトルの列名。順序を変えてはならない
```

---

## 11. 平滑化・継続時間・休憩促し

```python
# pipeline/smoother.py
@dataclass(frozen=True, slots=True)
class SmoothingResult:
    status: DeskStatus
    changed: bool
    confidence: float          # 表示用（EMA 後）
    vote_count: int
    candidate: DeskStatus      # 平滑化前の候補（詳細画面で対比表示）

class StatusSmoother:
    """[status-definition.md] §6 のアルゴリズムを実装する。"""

    def __init__(self, config: SmoothingConfig, clock: Clock) -> None: ...

    def update(self, estimate: StatusEstimate, now: float,
               force_away: bool = False) -> SmoothingResult:
        """now は time.monotonic() の値。
        force_away=True のとき [status-definition.md] §7.2-5 の即時遷移を行う。"""

    def reset(self, status: DeskStatus = DeskStatus.UNKNOWN) -> None: ...

    @property
    def current(self) -> DeskStatus: ...

    @staticmethod
    def is_transition_allowed(src: DeskStatus, dst: DeskStatus) -> bool:
        """§6.3 の遷移表。"""

TRANSITION_TABLE: dict[DeskStatus, frozenset[DeskStatus]]
```

```python
# pipeline/duration.py
class DurationTracker:
    def __init__(self, history_limit: int = 200) -> None: ...
    def update(self, status: DeskStatus, changed: bool, confidence: float,
               now: float) -> float:
        """Returns: 現在状態の継続秒数。changed=True なら 0 から数え直す。"""
    @property
    def current_duration(self) -> float: ...
    @property
    def history(self) -> list[HistoryEntry]:
        """新しい順ではなく、古い順（started_monotonic 昇順）で返す。"""
    def recent(self, seconds: float, now: float) -> list[HistoryEntry]: ...
    def reset(self) -> None: ...
```

```python
# pipeline/break_tracker.py
@dataclass(frozen=True, slots=True)
class BreakState:
    """Break-prompt state. Independent of DeskStatus."""
    focus_streak_seconds: float
    break_due: bool
    snoozed_until: float | None


class BreakTracker:
    """[status-definition.md] §3 の休憩促しを実装する。特徴量には触れない。"""

    def __init__(self, config: BreakConfig, clock: Clock) -> None: ...

    def update(self, status: DeskStatus, system_status: SystemStatus,
               window_seconds: float, now: float) -> BreakState:
        """1 窓ごとに呼ぶ。連続集中を数え、25 分で break_due を立てる。"""

    def snooze(self, now: float) -> None:
        """「あとで」。snooze_seconds 後に再提示する。"""

    def acknowledge(self, now: float) -> None:
        """「休憩する」。連続集中を 0 に戻す。"""

    def reset(self) -> None: ...

    @property
    def state(self) -> BreakState: ...
```

---

## 12. パイプライン実行と UI 間通信

### 12.1 通信方式（確定）

**同一プロセス内の Qt シグナル / スロット（`Qt.QueuedConnection`）を使う。**
HTTP / WebSocket / ソケット / 共有メモリは使わない。理由は §1.3。

- パイプライン → UI: シグナルで `StatusSnapshot` / `DetailFrame` / `PipelineStats` を渡す。
  受け渡すオブジェクトは**すべて immutable かコピー済み**。UI 側で書き換えない。
- UI → パイプライン: `UiBridge` のメソッド呼び出しが `QMetaObject.invokeMethod`（Queued）で
  パイプラインスレッドのスロットに届く。UI から直接パイプラインの属性を読み書きしない。

### 12.2 PipelineRunner

```python
# pipeline/runner.py
class PipelineRunner(QObject):
    """パイプラインスレッドで動く本体。QThread へ moveToThread して使う。"""

    # ---- シグナル（すべて UI スレッドへ Queued 接続する）----
    snapshot_ready   = Signal(object)   # StatusSnapshot（毎窓）
    status_changed   = Signal(object)   # StatusSnapshot（確定状態が変わった時のみ）
    detail_ready     = Signal(object)   # DetailFrame（詳細購読中のみ）
    stats_updated    = Signal(object)   # PipelineStats（1 秒ごと）
    source_state     = Signal(str, str) # (SourceStatus.value, 人間可読メッセージ)
    error_occurred   = Signal(str, str) # (エラー種別, メッセージ)

    def __init__(self, config: AppConfig, clock: Clock | None = None) -> None: ...

    # ---- スロット（UI スレッドから呼ばれる）----
    @Slot()
    def start(self) -> None:
        """入力ソースを生成・オープンし、取得ループを開始する。"""

    @Slot()
    def stop(self) -> None:
        """ループを停止し、ソースを close する。冪等。"""

    @Slot(bool)
    def set_paused(self, paused: bool) -> None:
        """推定の一時停止 / 再開。SystemStatus.PAUSED を発火する。"""

    @Slot(bool)
    def set_detail_subscription(self, enabled: bool) -> None:
        """詳細画面の開閉に応じて DetailFrame の生成を ON/OFF する。既定 False。"""

    @Slot(str)
    def set_scenario(self, scenario_id: str) -> None:
        """デバッグモード: ダミーソースのシナリオを切り替える。
        ダミー以外のソースでは何もしない。"""

    @Slot(str)
    def force_status(self, status_value: str) -> None:
        """デバッグモード: 推定を無視して状態を固定する。
        status_value == "" で解除。debug.enabled が False のときは無視する。"""

    @Slot()
    def request_reconnect(self) -> None: ...

    # ---- 内部 ----
    def _loop(self) -> None:
        """取得 → 窓化 → 特徴量 → 推定 → 平滑化 → 発火 の 1 ループ。
        QTimer(0) の連続呼び出しではなく、専用スレッドの while ループで回す。"""
    def _process_window(self, window: EventWindow) -> None: ...
    def _build_snapshot(self, ...) -> StatusSnapshot: ...
    def _build_detail_frame(self, ...) -> DetailFrame: ...
    def _handle_source_error(self, exc: Exception) -> None: ...
```

ループの周期制御:

- `EventSource.read(timeout_s=config.input.poll_timeout_ms/1000)` でブロックする。
- `None` が返り続けて `input.stall_timeout_ms`（既定 1500）を超えたら `SourceStatus.STALLED` を発火し、
  `EventWindower.flush_idle()` で空窓を刻み続ける（＝ `away` に向かう）。
- `input.disconnect_timeout_ms`（既定 5000）を超えたら `SystemStatus.NO_SIGNAL`。
  以後 `input.reconnect_interval_ms`（既定 3000）ごとに `reset()` → `open()` を試みる。

### 12.3 UiBridge

```python
# ui/bridge.py
class UiBridge(QObject):
    """UI 側の唯一の窓口。3 ウィンドウはこのオブジェクトだけを見る。"""

    snapshot_updated = Signal(object)   # StatusSnapshot
    status_changed   = Signal(object)   # StatusSnapshot
    detail_updated   = Signal(object)   # DetailFrame
    stats_updated    = Signal(object)   # PipelineStats
    notice_changed   = Signal(str)      # 画面上部に出す通知文（空文字で消去）

    def __init__(self, runner: PipelineRunner, config: AppConfig) -> None: ...

    # UI からの操作（内部で invokeMethod による Queued 呼び出しに変換する）
    def set_paused(self, paused: bool) -> None: ...
    def snooze_break(self) -> None: ...        # 版2.0
    def acknowledge_break(self) -> None: ...   # 版2.0
    def open_detail(self) -> None: ...      # detail 購読 ON
    def close_detail(self) -> None: ...     # detail 購読 OFF
    def set_scenario(self, scenario_id: str) -> None: ...
    def force_status(self, status: DeskStatus | None) -> None: ...

    @property
    def last_snapshot(self) -> StatusSnapshot | None: ...
```

版 2.0 では共有画面が無いため `set_sharing_enabled()` / `sharing_enabled` は削除する。

---

## 13. キャラクター表示

**版 2.0 でドット絵 GIF に変更した。** 素材は作成済みで `assets/character/` にある。

```python
# character/mapping.py
def resolve_animation(status: DeskStatus, break_due: bool,
                      system_status: SystemStatus = SystemStatus.RUNNING) -> AnimationId:
    """[status-definition.md] §4.2 の 5 段の順序で判定する。

    1. system_status != RUNNING          -> SITTING
    2. break_due                         -> BREAK
    3. status == AWAY                    -> SLEEPING
    4. status == FOCUSED                 -> RUNNING
    5. status == IDLE                    -> SITTING

    版 1.0 の ANIMATION_RULES / SYSTEM_ANIMATION / 継続時間による分岐は廃止。
    """
```

```python
# character/renderer.py
class CharacterRenderer(abc.ABC):
    """キャラクター描画の差し替え口。"""

    @abc.abstractmethod
    def set_animation(self, animation: AnimationId) -> None:
        """表示するアニメーションを切り替える。同じ値なら何もしない
        （GIF の再生位置をリセットしないため）。"""

    @abc.abstractmethod
    def widget(self) -> QWidget:
        """描画ウィジェットを返す。"""


class GifCharacterRenderer(CharacterRenderer):
    """版 2.0 の既定実装。QMovie で 30x30 の GIF を再生する。

    - `assets/character/<animation_id>.gif` を起動時にすべて QMovie として読み込み、
      切り替え時は再生対象を差し替えるだけにする（毎回ロードしない）
    - **拡大は最近傍補間・整数倍のみ**。
      `movie.setScaledSize(QSize(30 * scale, 30 * scale))` ではなく、
      各フレームを `QPixmap.scaled(..., Qt.TransformationMode.FastTransformation)` で
      拡大してから QLabel に渡す（QMovie の既定は滑らかな補間になりうるため）
    - `scale` は `character.scale`（既定 4 -> 120px）
    - 素材が欠けている AnimationId があれば ConfigError を投げる（黙って落とさない）
    - 背景は透過のまま扱う

    Raises: ConfigError（assets_dir に必要な 4 つの GIF が揃っていない）
    """
    def __init__(self, config: CharacterConfig) -> None: ...


class ShapeCharacterRenderer(CharacterRenderer):
    """素材が無い環境のための保険。単色の円と状態名の頭文字だけを描く。
    既定では使わない（`character.renderer: gif`）。"""


def create_renderer(config: CharacterConfig) -> CharacterRenderer:
    """config.character.renderer ('gif' | 'shape') で選ぶ。既定 'gif'。"""
```

**版 1.0 の `ImageCharacterRenderer` は削除する。** `GifCharacterRenderer` が置き換える。

```python
# ui/character_view.py
class CharacterView(QWidget):
    """CharacterRenderer を載せる描画ウィジェット。
    - 20 fps の QTimer で advance() → update()
    - 状態変化時は 350ms のクロスフェード + 4px バウンス（QPropertyAnimation）
    - サイズは常駐 64px / 共有 96px / 詳細 96px（設定で変更可）"""
    def __init__(self, renderer: CharacterRenderer, size: int, parent=None) -> None: ...
    def apply_snapshot(self, snapshot: StatusSnapshot) -> None: ...
    def set_renderer(self, renderer: CharacterRenderer) -> None: ...
```

---

## 14. UI 詳細

### 14.1 常駐ウィジェット `ui/widget_window.py`

```python
class WidgetWindow(QWidget):
    """枠なし・最前面・ドラッグ移動可能な常駐ウィジェット。
    Window flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
    Attributes: Qt.WA_TranslucentBackground
    既定サイズ: 460 x 250 px（ui.widget.width / height）
    最小化時: 96 x 96 px（ui.widget.minimized_size）。キャラクターのみ
    """
    def __init__(self, bridge: UiBridge, config: AppConfig) -> None: ...
    def apply_snapshot(self, snapshot: StatusSnapshot) -> None: ...
    def toggle_minimized(self) -> None:
        """最小化時は 64x64 のキャラクターのみになる。"""
    def restore_position(self) -> None:
        """前回位置（ui.widget.last_position）を復元。画面外なら右下へ。"""
    # マウス操作
    def mousePressEvent / mouseMoveEvent / mouseReleaseEvent   # ドラッグ移動
    def contextMenuEvent    # 右クリックメニュー（詳細/共有/停止/設定/終了）
```

レイアウト（3 段構成、外周マージン 16/12px）:

```
┌────────────────────────────────────────────────────┐
│ ● DeskMate                     [⋯] [⧉] [‖]         │ ヘッダ（24px）
│                                                    │
│   ╭──────────╮   集中傾向                           │ 本体
│   │  キャラ   │   5分12秒                            │
│   │  132px   │   信頼度 ▓▓▓▓▓▓▓░░░  78%            │
│   ╰──────────╯                                     │
│ ──────────────────────────────────────────────────  │ 区切り線
│ ▓▓▓▓▒▒▒▒████░░░░                                   │ 状態履歴ストライプ（10px）
│ RGB映像は使用していません / UDP送信は設定で管理されています │ プライバシー注記（10px）
└────────────────────────────────────────────────────┘
```

| 要素 | 内容 | 設定キー |
|------|------|---------|
| 状態ドット | 現在状態の色（[status-definition.md](status-definition.md) §7.3） | – |
| タイトル | `WINDOW_TITLE_JA`（11px、`muted` 色） | – |
| 詳細ボタン | `⋯`（`GLYPH_DETAIL`） | – |
| 共有ボタン | `⧉`（`GLYPH_SHARE`） | – |
| 停止 / 再開ボタン | `‖` / `►`（`GLYPH_PAUSE` / `GLYPH_RESUME`） | – |
| キャラクター | `CharacterView`（132px）。状態色のハロー付き | `ui.widget.character_size` |
| 状態ラベル | `STATUS_LABELS_SHORT_JA` を `resolve_label(short=True)` 経由で（21px 太字） | – |
| 継続時間 | `format_duration()`（15px、等幅ヒント）。1 秒ごとに更新 | – |
| 信頼度 | ラベル + 状態色のバー（高さ 8px）+ パーセント数値 | `ui.widget.show_confidence` |
| 状態履歴ストライプ | `StatusStripe`（高さ 10px）。直近 `ui.detail.history_seconds` 秒 | `ui.widget.show_history` |
| プライバシー注記 | `PRIVACY_NOTICE_JA`（10px、`muted` 色） | `ui.widget.show_privacy_notice` |
| 共有停止表示 | 共有 OFF のときヘッダに「共有停止中」 | – |

**ボタンのグリフは必ず text presentation の文字を使う。**
`⏸`(U+23F8) や `▶`(U+25B6) は絵文字表示を持つため、絵文字フォントにフォールバックして
フルカラーで描画されてしまう。ボタンには明示的に `Segoe UI` を設定する。

要件: 常に最前面 / 画面の邪魔になりにくい（半透明 0.96、クリックスルーはしない） /
移動できる（ドラッグ）/ ダブルクリックで最小化 / 状態変化時だけ遷移アニメーション。

**`StatusStripe` のプライバシー上の位置づけ**: 自前で `StatusSnapshot` を蓄積して描画する。
`DetailFrame`・特徴量・座標には一切触れないため、L3（抽象状態）のみで成立し、
詳細購読を有効にする必要がない（[privacy-design.md](privacy-design.md) §2 / PV-6）。
`tests/test_widget_ui.py` で AST を走査して検証する。

### 14.2 詳細画面 `ui/detail_window.py`

`QMainWindow`、既定 1200×800。開いたとき `bridge.open_detail()`、閉じたとき `bridge.close_detail()`。

レイアウト（3 列 × 3 行のグリッド）:

| # | パネル | クラス | 表示内容 |
|---|-------|-------|---------|
| 1 | 点群 | `EventScatterPanel` | 間引き点群（正極性 / 負極性で色分け）、領域矩形の重ね描き |
| 2 | 時間窓 | `EventScatterPanel` 内の見出し | 窓番号・窓長・窓内イベント数・`truncated` 表示 |
| 3 | 動きの範囲 | `MotionPanel` | bbox 矩形、幅・高さ・面積比 |
| 4 | 重心 | `MotionPanel` | 重心マーカーと直近 20 窓の軌跡 |
| 5 | 変化量 | `MotionPanel` | `centroid_speed`・`event_rate_delta`・`change_score` の数値とバー |
| 6 | 領域別活動量 | `RegionPanel` | 6 領域の横棒グラフ（share と eps）+ グリッドヒートマップ |
| 7 | 特徴量 | `FeatureTablePanel` | `FeatureFrame.to_display_dict()` の全項目をテーブル表示 |
| 8 | 現在の状態 | `StatusHeader`（`detail_window.py` 内） | 状態名・信頼度・継続時間・適用ルール ID・reason・候補状態 |
| 9 | キャラクター | `CharacterView`（96px） | 現在のアニメーション |
| 10 | 状態履歴 | `HistoryPanel` | 直近 5 分の帯グラフ + 活動量の折れ線 |

画面上部に固定表示（`ui/labels.py` の定数）:

- `PRIVACY_NOTICE_JA`（RGB 未使用 / UDP 送信は設定で管理）
- `PRIVACY_CAVEAT_JA`（形状が推測されうる旨）
- 現在の入力ソース名と `SourceStatus`、`PipelineStats`（処理時間・破棄バッチ数）

デバッグ操作（`debug.enabled: true` のときだけ表示）:

- シナリオ選択コンボボックス（8 シナリオ）
- 状態固定ボタン（7 状態 + 解除）
- 「特徴量を CSV に保存」ボタン（`PrivacyGuard` の許可が必要）

### 14.3 休憩促しバナー `ui/break_banner.py`

**版 2.0 で共有画面を廃止し、代わりにこのバナーを追加する。**
共有機能は将来の展望として設計から外す（[requirements.md](requirements.md) §10 EXT-1）。

`break_due` が `True` の間だけ、常駐ウィジェットの本体部分に重ねて表示する小さなバナー。

```
┌────────────────────────────────────┐
│ そろそろ休憩しませんか               │
│ 25分12秒 集中しています              │
│              [あとで]  [休憩する]    │
└────────────────────────────────────┘
```

| 要素 | 内容 |
|------|------|
| 見出し | `BREAK_TITLE_JA`「そろそろ休憩しませんか」 |
| 本文 | `BREAK_BODY_JA` に `format_duration(focus_streak_seconds)` を埋める |
| あとでボタン | `bridge.snooze_break()` → 5 分後に再提示 |
| 休憩するボタン | `bridge.acknowledge_break()` → 連続集中をリセット |
| 配色 | `#E8A33D`（橙）の枠。背景は `theme.surface_alt` |

同時にキャラクターが `break.gif` に切り替わる（[status-definition.md](status-definition.md) §4.2）。
**音やポップアップウィンドウは出さない。** 作業の邪魔をしないこと。

### 14.4 トレイ `ui/tray.py`

`QSystemTrayIcon`。メニュー: ウィジェット表示 / 詳細画面 / 推定停止・再開 / 終了。

アイコンは `build_status_icon(status)` で**実行時に生成**する（バイナリ素材を持たない）。
現在状態の `STATUS_COLORS` で塗った円を描き、`snapshot_updated` ごとに更新する。
ツールチップに状態ラベルと継続時間を出す。
シングルクリック / ダブルクリックでウィジェットを再表示する
（ウィジェットを閉じても常駐しているため、ここが唯一の復帰経路になる）。

---

## 15. 設定ファイル

`config/default.yaml`（リポジトリ管理、編集は原則しない）→
`%APPDATA%\DeskMate\config.yaml`（ユーザ設定、存在すれば深いマージで上書き）→
CLI 引数（`--source`, `--config`, `--debug`, `--demo`）の順に優先。

```yaml
version: 1

app:
  locale: ja
  autostart_pipeline: true      # 起動時に推定を開始するか
  fullscreen: false             # Pi の画面いっぱいに出すか

sensor:
  width: 320                    # Prophesee GenX320
  height: 320

input:
  source: auto                  # auto | metavision | dummy | file | hdf5
                                # auto = Pi なら metavision、無ければ dummy
  metavision:
    delta_t_us: 20000           # 1 バッチが表す時間 (20ms)
    input_path: ""              # "" = 接続中の最初のカメラ
  poll_timeout_ms: 50
  stall_timeout_ms: 1500
  disconnect_timeout_ms: 5000
  reconnect_interval_ms: 3000
  max_open_retries: 10
  dummy:
    mode: demo                  # demo（自動遷移）| manual（固定）
    scenario: keyboard_steady   # mode=manual のときのシナリオ ID
    loop: true
    seed: 20260726
    batch_interval_ms: 20       # 1 バッチが表す時間
    rate_scale: 1.0             # 全シナリオの活動量倍率
  file:
    path: null                  # .jsonl または .npz
    speed: 1.0
    loop: true
  hdf5:
    path: null
    events_dataset: /events
    speed: 1.0
    loop: false

pipeline:
  queue_size: 64
  queue_overflow: drop_oldest   # drop_oldest のみ実装

window:
  window_ms: 200                # 100–1000
  stride_ms: 200                # <= window_ms
  max_events_per_window: 200000
  grid_cols: 16
  grid_rows: 16                 # センサが正方（320x320）なので 16x16

regions:
  - {id: keyboard, rect: [0.25, 0.62, 0.75, 1.00]}
  - {id: mouse,    rect: [0.75, 0.60, 1.00, 1.00]}
  - {id: center,   rect: [0.30, 0.25, 0.70, 0.62]}
  - {id: left,     rect: [0.00, 0.00, 0.30, 0.62]}
  - {id: right,    rect: [0.70, 0.00, 1.00, 0.60]}

features:
  ema_short_seconds: 1.0
  ema_long_seconds: 10.0
  history_seconds: 60.0
  bbox_percentile: 0.05
  voxel:
    enabled: false
    time_bins: 4
    spatial_scale: 4            # 1 で参照実装と同じフル解像度

estimation:
  estimator: rule               # rule | ml
  model_path: null
  warmup_seconds: 3.0
  idle_eps: 100.0
  away_seconds: 30.0
  focus_min_eps: 400.0
  high_activity_eps: 5000.0
  focus_regions: [keyboard, mouse]
  focus_region_share: 0.60
  focus_min_seconds: 5.0
  focus_max_bbox_area_ratio: 0.20
  focus_max_activity_cv: 0.60

break:
  enabled: true
  after_seconds: 1500.0         # 連続集中 25 分
  reset_seconds: 180.0          # 非集中が 3 分続いたらリセット
  snooze_seconds: 300.0         # 「あとで」で 5 分後に再提示
  demo_scale: 1.0               # デモでは 0.02 (25分 -> 30秒)

smoothing:
  vote_window_size: 5
  vote_min_count: 3
  enter_confidence: 0.50
  exit_confidence: 0.35
  confidence_ema_seconds: 2.0
  min_dwell_seconds:
    default: 3.0
    away: 5.0

character:
  renderer: gif                 # gif | shape（shape は素材が無いときの保険）
  assets_dir: assets/character
  scale: 4                      # 30px の整数倍のみ (4 -> 120px)

ui:
  theme: dark                   # dark | light
  widget:
    width: 460
    height: 250
    opacity: 0.96
    show_confidence: true
    show_history: true          # 状態履歴ストライプ
    show_privacy_notice: true   # 下部のプライバシー注記
    character_size: 132
    minimized_size: 96
    last_position: null         # [x, y]。null なら右下
    minimized: false
  detail:
    max_preview_points: 5000
    history_seconds: 300
    refresh_hz: 10
    character_size: 96

privacy:
  save_raw_events: false        # 常に false 起動。true にしても実行時に警告を出す
  save_features: false
  history_retention_minutes: 60
  allow_external_send: false    # MVP では実装が存在しないため常に false
  show_caveat: true

logging:
  level: INFO                   # DEBUG | INFO | WARNING | ERROR
  file_enabled: true
  dir: null                     # null なら %LOCALAPPDATA%\DeskMate\logs
  max_bytes: 1048576
  backup_count: 3
  log_features: false           # true でも DEBUG レベルのときのみ出力

debug:
  enabled: false                # true でデバッグ操作 UI と状態固定を有効化
  force_status: null
```

### 15.1 pydantic スキーマ

```python
# config/schema.py
class SensorConfig(BaseModel):
    width: int = Field(320, ge=64, le=4096)    # GenX320
    height: int = Field(320, ge=64, le=4096)

class WindowConfig(BaseModel):
    window_ms: int = Field(200, ge=100, le=1000)
    stride_ms: int = Field(200, ge=10, le=1000)
    max_events_per_window: int = Field(200_000, ge=1000)
    grid_cols: int = Field(16, ge=2, le=128)
    grid_rows: int = Field(16, ge=2, le=128)

    @model_validator(mode="after")
    def _check_stride(self) -> "WindowConfig":
        if self.stride_ms > self.window_ms:
            raise ValueError("stride_ms must be <= window_ms")
        return self

# 以下同様に:
# AppSectionConfig, InputConfig, DummyInputConfig, FileInputConfig, Hdf5InputConfig,
# PipelineConfig, RegionConfigItem, FeatureConfig, VoxelConfig, EstimationConfig,
# SmoothingConfig, MinDwellConfig, ShareConfig, CharacterConfig, UiConfig,
# WidgetUiConfig, DetailUiConfig, ShareUiConfig, PrivacyConfig, LoggingConfig, DebugConfig

class AppConfig(BaseModel):
    version: int = 1
    app: AppSectionConfig = AppSectionConfig()
    sensor: SensorConfig = SensorConfig()
    input: InputConfig = InputConfig()
    pipeline: PipelineConfig = PipelineConfig()
    window: WindowConfig = WindowConfig()
    regions: list[RegionConfigItem] = Field(default_factory=default_regions)
    features: FeatureConfig = FeatureConfig()
    estimation: EstimationConfig = EstimationConfig()
    smoothing: SmoothingConfig = SmoothingConfig()
    share: ShareConfig = ShareConfig()
    character: CharacterConfig = CharacterConfig()
    ui: UiConfig = UiConfig()
    privacy: PrivacyConfig = PrivacyConfig()
    logging: LoggingConfig = LoggingConfig()
    debug: DebugConfig = DebugConfig()

    model_config = ConfigDict(extra="forbid")   # 未知キーはエラー
```

```python
# config/loader.py
DEFAULT_CONFIG_PATH: Path        # <package_root>/../../config/default.yaml
def user_config_path() -> Path:  # %APPDATA%\DeskMate\config.yaml
def load_config(cli_overrides: dict | None = None,
                config_path: Path | None = None) -> AppConfig:
    """Raises: ConfigError（YAML 構文エラー、バリデーション失敗、必須ファイル欠落）"""
def deep_merge(base: dict, override: dict) -> dict: ...
def write_user_config_template(path: Path | None = None) -> Path: ...
```

**設定変更の反映**: MVP では再起動が必要。ホットリロードは実装しない。
ただし `debug` セクションと `share.enabled` は UI から実行時に変更でき、その値はファイルに書き戻さない。

---

## 16. エラー処理

### 16.1 例外階層

```python
# core/errors.py
class DeskMateError(Exception):
    """全例外の基底。"""

class ConfigError(DeskMateError):
    """設定の読込・検証エラー。起動時に致命。ダイアログを出して既定値で続行するか終了。"""

class SourceError(DeskMateError):
    """入力ソース一般。"""

class SourceOpenError(SourceError):
    """open() に失敗。"""

class SourceDisconnectedError(SourceError):
    """接続が切れた。再接続を試みる。"""

class DecodeError(SourceError):
    """受信データが仕様に合わない。該当バッチのみ破棄。"""

class PipelineError(DeskMateError):
    """窓化・特徴量計算の異常。パイプラインを reset して継続。"""

class PrivacyViolationError(DeskMateError):
    """PrivacyGuard が禁止された操作を検出した。必ず送出し、握り潰さない。"""
```

### 16.2 対応方針

| 発生箇所 | 例外 | 対応 | UI 表示 |
|---------|------|------|--------|
| 設定読込 | `ConfigError` | 起動時: ダイアログで内容表示 → 既定設定で続行するか終了を選ばせる | モーダル |
| ソース生成 | `ConfigError` | `dummy` にフォールバックして続行 | 通知バー「入力ソースを dummy に切り替えました」 |
| `open()` | `SourceOpenError` | `reconnect_interval_ms` ごとに最大 `input.max_open_retries`(既定 10) 回リトライ。超過で `SystemStatus.ERROR` | 「入力を開けません」 |
| `read()` が `None` 継続 | – | `stall_timeout_ms` 超で `STALLED`、`disconnect_timeout_ms` 超で `NO_SIGNAL` | 「入力が途切れています」 |
| `read()` | `SourceDisconnectedError` | ソースを `reset()` して再接続。`NO_SIGNAL` へ | 同上 |
| `read()` | `DecodeError` | そのバッチだけ破棄。1 分あたり 10 件を超えたら WARNING ログ + 通知 | 「一部のデータを読み取れませんでした」 |
| 窓化 / 特徴量 | `PipelineError` | `windower.reset()` + `extractor.reset()` + `history.reset()`、状態は `unknown` | 「処理を再初期化しました」 |
| 予期しない例外 | `Exception` | ループ内で捕捉しログ出力。3 回/分を超えたら停止して `ERROR` | 「エラーが発生しています」 |
| UI スレッド | `Exception` | `sys.excepthook` でログ + ダイアログ。アプリは落とさない | モーダル |

**共通ルール**: どの経路でもアプリを終了させない（`ConfigError` の起動時のみ例外）。
状態が判定できない間は `unknown` / `no_signal` を表示し、決して古い状態を表示し続けない。

### 16.3 入力切断時の挙動（詳細）

1. `read()` が `None` を返し続ける。
2. `stall_timeout_ms`（1500 ms）経過 → `SourceStatus.STALLED` を発火。
   `EventWindower.flush_idle()` で空窓を生成し続ける。特徴量は 0、`idle_seconds` が伸びる。
   → 通常の推定に従い、`away_seconds`（30 秒）後に `away` になる。
3. `disconnect_timeout_ms`（5000 ms）経過 → `SystemStatus.NO_SIGNAL`。
   **ここで空窓の生成を止める**（データが無いのに「動きがない」と主張しないため）。
   UI は「入力が途切れています」を表示する（`SystemStatus.NO_SIGNAL`）。
4. `reconnect_interval_ms`（3000 ms）ごとに `source.reset()` → `source.open()`。
5. 復帰したら `windower.reset()` / `extractor.reset()` / `history.reset()` / `smoother.reset()` を行い、
   `SystemStatus.STARTING` から再度ウォームアップする。

---

## 17. ダミーデータ生成

```python
# input/scenarios.py
@dataclass(frozen=True, slots=True)
class ScenarioSpec:
    scenario_id: str
    label: str                       # 日本語名（デバッグ UI 用）
    base_rate_eps: float             # 平均活動量
    rate_jitter: float               # 0–1。窓ごとの変動幅
    burst_period_s: float | None     # 断続動作の周期。None で連続
    burst_duty: float                # 0–1。バースト中の時間比率
    centers: tuple[tuple[float, float], ...]   # 正規化座標の発生中心（複数可）
    center_switch_s: float           # 中心を切り替える周期
    sigma_px: float                  # 発生位置のガウス分布の標準偏差
    drift_px_per_s: float            # 中心のドリフト速度
    positive_ratio: float            # 正極性の比率
    uniform_noise_ratio: float       # 全面ランダムノイズの比率
    rate_decay_per_s: float          # 1 秒あたりの活動量減衰率（1.0 で減衰なし）
    dropout: bool                    # True なら read() が None を返し続ける

SCENARIOS: dict[str, ScenarioSpec]   # 8 種（demo-scenario.md §1）

@dataclass(frozen=True, slots=True)
class DemoStep:
    scenario_id: str
    duration_s: float

DEMO_SEQUENCE: tuple[DemoStep, ...]  # demo-scenario.md §3 の時系列
```

```python
# input/dummy_source.py
class DummyEventSource(EventSource):
    """ScenarioSpec に従って合成イベントを生成する。

    生成規則（1 バッチ = batch_interval_ms 分）:
      1. 現在シナリオの base_rate_eps に rate_jitter（一様乱数）と rate_decay を適用し、
         このバッチの目標イベント数 n = rate * batch_interval_ms / 1000 を決める。
      2. burst_period_s が None でなければ、位相が burst_duty の外なら n を 0.05 倍にする。
      3. n 件のうち uniform_noise_ratio の割合は画面全体の一様乱数、
         残りは現在の中心 + N(0, sigma_px) のガウス分布で座標を生成する。
      4. 座標を [0, width-1] / [0, height-1] にクリップして uint16 化する。
      5. 極性は positive_ratio のベルヌーイ試行。
      6. 時刻は区間内の一様乱数を昇順ソートしたもの。
      7. dropout が True の場合は read() が None を返す（バッチを作らない）。

    乱数は np.random.default_rng(seed) を使い、seed 固定で再現可能にする。
    実時間との同期: 内部で next_emit_monotonic を持ち、read() は必要なら
    min(timeout_s, 次バッチまでの時間) だけ sleep してから返す。
    """
```

デモモードは `DEMO_SEQUENCE` を順に再生し、末尾に達したら `loop` に従って先頭へ戻る。
デバッグモードは `set_scenario()` で固定する。

---

## 18. ログ設計

```python
# logging_setup.py
def setup_logging(config: LoggingConfig, privacy: PrivacyConfig) -> None:
    """ルートロガーを設定する。
    - コンソール: level に従う
    - ファイル: RotatingFileHandler（max_bytes / backup_count）。file_enabled で切替
    - フォーマット: '%(asctime)s %(levelname)-7s %(name)s: %(message)s'
    - privacy.log_features が False のとき、'deskmate.features' ロガーを WARNING 以上に固定する
    """

def get_logger(name: str) -> logging.Logger: ...
```

ロガー名の規約: `deskmate.<module>`（例 `deskmate.pipeline.runner`）。

| レベル | 出力内容 |
|-------|---------|
| ERROR | 例外、再接続失敗、プライバシー違反検出 |
| WARNING | バッチ破棄、キュー溢れ、デコード失敗、処理時間が窓長を超えた |
| INFO | 起動 / 終了、ソース種別と接続状態、**確定状態の変化**（状態名・継続時間・信頼度のみ） |
| DEBUG | 窓ごとの候補状態・適用ルール ID・平滑化の得票数 |

**ログに書いてはならないもの**: イベント座標、点群、重心座標、領域別の詳細値、
ファイルパス以外の入力データ内容。`log_features: true` かつ `level: DEBUG` のときのみ、
`deskmate.features` ロガーが集約値（eps・比率）を出力してよい。座標は常に禁止。

---

## 19. プライバシー実装ポイント

詳細は [privacy-design.md](privacy-design.md)。実装上の要点のみ。

```python
# privacy/guard.py
class PrivacyGuard:
    """保存・外部送信の可否を一元判定する。保存系の処理は必ずここを通す。"""

    def __init__(self, config: PrivacyConfig) -> None: ...

    def can_save_raw_events(self) -> bool: ...
    def can_save_features(self) -> bool: ...
    def can_send_external(self) -> bool:
        """MVP では常に False を返す。"""

    def assert_can_save_raw_events(self) -> None:
        """Raises: PrivacyViolationError"""
    def assert_no_external_send(self, destination: str) -> None:
        """Raises: PrivacyViolationError"""

    def retention_cutoff(self, now: float) -> float:
        """history_retention_minutes に基づく保持期限（monotonic 秒）。"""

    @property
    def notice_text(self) -> str: ...
    @property
    def caveat_text(self) -> str: ...
```

- `DetailFrame` を生成するのは `set_detail_subscription(True)` の間だけ。
- `StatusSnapshot` に座標・特徴量フィールドを追加してはならない（テストで検証）。
- 状態履歴は `privacy.history_retention_minutes` を超えたエントリを `DurationTracker` が破棄する。

---

## 20. Raspberry Pi から PC への入力差し替え

実装済みの §7.5 を使用する。Pi は Metavision 入力、PC は `UdpEventSource` を選ぶ。
ネットワーク形式を追加する場合も `EventSource` の契約を変えず、UDP 以外は別途プライバシー
レビューを必要とする。WebSocket/JSON の旧案は廃止する。

---

## 21. テスト方針

詳細な項目は [implementation-plan.md](implementation-plan.md) §4。

| 種別 | 対象 | 方針 |
|------|------|------|
| 単体 | `windower` / `features` / `regions` / `history` / `rule_estimator` / `smoother` / `duration` / `break_tracker` / `character.mapping` / `labels` / `config` | 合成イベント列を与え、期待値を厳密比較（float は `pytest.approx`） |
| 単体 | `dummy_source` / `file_source` | seed 固定で再現性を確認。統計量（平均 eps、領域偏り）が仕様どおりか |
| 結合 | `runner` | ダミーソース → 各シナリオを流し、期待する `DeskStatus` に到達することを確認（実時間ではなく `FakeClock` と手動 tick で駆動） |
| 異常系 | `source_failure` | `read()` が `None` / 例外を返すソースを注入し、`NO_SIGNAL` → 復帰を確認 |
| プライバシー | `privacy_guard` | 既定でファイルが生成されないこと、`StatusSnapshot` に座標フィールドが無いこと（`dataclasses.fields` を検査） |
| UI スモーク | `ui_smoke` | pytest-qt で 3 ウィンドウを生成し、`StatusSnapshot` を流して例外なく描画されること。`ShareWindow` が `detail_updated` に接続していないこと |

`FakeClock` は `tests/conftest.py` に置き、`Clock` プロトコルを実装する。
GUI テストは `QT_QPA_PLATFORM=offscreen` で実行する。

---

## 22. 想定される技術的リスク

| # | リスク | 影響 | 対策 |
|---|-------|------|------|
| R1 | **実 GenX320 の活動量スケールが、想定（数百〜数千 eps）と大きく違う。これは現時点で未検証の最大リスク** | 全閾値が無意味になり、`working` か `unknown` に貼り付く | 閾値をすべて設定ファイル化済み。実データ入手後に `estimation.*` のみ調整すれば足りる。`activity` 系は eps という物理量で定義してあり、キャリブレーション用に詳細画面へ実測 eps を常時表示する。§24 の手順で実測してから調整する |
| R2 | 照明のちらつき・モニタのリフレッシュがノイズとして大量に乗る | 常に `idle`（非集中）になり、`focused` が出なくなる | ノイズは空間的に散るため `focus_share` が下がり、安全側の `idle` に落ちる。EXT として「常時発火する画素のマスク」を追加できるよう `RegionMap` に除外矩形の余地を残す（MVP では未実装） |
| R3 | 領域矩形の設定が実機と合わない | `focused` が出ない | 詳細画面に領域矩形を点群へ重ね描きし、目視で調整できるようにする。EXT-3 で GUI エディタ |
| R4 | pyqtgraph の点群描画が UI をブロックする | 詳細画面でカクつく | 描画は最大 5,000 点に間引き、更新は 10 Hz に制限。詳細画面を閉じている間は `DetailFrame` 自体を作らない |
| R5 | 平滑化が強すぎて、デモ中に状態が変わらない | デモが成立しない | `min_dwell_seconds` を設定化。デモ用シナリオの各ステップは最小継続時間の 5 倍以上の長さにする（[demo-scenario.md](demo-scenario.md) §3） |
| R6 | PySide6 の枠なし最前面ウィンドウが、特定の Windows 環境で他の全画面アプリに隠れる | 常駐表示が見えない | トレイアイコンから再表示できるようにする。`WindowStaysOnTopHint` の再適用ボタンを右クリックメニューに置く |
| R7 | センサ時刻 `t` の巻き戻り・飛び | 窓化が壊れる | `EventWindower.push()` で検出し `PipelineError` → reset。飛びは `flush_idle` 相当の空窓で埋める |
| R8 | 状態が `unknown` ばかりになる（閾値が実データに対して厳しい） | デモの説得力が落ちる | `working` を最後の砦にして広めに取る。詳細画面に「どのルールで落ちたか」（最後に評価したルール ID）を表示して調整を容易にする |
| R9 | Raspberry Pi 5 の描画性能が足りず、ウィジェットがカクつく | デモの見栄えが落ちる | GIF は 30×30 の整数倍拡大なので描画負荷はごく小さい。詳細画面の点群描画だけが重いので、既定で閉じておき `ui.detail.refresh_hz` を Pi では 5 に下げられるようにする |
| R10 | `focused` と `working` の境界が実データで曖昧 | 表示が頻繁に揺れる | 遷移表で `focused ↔ working` の相互遷移は許可しつつ、`min_dwell` と多数決で抑える。それでも揺れる場合は `focus_min_seconds` を伸ばす |

---

## 23. 設計上の未確定事項

| # | 未確定事項 | 現時点の暫定 | 決定時期 / 決定者 |
|---|-----------|------------|-----------------|
| Q1 | Raspberry Pi ↔ PC の通信方式 | WebSocket を第一候補として設計。`EventSource` で吸収。Pi 5 は V4L2 経由で GenX320 を扱えることを §24 で確認済み | Pi 側実装着手時（EXT-2） |
| Q2 | ~~実イベントカメラの型番・解像度~~ → **解決**（GenX320 / 320×320） / 平均イベントレートは未確定 | 解像度は 320×320 に確定。eps は §24 の手順で実測して調整する | 実データ取得時。`estimation.*` のみ調整 |
| Q3 | ~~既存 `EVENT_CAMERA` の Voxel 実装~~ → **解決** | 数式を §24 で確認し、[status-definition.md](status-definition.md) §4.6 と本書 §9.3 に反映済み。コードはコピーせず数式から独立実装する | 完了 |
| Q3b | 実機 HDF5 を Windows 側で直接読むか、変換経由にするか → **変換経由に決定** | §7.3 のとおり。ECF コーデックと Linux 専用 SDK のため、WSL2 側で `.npz` へ変換する | 完了 |
| Q4 | 机上領域の既定矩形が実際の設置と合うか | [status-definition.md](status-definition.md) §3 の既定値 | 実機設置後に `config.yaml` で調整 |
| Q5 | 閾値の実測キャリブレーション手順 | 手動調整（詳細画面の実測 eps を見て設定を書き換え） | 実データ取得後。EXT で自動キャリブレーションを検討 |
| Q6 | ~~キャラクターのデザイン・素材形式~~ → **解決**。30×30 ドット絵ティラノサウルスの GIF 4 種を作成済み | `assets/character/` に配置済み。`tools/make_character_gifs.py` で再生成できる | 完了 |
| Q7 | 状態を周囲に共有する手段（旧・共有画面） | **版2.0 では実装しない。将来の展望として保留** | 再開時はローカルネットワーク限定とし、[status-definition.md](status-definition.md) §9 の JSON 形式のみを出す |
| Q8 | 状態履歴を永続化するか（セッションをまたぐか） | MVP はメモリ上のみ。終了で消える | EXT-4。保存するなら抽象状態のみ・保持期間設定必須 |
| Q9 | Random Forest の教師データ収集方法 | ルールベースの出力を弱教師として使う想定 | EXT-6 着手時 |
| Q10 | 複数人・複数机への対応 | 対象外（1 台 1 人） | 未定 |
| Q11 | GenX320 を机上向けに設置したときの実効イベントレートと、照明ちらつきの影響 | 未検証。R1 / R2 として管理 | 実機設置時 |

---

## 24. 参照リポジトリの調査結果

**両リポジトリとも読み取りのみで参照した。いかなる変更も加えていない。**
DeskMate は両者に**コードレベルでは依存しない**（数式と運用手順のみを参照する）。

### 24.1 `Ryunoshin3150/EVENT_CAMERA`（NAIST 研究室のイベントカメラ分析）

| 項目 | 内容 | DeskMate への反映 |
|------|------|------------------|
| 使用機材 | **Raspberry Pi 5 + Prophesee GenX320** | `sensor: 320x320` を既定に確定。`grid_rows` を 16 に変更 |
| 主要スクリプト | `minimal_voxel_analysis.py`（Voxel Grid 変換・ビン間差分・重心軌跡・変化量） | 数式を [status-definition.md](status-definition.md) §4.6 と本書 §9.3 に反映 |
| Voxel パラメータ | `HEIGHT = WIDTH = 320`, `NUM_BINS = 10`, bilinear temporal interpolation, `pol = p*2-1` | 同上。時間ビン数と空間解像度のみ DeskMate 側の要件に合わせて変更（相違点は §4.6 の表に明記） |
| 重心の定義 | `|ΔV|` 重み付き重心を `height` / `width` で割って 0–1 正規化 | 同一の定義を採用 |
| 変化量の定義 | `mean(|ΔV[b]|)` | `diff_l1` として採用 |
| イベント読込 | `metavision_core.event_io.EventsIterator(filepath, delta_t=100_000)` | **DeskMate では使わない**（Linux 専用のため）。ただし `delta_t = 100 ms` は DeskMate の窓長 200 ms と同オーダーであり、時間スケールの妥当性を裏付ける |
| データ形式 | HDF5。フィールドは `x`, `y`, `t`, `p` | DeskMate の `EventBatch` と同一。フィールド順と `p` の型のみ変換が必要（§6.1 の `EVENT_DTYPE_METAVISION`） |
| 収録手順 | `metavision_viewer -o rec.raw` → `metavision_file_to_hdf5 -i rec.raw -o rec.hdf5` → scp で PC へ | §7.3 のデータ経路に反映 |
| 環境 | Metavision/OpenEB は Ubuntu（Windows では WSL2）。`sudo apt install metavision-openeb` | **制約 C-1**。DeskMate 本体を `metavision_core` 非依存にする根拠 |
| 関連分析 | `analize_fidgeting.md`: 5 ms ビン（fs = 200 Hz）、2–6 Hz 帯のバンドエネルギー比で「そわそわ」を検出 | MVP では採用しない。EXT-9 として §25 に記載 |

### 24.2 `prophesee-ai/openeb`（Metavision SDK のオープンソース部分）

| 項目 | 内容 | DeskMate への反映 |
|------|------|------------------|
| 構成 | HAL / Base / Core / Core ML / Stream / UI の 6 モジュール + カメラプラグイン | DeskMate は**いずれも使わない**。イベント受信後の処理のみを対象とするため |
| 対応 OS | Ubuntu 22.04 / 24.04、Windows 11。Python 3.9–3.12 | **DeskMate は Python 3.11–3.13 / PySide6 で独立して動く。SDK を必須にしない** |
| HDF5 形式 | `/CD/events`（`x` uint16, `y` uint16, `p` int16, `t` int64）と `/CD/indexes`。**ECF コーデック（filter code 0x8ECF）で圧縮** | §6.1 の `EVENT_DTYPE_METAVISION` に反映 |
| h5py 互換性 | 素の h5py では読めない。`hdf5_ecf` プラグインの導入と `HDF5_PLUGIN_PATH` の設定が必要。公式も「試作用途に限る」と注記 | **制約 C-2**。§7.3 の「WSL2 側で `.npz` へ変換する」経路を採る根拠 |

### 24.3 実測キャリブレーション手順（実機入手後に実施）

閾値（R1）を確定させるための手順。

1. Pi 上で、机上の代表的な 4 場面を各 30 秒ずつ収録する
   （タイピング / マウス操作 / 座って静止 / 無人）。
2. `tools/convert_events.py` で `.npz` へ変換し、Windows へコピーする。
3. `python -m deskmate --source file --file <path> --debug` で再生し、
   詳細画面の実測 `event_rate_eps` を場面ごとに記録する。
4. 記録値から次のように閾値を決める。
   - `idle_eps` ← 「座って静止」の中央値 × 1.5
   - `away_seconds` ← 実際に離席してから表示が変わるまでの体感で調整（既定 30 秒）
   - `focus_min_eps` ← 「タイピング」の 10 パーセンタイル × 0.8
   - `high_activity_eps` ← 「片付ける」の 90 パーセンタイル
5. [status-definition.md](status-definition.md) §5.2 と `config/default.yaml` の**両方**を更新する。

---

## 25. 追加機能の候補（参照リポジトリ由来）

| # | 機能 | 概要 | 優先度 |
|---|------|------|--------|
| EXT-9 | 周波数解析による集中判定の補強 | `EVENT_CAMERA/analize_fidgeting.md` の手法。`event_rate_eps` の時系列を 5 ms ビン（fs = 200 Hz）で取り、2–6 Hz 帯のバンドエネルギー比を特徴量に加える。タイピングの周期性を捉えられれば `focused` の判定精度が上がる可能性がある | 低（MVP 後） |

**MVP では採用しない。** 理由: 5 ms ビンの時系列を保持するとメモリと計算量が増え、
現在の 200 ms 窓ベースの設計に対して構造変更が必要になるため。
ルールベースが実データで期待どおり動かなかった場合の改善案として記録しておく。

---

## 26. Raspberry Pi での実行

### 26.1 前提（DeskMate の外で済ませておくこと）

GitHub の `EVENT_CAMERA/RaspberryPi.md` で確認した手順。**DeskMate はこれらを実行しない。**

```bash
sudo dtoverlay genx320,cam0            # GenX320 のドライバオーバーレイ
cd ~/rpi-sensor-drivers
./rp5_setup_v4l.sh                     # V4L2 の設定
export PSEE_VAR_V4L2_BSIZE=1           # Metavision のバッファ設定
metavision_viewer                      # ライブ映像が出れば準備完了
```

`metavision_viewer` で映像が出ることを確認してから DeskMate を起動する。
`MetavisionEventSource.open()` が失敗したときは、このエラーメッセージにこの手順を出す。

### 26.2 DeskMate の導入

```bash
git clone <このリポジトリ> ~/DeskMate
cd ~/DeskMate
python3 -m venv --system-site-packages .venv    # metavision_core を見せるため必須
.venv/bin/pip install -e ".[dev]"
```

**`--system-site-packages` が必要。** Metavision SDK は apt でシステム側に入るので、
これを付けないと仮想環境から `metavision_core` が見えない。

### 26.3 起動

```bash
.venv/bin/python -m deskmate                    # input.source: auto -> metavision
.venv/bin/python -m deskmate --fullscreen       # Pi の画面いっぱいに出す
.venv/bin/python -m deskmate --source dummy     # カメラ無しで UI だけ確認
```

### 26.4 Windows 開発環境との違い

| 項目 | Raspberry Pi 5 | Windows |
|------|---------------|---------|
| `input.source: auto` の解決先 | `metavision`（ライブ） | `dummy`（自動フォールバック） |
| `.raw` の再生 | Metavision SDK で可能 | 不可。Pi 側で `.npz` へ変換して持ち込む（§7.3） |
| 詳細画面の更新頻度 | `ui.detail.refresh_hz` を 5 に下げることを推奨 | 10 のままでよい |
| 確認できること | 全機能 | UI・状態遷移・休憩促し（ダミー入力で） |

**Windows でできない確認**（実機でのみ可能）:

- 実カメラのイベントレートが `estimation` の閾値と合っているか（§24.3 のキャリブレーション）
- 机上の領域矩形が実際の設置と合っているか
- Pi の画面サイズでウィジェットが適切に見えるか
- 連続稼働時の発熱・性能

### 26.5 自動起動（任意）

デモ時に電源投入だけで立ち上げたい場合は systemd のユーザーユニットにする。

```ini
# ~/.config/systemd/user/deskmate.service
[Unit]
Description=DeskMate
After=graphical-session.target

[Service]
Environment=PSEE_VAR_V4L2_BSIZE=1
WorkingDirectory=%h/DeskMate
ExecStart=%h/DeskMate/.venv/bin/python -m deskmate
Restart=on-failure

[Install]
WantedBy=graphical-session.target
```

`systemctl --user enable --now deskmate` で有効化する。
**MVP では必須ではない。** 手動起動で足りる。
