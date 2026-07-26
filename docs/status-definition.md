# DeskMate 状態定義書

版: 1.0 / 最終更新: 2026-07-26

本書は DeskMate の**状態・特徴量・閾値・アニメーション・表示文字列**の唯一の正典である。
実装で数値や文字列に迷ったら、本書の値をそのまま使うこと。本書と他文書が矛盾した場合、本書を優先する。

---

## 1. 表示文言の原則（必読）

イベントカメラは輝度変化しか観測しない。したがって次を厳守する。

1. **「離席中」「不在」「席にいます」と表示してはならない。** 静止した在席と離席を区別できない。
2. 動きが無いときは、観測事実だけを述べる。使用してよい文言は以下に限る。
   - 「一定時間、動きを検出していません」
   - 「静かな状態が続いています」
   - 「現在の状態を判定できません」
3. **「作業しています」ではなく「作業中」「集中傾向」** のように、断定を避けた語尾を使う。
4. 信頼度 `confidence < 0.45` のときは、確定状態のラベルではなく「状態不明」を表示する（§6.4。`no_motion` のみ例外）。
5. 「話しかけやすそう」は観測事実ではない。必ず「〜そう」「〜かもしれません」の推量形で表示する。
6. 状態名の末尾に句点を付けない。継続時間は状態名とは別要素として表示する。

---

## 2. 抽象状態 DeskStatus

`src/deskmate/core/enums.py`

```python
class DeskStatus(str, Enum):
    FOCUSED     = "focused"
    WORKING     = "working"
    ORGANIZING  = "organizing"
    SHORT_BREAK = "short_break"
    TRANSITION  = "transition"
    NO_MOTION   = "no_motion"
    UNKNOWN     = "unknown"
```

| enum 値 | 日本語ラベル | 意味（観測ベース） | 詳細画面 | 共有画面 |
|---------|------------|------------------|:--------:|:--------:|
| `focused` | 集中傾向 | キーボード / マウス周辺に限定された動きが継続している | ○ | ○ |
| `working` | 作業中 | 机上に一定の活動があるが、集中傾向の条件は満たさない | ○ | ○ |
| `organizing` | 机上整理中 | 机上の広い範囲で、大きく速い動きがある | ○ | ○ |
| `short_break` | 小休止 | 活動量が直前より明確に低下し、低水準で推移している | ○ | ○ |
| `transition` | 状態が変化中 | 活動パターンが短時間で大きく変化している | ○ | ○ |
| `no_motion` | 一定時間、動きを検出していません | 一定時間、イベントがほとんど発生していない | ○ | ○ |
| `unknown` | 状態不明 | いずれの条件にも該当しない、または信頼度が低い | ○ | ○ |

### 2.1 システム状態 SystemStatus（DeskStatus とは別軸）

推定結果ではなく、アプリの動作状況を表す。UI では DeskStatus より優先して表示する。

```python
class SystemStatus(str, Enum):
    STARTING      = "starting"       # 起動中・ウォームアップ中
    RUNNING       = "running"        # 正常稼働
    NO_SIGNAL     = "no_signal"      # 入力が途切れている
    PAUSED        = "paused"         # ユーザが推定を停止した
    SHARING_OFF   = "sharing_off"    # 共有のみ停止（推定は継続）
    ERROR         = "error"          # 復帰不能なエラー
```

| enum 値 | 表示文言（本人用） | 表示文言（共有画面） |
|---------|------------------|--------------------|
| `starting` | 起動中です（推定準備中） | 準備中です |
| `running` | （DeskStatus のラベルを表示） | （DeskStatus のラベルを表示） |
| `no_signal` | 入力が途切れています | 現在の状態を判定できません |
| `paused` | 推定を停止しています | 共有を停止しています |
| `sharing_off` | （DeskStatus のラベルを表示） | 共有を停止しています |
| `error` | エラーが発生しています | 現在の状態を判定できません |

`paused` / `sharing_off` / `no_signal` / `error` の間、共有画面には**直前の状態を残さない**。

---

## 3. 領域 RegionId

```python
class RegionId(str, Enum):
    KEYBOARD = "keyboard"
    MOUSE    = "mouse"
    CENTER   = "center"
    LEFT     = "left"
    RIGHT    = "right"
    OTHER    = "other"
```

- 領域は**センサ座標を 0.0–1.0 に正規化した矩形** `[x0, y0, x1, y1]` で定義する。
- 設定ファイルの並び順が優先順位であり、**最初に一致した領域に属する**（重なりを許す）。
- どの矩形にも属さないイベントは `other` に集計する。`other` は設定に書かない（暗黙）。
- 既定値（モニタ上部から俯瞰、手前がキーボード側を想定）:

```yaml
regions:
  - id: keyboard
    rect: [0.25, 0.62, 0.75, 1.00]
  - id: mouse
    rect: [0.75, 0.60, 1.00, 1.00]
  - id: center
    rect: [0.30, 0.25, 0.70, 0.62]
  - id: left
    rect: [0.00, 0.00, 0.30, 0.62]
  - id: right
    rect: [0.70, 0.00, 1.00, 0.60]
```

`focused` 判定に使う「入力デバイス領域」は `estimation.focus_regions`（既定 `[keyboard, mouse]`）で定義する。

---

## 4. 特徴量

### 4.1 単位と記号

| 記号 | 意味 | 単位 |
|------|------|------|
| `W` | 時間窓長 | 秒（既定 0.2） |
| `N` | 窓内イベント総数 | 件 |
| `eps` | 活動量 = `N / W` | 件/秒 |
| `w_px`, `h_px` | センサ解像度 | px（既定 **320×320** = Prophesee GenX320） |
| `diag` | `hypot(w_px, h_px)` | px（320×320 のとき 452.5） |

**センサ解像度の根拠**: 参照リポジトリ `EVENT_CAMERA` の `RaspberryPi.md` により、
使用機材が **Raspberry Pi 5 + Prophesee GenX320** であることを確認した。
GenX320 は 320×320。同リポジトリの `minimal_voxel_analysis.py` も `HEIGHT = WIDTH = 320` を用いている。

座標は**センサ座標（px, 左上原点）**で計算し、比率系の特徴量のみ正規化する。

### 4.2 全体特徴量 GlobalFeatures

`src/deskmate/pipeline/features.py`

| フィールド名 | 型 | 定義 | 備考 |
|-------------|----|------|------|
| `event_count` | `int` | 窓内イベント総数 `N` | |
| `positive_count` | `int` | `p == 1` の件数 | |
| `negative_count` | `int` | `p == 0` の件数 | |
| `positive_ratio` | `float` | `positive_count / N`。`N == 0` なら `0.5` | 0–1 |
| `event_rate_eps` | `float` | `N / W` | 件/秒 |
| `centroid_x` | `float` | `mean(x)`。`N == 0` なら直前窓の値、初回は `w_px/2` | px |
| `centroid_y` | `float` | `mean(y)`。同上（初回は `h_px/2`） | px |
| `centroid_shift` | `float` | 直前窓の重心とのユークリッド距離。初回は `0.0` | px |
| `centroid_speed` | `float` | `centroid_shift / W` | px/秒 |
| `var_x` | `float` | `var(x)`。`N < 2` なら `0.0` | px² |
| `var_y` | `float` | `var(y)`。同上 | px² |
| `spatial_std` | `float` | `sqrt(var_x + var_y)` | px |
| `bbox_width` | `float` | パーセンタイル幅 `p(1-q)(x) - p(q)(x)`、`q = features.bbox_percentile`（既定 0.05）。`N < 10` なら `0.0` | px |
| `bbox_height` | `float` | 同様に y 方向 | px |
| `bbox_area_ratio` | `float` | `bbox_width * bbox_height / (w_px * h_px)` | 0–1 |
| `active_cell_ratio` | `float` | 1 件以上のイベントを含むグリッドセル数 / 全セル数。グリッドは `window.grid_cols × window.grid_rows`（既定 16×16） | 0–1 |
| `event_count_delta` | `int` | `event_count - 直前窓の event_count`。初回は `0` | 件 |
| `event_rate_delta` | `float` | `event_rate_eps - 直前窓の event_rate_eps` | 件/秒 |
| `activity_ratio_10s` | `float` | 直近 10 秒の窓のうち `event_rate_eps >= estimation.idle_eps` だった窓の割合 | 0–1 |
| `idle_seconds` | `float` | `event_rate_eps < estimation.idle_eps` が連続している秒数。条件を外れたら 0 にリセット | 秒 |
| `active_seconds` | `float` | `event_rate_eps >= estimation.idle_eps` が連続している秒数。条件を外れたら 0 にリセット | 秒 |
| `noise_ratio` | `float` | `1.0 - (上位 active_cell の 10% が占めるイベント比率)`。ノイズ検知の補助。`N == 0` なら `0.0` | 0–1 |

`bbox` にパーセンタイルを使うのは、単発ノイズで範囲が跳ねるのを避けるため。

### 4.3 領域別特徴量 RegionFeatures

各 `RegionId` について算出する（`other` を含む 6 件、常に全件を埋める）。

| フィールド名 | 型 | 定義 |
|-------------|----|------|
| `region_id` | `RegionId` | 領域 |
| `event_count` | `int` | 領域内イベント数 |
| `event_rate_eps` | `float` | `event_count / W` |
| `share` | `float` | `event_count / N`。`N == 0` なら `0.0` |
| `centroid_x` | `float` | 領域内重心 x（px）。`event_count == 0` なら領域矩形の中心 |
| `centroid_y` | `float` | 領域内重心 y（px）。同上 |
| `active_cell_ratio` | `float` | 領域内グリッドセルの活性率 |

### 4.4 平滑値 SmoothedFeatures

推定はこの平滑値に対して行う。EMA の係数は `alpha = 1 - exp(-W / tau)`。

| フィールド名 | tau | 由来 |
|-------------|-----|------|
| `rate_short` | `features.ema_short_seconds`（既定 1.0） | `event_rate_eps` の EMA |
| `rate_long` | `features.ema_long_seconds`（既定 10.0） | `event_rate_eps` の EMA |
| `centroid_short` | 1.0 | `(centroid_x, centroid_y)` の EMA |
| `centroid_long` | 10.0 | 同上 |
| `area_short` | 1.0 | `bbox_area_ratio` の EMA |
| `area_long` | 10.0 | 同上 |
| `speed_short` | 1.0 | `centroid_speed` の EMA |
| `cell_short` | 1.0 | `active_cell_ratio` の EMA |
| `share_short[region]` | 1.0 | 領域 `share` の EMA（6 領域） |
| `share_long[region]` | 10.0 | 同上 |
| `rate_cv_10s` | – | 直近 10 秒の `event_rate_eps` の変動係数 `std/mean`。`mean <= 0` なら `999.0` |

### 4.5 変化スコア change_score

`transition` 判定に使う。0.0–1.0。

```
c1 = clip(abs(rate_short - rate_long) / max(rate_long, idle_eps), 0, 1)
c2 = clip(hypot(centroid_short - centroid_long) / (0.25 * diag), 0, 1)
c3 = clip(abs(area_short - area_long), 0, 1)
c4 = clip(0.5 * sum_over_regions(abs(share_short[r] - share_long[r])), 0, 1)

change_score = 0.35*c1 + 0.25*c2 + 0.15*c3 + 0.25*c4
```

### 4.6 拡張特徴量 Voxel（既定 OFF）

`features.voxel.enabled: false`。EXT-5 で有効化する。有効時のみ以下を追加算出する。

**算出方法は参照リポジトリ `EVENT_CAMERA` の `minimal_voxel_analysis.py` の数式に一致させる**
（同リポジトリは読み取りのみ。コードはコピーせず、数式に基づいて独立に実装する）。

| フィールド名 | 定義 | 参照実装の対応 |
|-------------|------|--------------|
| `diff_l1` | `mean(abs(ΔV))` を全差分ステップで平均した値 | `mag_seq = [np.abs(diff_v[b]).mean() ...]` の平均 |
| `diff_centroid_x` | 最終差分ステップの重心 X（**0.0–1.0 に正規化**） | `cx_seq[-1]` |
| `diff_centroid_y` | 最終差分ステップの重心 Y（**0.0–1.0 に正規化**） | `cy_seq[-1]` |
| `diff_energy` | `sum(ΔV ** 2)` を全差分ステップで合計した値 | 参照実装には無い DeskMate 独自の追加 |
| `diff_centroid_shift` | 重心軌跡の総移動量 `sum(hypot(Δcx, Δcy))`（正規化座標） | `cy_seq` / `cx_seq` の軌跡長 |

数式（参照リポジトリ README の記載と同一）:

```
1. 正規化タイムスタンプ   t* = (B - 1) * (t - t0) / (tN - t0)
2. 極性                  pol = p * 2 - 1            （0/1 → -1/+1）
3. Bilinear kernel       w(b) = max(0, 1 - |b - t*|)
4. Voxel Grid            V[b, y, x] = Σ pol * w(b)
5. ビン間差分            ΔV[b] = V[b+1] - V[b]      （B-1 枚）
6. 重心                  cy[b] = Σ|ΔV[b,y,x]| * y / (Σ|ΔV[b,y,x]| + 1e-9) / H
                         cx[b] = Σ|ΔV[b,y,x]| * x / (Σ|ΔV[b,y,x]| + 1e-9) / W
7. 変化量                mag[b] = mean(|ΔV[b]|)
```

**参照実装との相違点（意図的）**:

| 項目 | 参照実装 | DeskMate | 理由 |
|------|---------|---------|------|
| 時間ビン数 | `NUM_BINS = 10`（2 秒クリップ = 1 ビン 200 ms） | `features.voxel.time_bins`（既定 4、200 ms 窓 = 1 ビン 50 ms） | DeskMate はリアルタイムの短い窓を扱う |
| 空間解像度 | `H = W = 320`（フル解像度） | `features.voxel.spatial_scale`（既定 4 → 80×80）でダウンサンプル | 200 ms ごとの実時間処理に収めるため |
| 累積方法 | `np.add.at` | `np.bincount(minlength=...)` で等価計算 | `np.add.at` は低速。数値結果は一致する |
| 用途 | オフライン分析と PNG 出力 | オンライン特徴量 | – |

`spatial_scale = 1` にすればフル解像度になり、参照実装と同じ値が得られる。
`tests/test_voxel.py` でこの一致を検証する（§4.6 の検証項目）。

**MVP では `voxel.py` を実装するが、`FeatureExtractor` からは呼ばない**（既定 OFF）。

---

## 5. 推定ルール

`src/deskmate/pipeline/rule_estimator.py`

### 5.1 評価順序

上から順に評価し、**最初に条件を満たしたものを候補状態とする**（早期 return）。

| 順位 | 状態 | 条件 |
|:----:|------|------|
| 1 | `no_motion` | `idle_seconds >= no_motion_seconds` |
| 2 | `transition` | `change_score >= transition_change_score` かつ `rate_short >= idle_eps` かつ 抑止中でない（下記） |
| 3 | `organizing` | `rate_short >= active_eps` かつ `area_short >= organizing_bbox_area_ratio` かつ `cell_short >= organizing_active_cell_ratio` かつ `speed_short >= organizing_centroid_speed` |
| 4 | `focused` | `rate_short >= focus_min_eps` かつ `focus_share >= focus_region_share` かつ `area_short <= focus_max_bbox_area_ratio` かつ `rate_cv_10s <= focus_max_activity_cv` かつ `active_seconds >= focus_min_seconds` |
| 5 | `short_break` | `rate_short <= break_max_eps` かつ `rate_short <= break_decay_ratio * rate_long` かつ `rate_short > idle_eps` |
| 6 | `working` | `rate_short >= low_activity_eps` |
| 7 | `unknown` | 上記いずれも該当しない |

`focus_share = sum(share_short[r] for r in estimation.focus_regions)`

**`transition` の抑止**: `RuleStatusEstimator` は内部に `_transition_started_at: float | None` を持つ。
ルール 2 が成立して `transition` を返した窓では、`None` なら
`SmoothedFeatures.elapsed_seconds` を記録する。
`elapsed_seconds - _transition_started_at > transition_max_seconds` になったら、
以後ルール 2 をスキップし（＝抑止状態）、ルール 3 以降で評価する。
ルール 2 が不成立の窓が 1 回でも来たら `_transition_started_at = None` に戻して抑止を解除する。
これにより、変化が続く限り `transition` に貼り付き続けることを防ぐ。
`reset()` で `None` に戻す。

### 5.2 閾値（設定 `estimation.*` の既定値）

**活動量閾値のスケール根拠**: 下表の eps 値は **320×320（102,400 画素）** を前提にした初期値である。
実機データ未取得のため確定値ではなく、[architecture.md](architecture.md) §22 のリスク R1 として管理する。
実測後は本表と `config/default.yaml` の**両方**を同時に更新すること。

| キー | 既定値 | 単位 | 説明 |
|------|-------|------|------|
| `idle_eps` | 100.0 | 件/秒 | これ未満を「動きなし」とみなす |
| `low_activity_eps` | 400.0 | 件/秒 | `working` の下限。`focus_min_eps` と同値にして判定の隙間を作らない |
| `focus_min_eps` | 400.0 | 件/秒 | `focused` の下限 |
| `active_eps` | 2000.0 | 件/秒 | `organizing` の下限 |
| `high_activity_eps` | 5000.0 | 件/秒 | 信頼度計算の上限基準 |
| `no_motion_seconds` | 20.0 | 秒 | この時間、活動なしが続くと `no_motion` |
| `focus_regions` | `["keyboard","mouse"]` | – | 集中判定に使う領域 |
| `focus_region_share` | 0.60 | 0–1 | 入力デバイス領域のイベント占有率下限 |
| `focus_min_seconds` | 5.0 | 秒 | 連続活動の下限 |
| `focus_max_bbox_area_ratio` | 0.20 | 0–1 | 動きの広がり上限。実測分布から決定（§5.4） |
| `focus_max_activity_cv` | 0.60 | – | 活動量の変動係数上限（安定していること） |
| `organizing_bbox_area_ratio` | 0.25 | 0–1 | 広い範囲の下限。実測分布から決定（§5.4） |
| `organizing_active_cell_ratio` | 0.25 | 0–1 | 活性セル比率の下限 |
| `organizing_centroid_speed` | 35.0 | px/秒 | 重心移動速度の下限（320×320 基準） |
| `break_max_eps` | 600.0 | 件/秒 | 小休止の活動量上限 |
| `break_decay_ratio` | 0.40 | – | 長期平均に対する低下率 |
| `transition_change_score` | 0.55 | 0–1 | 変化スコア閾値 |
| `transition_max_seconds` | 6.0 | 秒 | `transition` の最大継続時間（超えたら再評価） |
| `noise_ratio_threshold` | 0.79 | 0–1 | これを超えたらノイズ優勢とみなし信頼度を 0.6 倍する。`noise_ratio` は一様分布でも約 0.87 で飽和するため、0.85 では発火が半分の窓に留まる（§5.5） |
| `warmup_seconds` | 3.0 | 秒 | 起動後この時間は `SystemStatus.STARTING`。推定結果を出さない |

### 5.3 信頼度 confidence

各ルールは 0.0–1.0 の信頼度を返す。基本形は「閾値からの超過分を正規化して 0.5 に加算」。

```python
def _margin_conf(value: float, threshold: float, span: float) -> float:
    """閾値超過分を 0.5〜0.95 にマップする。"""
    m = (value - threshold) / span if span > 0 else 0.0
    return float(min(0.95, max(0.30, 0.5 + 0.45 * min(1.0, max(0.0, m)))))
```

| 状態 | 信頼度の式 |
|------|-----------|
| `no_motion` | `_margin_conf(idle_seconds, no_motion_seconds, no_motion_seconds)` |
| `transition` | `_margin_conf(change_score, transition_change_score, 1.0 - transition_change_score)` |
| `organizing` | 4 条件それぞれの `_margin_conf` の**最小値** |
| `focused` | `min(_margin_conf(focus_share, focus_region_share, 1.0 - focus_region_share), _margin_conf(active_seconds, focus_min_seconds, focus_min_seconds))` |
| `short_break` | `_margin_conf(break_decay_ratio * rate_long - rate_short, 0.0, max(break_max_eps, 1.0))` |
| `working` | `_margin_conf(rate_short, low_activity_eps, high_activity_eps - low_activity_eps)` |
| `unknown` | 固定 `0.30` |

補正: `noise_ratio > noise_ratio_threshold` のとき `confidence *= 0.6`。
`SystemStatus.STARTING` の間は候補を出さない。

### 5.4 面積閾値の実測根拠（ダミー入力）

`bbox_percentile` と 2 つの面積閾値は、当初値（0.02 / 0.25 / 0.35）ではダミー入力で
`focused` と `working` が 3 秒ごとに振動した。原因は `bbox_percentile = 0.02` が緩すぎて、
1 窓あたり約 280 イベントの中に混ざる数件の一様ノイズを削り切れず、
`bbox_area_ratio` が `focus_max_bbox_area_ratio` を跨いで上下していたことである。

`bbox_percentile = 0.05` に変更したうえで、各シナリオの `area_short` の分布を実測した
（320×320、窓 200 ms、シナリオごとに約 20 秒）。

| シナリオ | p5 | 中央値 | p95 |
|---------|-----|-------|-----|
| `keyboard_steady` | 0.058 | 0.064 | 0.077 |
| `mouse_intermittent` | 0.020 | 0.048 | 0.138 |
| `desk_wide_active` | 0.286 | 0.363 | 0.437 |
| `noise_burst` | 0.472 | 0.502 | 0.532 |

狭い動き（上 2 行、最大 0.138）と広い動き（下 2 行、最小 0.286）の間に
0.14–0.29 の空白帯があるので、そこに 2 つの閾値を置いた。

- `focus_max_bbox_area_ratio = 0.20`（狭い動きの p95 の 1.4 倍）
- `organizing_bbox_area_ratio = 0.25`（広い動きの p5 の 0.87 倍）

両者の間に 0.05 の間隔があるため、境界付近で `focused` と `organizing` が交互に出ることはない。
**実機データを得たら §24.3 の手順で同じ測定を行い、この 3 値を再設定すること。**


### 5.5 ダミーシナリオを作るときの制約

閾値とシナリオ・パラメータの噛み合わせで実測した、再発しやすい落とし穴を記録する。
新しいシナリオを追加するときは以下を守ること。

| # | 制約 | 理由（実測） |
|---|------|------------|
| 1 | `burst_period_s` は `features.ema_short_seconds`（既定 1.0 秒）より**短く**する | `mouse_intermittent` を `burst_period_s = 3.0` / `burst_duty = 0.45` にすると、休止が 1.65 秒続いて `rate_short` が `idle_eps` 付近まで落ち、`short_break` が誤発火した。1.0 秒 / 0.60 に変えて解消 |
| 2 | 実効活動量（`base_rate_eps × burst_duty`）が `break_max_eps` を明確に上回るようにする | 実効値が `break_max_eps`(600) 付近だと `working` と `short_break` が交互に出る |
| 3 | `uniform_noise_ratio` を上げてノイズ優勢を表現する場合、`noise_ratio` は**約 0.87 で飽和する**ことに注意 | グリッドが 16×16 のとき、完全な一様分布でも `noise_ratio ≈ 0.87` が上限。`noise_ratio_threshold` を 0.85 にすると発火が窓の約半分に留まり、信頼度の EMA が中間値（0.53〜0.57）で止まって「状態不明」に落ちなかった。閾値を 0.79 に下げて解消（他シナリオの p95 は 0.766 以下なので誤発火しない） |
| 4 | 面積系の閾値は §5.4 の空白帯（0.14–0.29）を跨がないようにする | 閾値が分布の中央にあると状態が振動する |

**実測した `noise_ratio` の分布**（320×320、グリッド 16×16、各 30 秒）:

| シナリオ | p5 | 中央値 | p95 |
|---------|-----|-------|-----|
| `keyboard_steady` | 0.526 | 0.590 | 0.636 |
| `mouse_intermittent` | 0.260 | 0.504 | 0.766 |
| `desk_wide_active` | 0.357 | 0.674 | 0.724 |
| `rapid_change` | 0.030 | 0.121 | 0.713 |
| `noise_burst` | 0.811 | 0.843 | 0.868 |

`noise_ratio` は「上位 10% の活性セルが占めるイベント比率」の補数なので、
活性セル数が少ない集中した動きでも 0.5〜0.6 程度になる。**一様性の指標としては弱い。**
実データでノイズ判定に使うなら、この飽和特性を踏まえて閾値を決めること。

---

## 6. 平滑化と状態遷移

`src/deskmate/pipeline/smoother.py`

### 6.1 パラメータ（`smoothing.*`）

| キー | 既定値 | 説明 |
|------|-------|------|
| `vote_window_size` | 5 | 直近この件数の候補状態で多数決（既定 200 ms × 5 = 1 秒） |
| `vote_min_count` | 3 | 遷移に必要な最小得票数 |
| `enter_confidence` | 0.50 | 新状態へ遷移するのに必要な、得票した候補の平均信頼度 |
| `exit_confidence` | 0.35 | 現状態の信頼度がこれを下回ると、遷移条件を緩和（得票数 2 で可） |
| `confidence_ema_seconds` | 2.0 | 表示用信頼度の EMA 時定数 |
| `min_dwell_seconds.default` | 3.0 | 最小状態継続時間 |
| `min_dwell_seconds.transition` | 2.0 | 〃（`transition`） |
| `min_dwell_seconds.no_motion` | 5.0 | 〃（`no_motion`） |
| `min_dwell_seconds.unknown` | 2.0 | 〃（`unknown`） |

### 6.2 アルゴリズム

窓ごとに 1 回呼ばれる。

1. 候補 `estimate` をリングバッファ（長さ `vote_window_size`）へ push。
2. バッファが満たない間は、現状態を維持（初期状態は `unknown`）。
3. 多数決で最多の候補 `top` と得票数 `n`、その平均信頼度 `c_avg` を求める。同数の場合は §5.1 の評価順位が上（数字が小さい）方を選ぶ。
4. `top == current` なら、状態を維持し継続時間を伸ばす。
5. `top != current` のとき、以下をすべて満たせば遷移:
   - `elapsed(current) >= min_dwell_seconds[current]`
   - `n >= vote_min_count`、ただし `current の平滑信頼度 < exit_confidence` なら `n >= vote_min_count - 1`
   - `c_avg >= enter_confidence`
   - 遷移が §6.3 の遷移表で許可されている
6. 遷移する場合、`StateChange` を発火し、継続時間を 0 にリセットする。
7. `no_motion` への遷移だけは例外で、`idle_seconds >= no_motion_seconds` が成立していれば
   `min_dwell` と多数決を無視して即座に遷移する（安全側の表示のため）。
8. `transition` が `transition_max_seconds` を超えて継続した場合、強制的に候補を再評価し、
   `transition` 以外で最も得票の多い状態へ遷移する。該当がなければ `unknown` へ。

### 6.3 遷移表

`o` = 許可、`-` = 直接遷移禁止（`transition` または `unknown` を経由する）。

| from \ to | focused | working | organizing | short_break | transition | no_motion | unknown |
|-----------|:-------:|:-------:|:----------:|:-----------:|:----------:|:---------:|:-------:|
| focused | – | o | o | o | o | o | o |
| working | o | – | o | o | o | o | o |
| organizing | - | o | – | o | o | o | o |
| short_break | - | o | o | – | o | o | o |
| transition | o | o | o | o | – | o | o |
| no_motion | - | o | - | o | o | – | o |
| unknown | o | o | o | o | o | o | – |

意図: `organizing`/`no_motion`/`short_break` から `focused` へ直接飛ばず、必ず `working` か `transition` を経由させる。
これにより「急に集中傾向になった」という不自然な表示を避ける。

### 6.4 表示信頼度と断定回避

- 表示用の信頼度は、確定状態の候補信頼度を `confidence_ema_seconds` で EMA した値。
- `confidence < 0.45` のとき、UI は確定状態のラベルの代わりに以下を表示する。
  - 確定状態が `no_motion` の場合はそのまま「一定時間、動きを検出していません」
  - それ以外は「状態不明」
  - 内部の `DeskStatus` は変更しない（表示のみの降格）。この判定は `ui.labels.resolve_label()` に集約する。

---

## 7. キャラクター表示

### 7.1 AnimationId

```python
class AnimationId(str, Enum):
    WORKING_AT_DESK = "working_at_desk"
    TYPING          = "typing"
    ORGANIZING_DESK = "organizing_desk"
    DRINKING_TEA    = "drinking_tea"
    RESTING         = "resting"
    LOOKING_AROUND  = "looking_around"
    SLEEPING        = "sleeping"
    TRANSITIONING   = "transitioning"
    UNKNOWN         = "unknown"
```

### 7.2 状態 → アニメーション対応表

継続時間で分岐する。**該当行のうち `min_duration_s` が条件を満たす最大のものを選ぶ**（決定的）。

| DeskStatus | min_duration_s | AnimationId | 代替表示（素材なし時） |
|------------|:--------------:|-------------|----------------------|
| `focused` | 0 | `typing` | ⌨️ + 上下に 2px 揺れ |
| `focused` | 600 | `working_at_desk` | 💻 + ゆっくり揺れ |
| `working` | 0 | `working_at_desk` | 💻 |
| `organizing` | 0 | `organizing_desk` | 🧹 + 左右移動 |
| `short_break` | 0 | `drinking_tea` | 🍵 |
| `short_break` | 60 | `resting` | 😌 |
| `transition` | 0 | `transitioning` | 🔄 + 回転 |
| `no_motion` | 0 | `looking_around` | 👀 + 左右に首振り |
| `no_motion` | 120 | `sleeping` | 😴 + ゆっくり拡縮 |
| `unknown` | 0 | `unknown` | ❔ |

SystemStatus による上書き:

| SystemStatus | AnimationId | 代替表示 |
|--------------|-------------|---------|
| `starting` | `unknown` | ⏳ |
| `no_signal` | `unknown` | 📡（薄く表示） |
| `paused` | `resting` | ⏸️ |
| `error` | `unknown` | ⚠️ |

### 7.3 状態ごとのアクセント色

`src/deskmate/ui/theme.py` の `STATUS_COLORS`。**light / dark で共通**にする
（見る人が色で状態を覚えるので、テーマによって意味が変わってはならない）。

| DeskStatus | 色 | 意図 |
|------------|----|------|
| `focused` | `#5B8DEF`（青） | 集中 |
| `working` | `#4FB3A9`（青緑） | 通常の作業 |
| `organizing` | `#C97B2B`（橙） | 大きな動き |
| `short_break` | `#3FA96B`（緑） | 休息・話しかけやすい |
| `transition` | `#A78BFA`（紫） | 過渡状態 |
| `no_motion` | `#6B7280`（灰） | 動きなし |
| `unknown` | `#4B5563`（暗灰） | 判定不能 |

この色は次の 3 箇所で共有する: 常駐ウィジェットの状態ドットと信頼度バー、
キャラクターのハローと胴体（`ANIMATION_COLORS` 経由）、状態履歴ストライプ。
`AnimationId` → 色は `ANIMATION_COLORS` で定義し、`drinking_tea` と `resting` は
`short_break` の色、`looking_around` と `sleeping` は `no_motion` の色を使う。

### 7.4 ループアニメーションの動き

`ShapeCharacterRenderer` の `_MOTION`。振幅はキャラクターの短辺に対する比率。

| 動き | 内容 | 適用する AnimationId |
|------|------|---------------------|
| `bob` | 上下に ±3.5% | `typing`, `working_at_desk` |
| `sway` | 左右に ±7.5% | `organizing_desk`, `looking_around` |
| `pulse` | 拡縮 ±5% | `resting`, `sleeping` |
| `spin` | 1 周期で 360° 回転 | `transitioning` |
| `still` | 静止 | `drinking_tea`, `unknown` |

周期は `character.loop_period_seconds`（既定 2.0 秒）。
描画は「ハロー（放射グラデーション、α110）→ 胴体（放射グラデーション + 明るいリム）→ 絵文字」の順。

### 7.5 状態変化時のアニメーション

- 状態が変化した瞬間だけ、350 ms のクロスフェード + 4px のバウンスを行う。
- 変化がない間は、ループアニメーション（既定は 2 秒周期の微小な上下動）のみ。
- アニメーション速度・振幅は `character.*` 設定で変更できる。

---

## 8. 話しかけやすさ Approachability（二次指標）

```python
class Approachability(str, Enum):
    LIKELY_OK    = "likely_ok"
    PREFER_LATER = "prefer_later"
    UNDETERMINED = "undetermined"
```

| enum 値 | 共有画面の文言 | 色（`ui.theme`） |
|---------|--------------|-----------------|
| `likely_ok` | 話しかけやすそう | `accent_ok` (#3FA96B) |
| `prefer_later` | 集中しているようです | `accent_busy` (#C97B2B) |
| `undetermined` | 判断できません | `accent_muted` (#6B7280) |

### 8.1 導出ルール

`src/deskmate/pipeline/approachability.py`。確定状態・継続時間・直近履歴のみを入力とし、
**特徴量を直接参照しない**（共有情報の抽象度を担保するため）。

上から順に評価し、最初に一致したものを返す。

| 順位 | 条件 | 結果 |
|:----:|------|------|
| 1 | `SystemStatus != running` | `undetermined` |
| 2 | `confidence < share.min_confidence`(0.50) | `undetermined` |
| 3 | `status in (no_motion, unknown, transition)` | `undetermined` |
| 4 | `status == short_break` かつ `duration >= approachable_after_break_seconds`(10) | `likely_ok` |
| 5 | `status == working` かつ 直近 `recent_busy_lookback_seconds`(120) 以内に `focused` か `organizing` の確定履歴がある かつ その履歴が現在より前に終了している | `likely_ok` |
| 6 | `status in (focused, organizing)` かつ `duration >= prefer_later_min_seconds`(30) | `prefer_later` |
| 7 | `status in (focused, organizing)` | `undetermined` |
| 8 | それ以外（`working` で直前に忙しい履歴なし） | `undetermined` |

ルール 4 / 5 が「活動量が低く、直前の活発な作業が終了している」を表す。
ルール 6 が「一定の操作が継続している」を表す。

### 8.2 更新間隔とちらつき防止

- 更新は `share.update_interval_ms`（既定 1000 ms）ごと。
- 結果が変わっても、`share.min_hold_seconds`（既定 5.0 秒）は前の値を保持する。
- `undetermined` への変化だけは即時反映する（安全側）。

---

## 9. 表示文字列の一覧（実装時はこの表をそのまま定数化する）

`src/deskmate/ui/labels.py` に集約する。ハードコードを他ファイルに置かないこと。

```python
STATUS_LABELS_JA: dict[DeskStatus, str] = {
    DeskStatus.FOCUSED:     "集中傾向",
    DeskStatus.WORKING:     "作業中",
    DeskStatus.ORGANIZING:  "机上整理中",
    DeskStatus.SHORT_BREAK: "小休止",
    DeskStatus.TRANSITION:  "状態が変化中",
    DeskStatus.NO_MOTION:   "一定時間、動きを検出していません",
    DeskStatus.UNKNOWN:     "状態不明",
}

STATUS_LABELS_SHORT_JA: dict[DeskStatus, str] = {   # 常駐ウィジェット用の短縮形
    DeskStatus.FOCUSED:     "集中傾向",
    DeskStatus.WORKING:     "作業中",
    DeskStatus.ORGANIZING:  "机上整理中",
    DeskStatus.SHORT_BREAK: "小休止",
    DeskStatus.TRANSITION:  "変化中",
    DeskStatus.NO_MOTION:   "動きを検出していません",
    DeskStatus.UNKNOWN:     "状態不明",
}

QUIET_VARIANTS_JA: list[str] = [   # no_motion の言い換え候補（継続時間で切替）
    "一定時間、動きを検出していません",   # 0 秒〜
    "静かな状態が続いています",           # 120 秒〜
]

APPROACHABILITY_LABELS_JA: dict[Approachability, str] = {
    Approachability.LIKELY_OK:    "話しかけやすそう",
    Approachability.PREFER_LATER: "集中しているようです",
    Approachability.UNDETERMINED: "判断できません",
}

SYSTEM_LABELS_JA: dict[SystemStatus, str] = {
    SystemStatus.STARTING:    "起動中です（推定準備中）",
    SystemStatus.RUNNING:     "",
    SystemStatus.NO_SIGNAL:   "入力が途切れています",
    SystemStatus.PAUSED:      "推定を停止しています",
    SystemStatus.SHARING_OFF: "",
    SystemStatus.ERROR:       "エラーが発生しています",
}

PRIVACY_NOTICE_JA = "RGB映像は使用していません / 生データは外部送信していません"
PRIVACY_CAVEAT_JA = "イベントデータからも動きの形状が推測される可能性があります"
```

ラベル解決関数のシグネチャ:

```python
def resolve_label(status: DeskStatus,
                  confidence: float,
                  duration_seconds: float = 0.0,
                  system_status: SystemStatus = SystemStatus.RUNNING,
                  short: bool = False,
                  floor: float = 0.45) -> str:
    """表示用ラベルを返す。
    1. system_status が RUNNING / SHARING_OFF 以外なら SYSTEM_LABELS_JA を返す。
    2. status == NO_MOTION なら duration_seconds で選ぶ（confidence による降格を行わない）。
       duration >= 120 秒なら QUIET_VARIANTS_JA[1]「静かな状態が続いています」。
       それ未満は short=True のとき STATUS_LABELS_SHORT_JA[NO_MOTION]（常駐ウィジェット用の
       短縮形）、short=False のとき QUIET_VARIANTS_JA[0]。
    3. confidence < floor なら STATUS_LABELS_JA[UNKNOWN]（"状態不明"）を返す。
    4. それ以外は short に応じて STATUS_LABELS_SHORT_JA / STATUS_LABELS_JA を返す。
    floor は smoothing.display_confidence_floor（既定 0.45）を渡す。
    """
```

継続時間の書式（`format_duration(seconds: float) -> str`）:

| 範囲 | 書式 | 例 |
|------|------|-----|
| < 60 秒 | `{n}秒` | `42秒` |
| < 60 分 | `{m}分{s}秒` | `5分12秒` |
| それ以上 | `{h}時間{m}分` | `1時間03分` |

---

## 10. 状態の JSON 表現（UI・将来の共有 API 共通）

```json
{
  "status": "focused",
  "label": "集中傾向",
  "animation": "working_at_desk",
  "duration_seconds": 320,
  "confidence": 0.78,
  "approachability": "prefer_later",
  "approachability_label": "集中しているようです",
  "system_status": "running",
  "updated_at": "2026-07-26T14:32:10+09:00"
}
```

このスキーマには**座標・特徴量・イベント数を含めない**。共有目的で外に出せるのはこの形のみ。
