# DeskMate 状態定義書

版: 2.0（Raspberry Pi 内完結・3 状態構成）/ 最終更新: 2026-07-27

本書は DeskMate の**状態・特徴量・閾値・アニメーション・表示文字列**の唯一の正典である。
実装で数値や文字列に迷ったら、本書の値をそのまま使うこと。本書と他文書が矛盾した場合、本書を優先する。

> **版 1.0 からの変更**: 状態を 7 種から 3 種へ削減。共有画面と話しかけやすさ指標を廃止。
> キャラクターを GIF に変更。休憩促し機能を追加。詳細は §11 の移行表を参照。

---

## 1. 表示文言の原則

イベントカメラは輝度変化しか観測しない。したがって次を守る。

1. **「離席中」は推定であって観測事実ではない。** イベントカメラは「席を外した」と
   「着席して静止している」を原理的に区別できない。表示名は「離席中」を採用する。
   **UI に言い訳めいた注記を常時出さない**（§10）。誤判定は閾値の調整で減らす。
   ただし「不在です」「席にいません」のような、人の所在を断定する言い回しは使わない。
2. **「作業しています」ではなく「集中」「非集中」** のように、断定を避けた短い名詞形を使う。
3. 「非集中」は否定的に響きうるため、UI 上では**サブテキストを添えない**（責める表現にしない）。
   休憩促し以外でユーザの行動を評価する文言を出さない。
4. 状態名の末尾に句点を付けない。継続時間は状態名とは別要素として表示する。
5. 「完全に安全」「完全に匿名」とは表現しない（[privacy-design.md](privacy-design.md) §5）。
6. **画面はスマートに保つ。** ユーザに見せるのは「状態名・継続時間・キャラクター」だけ。
   注意書き・免責・内部指標を常時表示しない。説明が必要な情報は詳細画面か README に置く。
   **キャラクターに性格を持たせることで面白さを出し、文章量では出さない。**

---

## 2. 抽象状態 DeskStatus

`src/deskmate/core/enums.py`

```python
class DeskStatus(str, Enum):
    AWAY    = "away"      # 離席中
    FOCUSED = "focused"   # 集中
    IDLE    = "idle"      # 非集中
```

**3 値のみ。** 版 1.0 にあった `working` / `organizing` / `short_break` / `transition` /
`no_motion` / `unknown` は廃止した。

| enum 値 | 日本語ラベル | 意味（観測ベース） | キャラクター |
|---------|------------|------------------|------------|
| `away` | 離席中 | 一定時間イベントがほとんど発生していない | 寝ている |
| `focused` | 集中 | キーボード / マウス周辺に限定された安定した動きが継続している | 走っている |
| `idle` | 非集中 | 活動はあるが集中の条件を満たさない。上記以外すべて | 座っている |

**低信頼度の降格表示は行わない。** 3 値なので、条件から外れたものはすべて `idle` に落ちる。
ノイズが多い場合も動きが空間的に散るため `focus_share` が下がり、自然に `idle` になる。
これが安全側の既定値として機能する。

### 2.1 システム状態 SystemStatus

推定結果ではなく、アプリの動作状況を表す。UI では DeskStatus より優先して表示する。

```python
class SystemStatus(str, Enum):
    STARTING  = "starting"    # 起動中・ウォームアップ中
    RUNNING   = "running"     # 正常稼働
    NO_SIGNAL = "no_signal"   # 入力が途切れている
    PAUSED    = "paused"      # ユーザが推定を停止した
    ERROR     = "error"       # エラー
```

版 1.0 の `SHARING_OFF` は共有画面の廃止に伴い削除。

| enum 値 | 表示文言 |
|---------|---------|
| `starting` | 起動中です |
| `running` | （DeskStatus のラベルを表示） |
| `no_signal` | 入力が途切れています |
| `paused` | 推定を停止しています |
| `error` | エラーが発生しています |

---

## 3. 休憩促し（break prompt）

集中が長く続いたら休憩を促す。**DeskStatus とは独立したフラグ**として扱う
（状態を増やさず、キャラクターの動作と 1 行のメッセージだけを差し替える）。

### 3.1 データ

```python
@dataclass(frozen=True, slots=True)
class BreakState:
    focus_streak_seconds: float   # 連続して focused だった秒数
    break_due: bool               # 休憩を促すべきか
    snoozed_until: float | None   # 「あとで」を押した場合の再提示時刻（monotonic）
```

### 3.2 パラメータ（`break.*`）

| キー | 既定値 | 説明 |
|------|-------|------|
| `enabled` | `true` | 休憩促し機能の有効 / 無効 |
| `after_seconds` | 1500.0 | **連続集中 25 分**で `break_due` を立てる |
| `reset_seconds` | 180.0 | `focused` 以外が 3 分続いたら連続集中を 0 に戻す |
| `snooze_seconds` | 300.0 | 「あとで」を押したら 5 分後に再提示 |
| `demo_scale` | 1.0 | デモ用の時間短縮係数。`0.02` で 25 分 → 30 秒 |

`after_seconds` と `reset_seconds` には `demo_scale` を掛ける。デモではこれを下げて実演する。

### 3.3 アルゴリズム

`src/deskmate/pipeline/break_tracker.py`

1. 確定状態が `focused` の窓では `focus_streak_seconds` に窓長を加算する。
2. `focused` 以外の窓では `non_focus_seconds` に窓長を加算する。
   `non_focus_seconds >= reset_seconds` になったら `focus_streak_seconds = 0`、
   `non_focus_seconds = 0`、`break_due = False` にリセットする。
   `focused` に戻ったら `non_focus_seconds` は 0 に戻す（連続集中は途切れさせない）。
3. `focus_streak_seconds >= after_seconds` かつスヌーズ中でなければ `break_due = True`。
4. `break_due` の間、キャラクターは `break` アニメーションになる（§4.2）。
5. ユーザが「あとで」を押すと `snoozed_until = now + snooze_seconds`、`break_due = False`。
   その時刻を過ぎ、まだ集中が続いていれば再び `break_due = True`。
6. 休憩が取られた（手順 2 のリセットが起きた）ら、次の 25 分に向けて数え直す。

**`break_due` は `SystemStatus.RUNNING` のときだけ立てる。** 停止中・入力途絶中は立てない。

---

## 4. キャラクター表示

### 4.1 AnimationId

```python
class AnimationId(str, Enum):
    RUNNING  = "running"    # 集中
    SITTING  = "sitting"    # 非集中
    SLEEPING = "sleeping"   # 離席中
    BREAK    = "break"      # 休憩促し
```

版 1.0 の 9 種は廃止。**この 4 種のみ。**

### 4.2 状態 → アニメーション

```python
def resolve_animation(status: DeskStatus, break_due: bool,
                      system_status: SystemStatus) -> AnimationId:
    ...
```

上から順に評価し、最初に一致したものを返す。

| 順位 | 条件 | AnimationId |
|:----:|------|-------------|
| 1 | `system_status != RUNNING` | `SITTING`（静かに座って待つ） |
| 2 | `break_due` が `True` | `BREAK` |
| 3 | `status == AWAY` | `SLEEPING` |
| 4 | `status == FOCUSED` | `RUNNING` |
| 5 | `status == IDLE` | `SITTING` |

### 4.3 GIF アセット

`assets/character/<animation_id>.gif`。**すでに作成済みでリポジトリに含まれている。**

| ファイル | フレーム数 | 1 周 | 内容 |
|---------|:---------:|:----:|------|
| `running.gif` | 10 | 900 ms | 脚を交互に動かして走る。尻尾を振り、土煙が出る |
| `sitting.gif` | 10 | 1600 ms | 座って呼吸。ときどき瞬きし、尻尾を揺らす |
| `sleeping.gif` | 10 | 2000 ms | 寝そべって目を閉じ、Z が昇る |
| `break.gif` | 10 | 1100 ms | 跳ねながら手を振り、「!」と「✦」が交互に出る |

仕様: **30×30 px、透過 GIF、`loop=0`（無限ループ）、9 色パレット**。

個別フレームは `assets/character/frames/<action>/00.png` 〜 `09.png` にある。
再生成・調整は `python tools/make_character_gifs.py`（Pillow が必要。**実行時には不要**）。

### 4.4 描画ルール

- **必ず最近傍補間で拡大する**（`Qt.TransformationMode.FastTransformation`）。
  滑らかな補間を使うとドット絵が崩れる。
- 拡大率は整数倍のみ（30px の 4 倍 = 120px、5 倍 = 150px、6 倍 = 180px）。
  非整数倍はピクセルが不均一になるため禁止。
- 背景は透過のまま。ウィジェットの背景色が透ける。
- アニメーションの切り替えは即座に行う。フェードなどの演出は入れない
  （ドット絵の質感を保つため）。

### 4.5 状態ごとのアクセント色

`src/deskmate/ui/theme.py` の `STATUS_COLORS`。

| DeskStatus | 色 | 意図 |
|------------|----|------|
| `focused` | `#5B8DEF`（青） | 集中 |
| `idle` | `#4FB3A9`（青緑） | 通常 |
| `away` | `#6B7280`（灰） | 動きなし |
| （休憩促し） | `#E8A33D`（橙） | `break_due` のときヘッダとバナーに使う |

---

## 5. 特徴量

### 5.1 単位と記号

| 記号 | 意味 | 単位 |
|------|------|------|
| `W` | 時間窓長 | 秒（既定 0.2） |
| `N` | 窓内イベント総数 | 件 |
| `eps` | 活動量 = `N / W` | 件/秒 |
| `w_px`, `h_px` | センサ解像度 | px（**320×320** = Prophesee GenX320） |

3 状態化にあたり、版 1.0 の特徴量のうち**推定に使わないものを削除**した。
詳細画面の表示には引き続き全項目を出す。

### 5.2 全体特徴量 GlobalFeatures

| フィールド名 | 型 | 定義 | 推定に使用 |
|-------------|----|------|:---------:|
| `event_count` | `int` | 窓内イベント総数 `N` | |
| `positive_count` / `negative_count` | `int` | 極性別の件数 | |
| `positive_ratio` | `float` | `positive_count / N`。`N == 0` なら `0.5` | |
| `event_rate_eps` | `float` | `N / W` | ○ |
| `centroid_x` / `centroid_y` | `float` | `mean(x)` / `mean(y)`。`N == 0` なら直前窓の値 | |
| `centroid_shift` | `float` | 直前窓の重心との距離。初回は `0.0` | |
| `centroid_speed` | `float` | `centroid_shift / W` | |
| `var_x` / `var_y` | `float` | 分散。`N < 2` なら `0.0` | |
| `spatial_std` | `float` | `sqrt(var_x + var_y)` | |
| `bbox_width` / `bbox_height` | `float` | パーセンタイル幅（`q = features.bbox_percentile`、既定 0.05）。`N < 10` なら `0.0` | |
| `bbox_area_ratio` | `float` | `bbox_width * bbox_height / (w_px * h_px)` | ○ |
| `active_cell_ratio` | `float` | 活性グリッドセル比率（16×16） | |
| `event_count_delta` / `event_rate_delta` | – | 直前窓との差 | |
| `activity_ratio_10s` | `float` | 直近 10 秒で活動していた窓の割合 | |
| `idle_seconds` | `float` | `event_rate_eps < idle_eps` の連続秒数 | ○ |
| `active_seconds` | `float` | `event_rate_eps >= idle_eps` の連続秒数 | ○ |
| `noise_ratio` | `float` | `1.0 - (上位 10% の活性セルが占めるイベント比率)` | |

### 5.3 領域別特徴量 RegionFeatures

領域定義は版 1.0 から変更なし（keyboard / mouse / center / left / right / other、
正規化矩形、設定順で先勝ち）。各領域について `event_count` / `event_rate_eps` /
`share` / `centroid_x` / `centroid_y` / `active_cell_ratio` を算出する。

推定に使うのは `share` のみ（`focus_regions` の合計 = `focus_share`）。

### 5.4 平滑値 SmoothedFeatures

EMA の係数は `alpha = 1 - exp(-W / tau)`。

| フィールド名 | tau | 推定に使用 |
|-------------|-----|:---------:|
| `rate_short` | `features.ema_short_seconds`（1.0） | ○ |
| `rate_long` | `features.ema_long_seconds`（10.0） | |
| `area_short` | 1.0 | ○ |
| `speed_short` | 1.0 | |
| `cell_short` | 1.0 | |
| `share_short[region]` | 1.0 | ○ |
| `rate_cv_10s` | – | 直近 10 秒の変動係数。`mean <= 0` なら `999.0` | ○ |
| `idle_seconds` / `active_seconds` | – | 素通し | ○ |
| `elapsed_seconds` | – | 開始からの経過秒 | |

版 1.0 の `change_score` は `transition` 状態の廃止に伴い**削除**。

---

## 6. 推定ルール

`src/deskmate/pipeline/rule_estimator.py`

### 6.1 評価順序

上から順に評価し、**最初に条件を満たしたものを候補状態とする**。

| 順位 | 状態 | 条件 |
|:----:|------|------|
| 1 | `away` | `idle_seconds >= away_seconds` |
| 2 | `focused` | `rate_short >= focus_min_eps` かつ `focus_share >= focus_region_share` かつ `area_short <= focus_max_bbox_area_ratio` かつ `rate_cv_10s <= focus_max_activity_cv` かつ `active_seconds >= focus_min_seconds` |
| 3 | `idle` | 上記以外すべて（フォールバック。必ずここに落ちる） |

`focus_share = sum(share_short[r] for r in estimation.focus_regions)`

### 6.2 閾値（`estimation.*`）

**320×320 / GenX320 前提の初期値。実機未検証**（[architecture.md](architecture.md) §22 の R1）。
実測後は本表と `config/default.yaml` の**両方**を同時に更新すること。

| キー | 既定値 | 単位 | 説明 |
|------|-------|------|------|
| `idle_eps` | 100.0 | 件/秒 | これ未満を「動きなし」とみなす |
| `away_seconds` | 30.0 | 秒 | 動きなしがこの時間続くと `away`。版 1.0 の 20 秒から延長（誤って離席と判定しにくくするため） |
| `focus_min_eps` | 400.0 | 件/秒 | `focused` の活動量下限 |
| `high_activity_eps` | 5000.0 | 件/秒 | 信頼度計算の上限基準 |
| `focus_regions` | `["keyboard", "mouse"]` | – | 集中判定に使う領域 |
| `focus_region_share` | 0.60 | 0–1 | 入力デバイス領域のイベント占有率下限 |
| `focus_min_seconds` | 5.0 | 秒 | 連続活動の下限 |
| `focus_max_bbox_area_ratio` | 0.20 | 0–1 | 動きの広がり上限（§6.4） |
| `focus_max_activity_cv` | 0.60 | – | 活動量の変動係数上限（安定していること） |
| `warmup_seconds` | 3.0 | 秒 | 起動後この時間は `SystemStatus.STARTING` |

削除した閾値: `low_activity_eps` / `active_eps` / `break_max_eps` / `break_decay_ratio` /
`organizing_*` / `transition_*` / `noise_ratio_threshold` / `no_motion_seconds`。

### 6.3 信頼度 confidence

```python
def margin_confidence(value: float, threshold: float, span: float) -> float:
    m = (value - threshold) / span if span > 0 else 0.0
    return float(min(0.95, max(0.30, 0.5 + 0.45 * min(1.0, max(0.0, m)))))
```

| 状態 | 信頼度の式 |
|------|-----------|
| `away` | `margin_confidence(idle_seconds, away_seconds, away_seconds)` |
| `focused` | `min(margin_confidence(focus_share, focus_region_share, 1.0 - focus_region_share), margin_confidence(active_seconds, focus_min_seconds, focus_min_seconds))` |
| `idle` | `margin_confidence(rate_short, idle_eps, high_activity_eps - idle_eps)` |

信頼度は詳細画面にのみ表示する。ウィジェットには出さない（3 値では意味が薄いため）。

### 6.4 面積閾値の実測根拠

ダミー入力での `area_short` の実測分布（320×320、窓 200 ms、`bbox_percentile = 0.05`）。

| 動きの種類 | p5 | 中央値 | p95 |
|-----------|-----|-------|-----|
| キーボード付近の細かい動き | 0.058 | 0.064 | 0.077 |
| マウス付近の断続的な動き | 0.020 | 0.048 | 0.138 |
| 机上の広い動き | 0.286 | 0.363 | 0.437 |

狭い動き（最大 0.138）と広い動き（最小 0.286）の間の空白帯に
`focus_max_bbox_area_ratio = 0.20` を置いている。

**`bbox_percentile` は 0.05 を下回らせないこと。** 0.02 では 1 窓 280 件程度のイベントに
混ざる一様ノイズを削り切れず、`area_short` が閾値を跨いで状態が振動する。

---

## 7. 平滑化

`src/deskmate/pipeline/smoother.py`

### 7.1 パラメータ（`smoothing.*`）

| キー | 既定値 | 説明 |
|------|-------|------|
| `vote_window_size` | 5 | 直近この件数の候補で多数決（200 ms × 5 = 1 秒） |
| `vote_min_count` | 3 | 遷移に必要な最小得票数 |
| `enter_confidence` | 0.50 | 遷移に必要な平均信頼度 |
| `exit_confidence` | 0.35 | 現状態の信頼度がこれを下回ると得票条件を 1 緩和 |
| `confidence_ema_seconds` | 2.0 | 表示用信頼度の EMA 時定数 |
| `min_dwell_seconds.default` | 3.0 | 最小状態継続時間 |
| `min_dwell_seconds.away` | 5.0 | 〃（`away`） |

### 7.2 アルゴリズム

版 1.0 と同一。ただし**遷移表は廃止**する（3 状態では相互遷移をすべて許可してよい）。

1. 候補をリングバッファに push。満たない間は現状態を維持（初期状態は `idle`）。
2. 多数決で最多候補 `top` と得票数 `n`、平均信頼度 `c_avg` を求める。
   同数の場合は §6.1 の評価順位が上のものを選ぶ。
3. `top == current` なら維持。
4. `top != current` のとき、以下をすべて満たせば遷移:
   - `elapsed(current) >= min_dwell_seconds[current]`
   - `n >= vote_min_count`（現状態の信頼度 < `exit_confidence` なら `n >= vote_min_count - 1`）
   - `c_avg >= enter_confidence`
5. `away` への遷移だけは例外で、`idle_seconds >= away_seconds` が成立していれば
   最小継続時間と多数決を無視して即座に遷移する。

**`min_dwell_seconds` により、状態が 3 秒未満で切り替わることはない。**

---

## 8. 表示文字列

`src/deskmate/ui/labels.py` に集約する。日本語リテラルを他ファイルに置かないこと。

```python
STATUS_LABELS_JA: dict[DeskStatus, str] = {
    DeskStatus.AWAY:    "離席中",
    DeskStatus.FOCUSED: "集中",
    DeskStatus.IDLE:    "非集中",
}

SYSTEM_LABELS_JA: dict[SystemStatus, str] = {
    SystemStatus.STARTING:  "起動中です",
    SystemStatus.RUNNING:   "",
    SystemStatus.NO_SIGNAL: "入力が途切れています",
    SystemStatus.PAUSED:    "推定を停止しています",
    SystemStatus.ERROR:     "エラーが発生しています",
}

BREAK_TITLE_JA   = "そろそろ休憩しませんか"
BREAK_BODY_JA    = "{duration} 集中しています"      # 例: 25分12秒 集中しています
BREAK_SNOOZE_JA  = "あとで"
BREAK_TAKEN_JA   = "休憩する"

DETAIL_BUTTON_JA = "詳細"
PAUSE_BUTTON_JA  = "停止"
RESUME_BUTTON_JA = "再開"
QUIT_BUTTON_JA   = "終了"
WINDOW_TITLE_JA  = "DeskMate"
DETAIL_TITLE_JA  = "DeskMate 詳細"

PRIVACY_NOTICE_JA = "RGB映像は使用していません / データはこの端末の外に出ません"
PRIVACY_CAVEAT_JA = "イベントデータからも動きの形状が推測される可能性があります"
```

ラベル解決:

```python
def resolve_label(status: DeskStatus,
                  system_status: SystemStatus = SystemStatus.RUNNING) -> str:
    """system_status が RUNNING 以外ならそのラベル、RUNNING なら状態ラベルを返す。"""
```

継続時間の書式（`format_duration(seconds: float) -> str`）:

| 範囲 | 書式 | 例 |
|------|------|-----|
| < 60 秒 | `{n}秒` | `42秒` |
| < 60 分 | `{m}分{s}秒` | `5分12秒` |
| それ以上 | `{h}時間{m}分` | `1時間03分` |

---

## 9. 状態の JSON 表現

```json
{
  "status": "focused",
  "label": "集中",
  "animation": "running",
  "duration_seconds": 320,
  "focus_streak_seconds": 1520,
  "break_due": true,
  "system_status": "running",
  "updated_at": "2026-07-27T14:32:10+09:00"
}
```

座標・特徴量・イベント数を含めないこと。将来 EXT で共有機能を作る場合、
外に出せるのはこの形のみとする。

---

## 10. 「離席中」の扱い

表示名は「離席中」を採用したが、**これは推定であり観測事実ではない**。
イベントカメラは「席を外した」と「着席して静止している」を区別できない。

### 10.1 UI では注記しない

**この限界を UI に常時表示してはならない。** 言い訳めいた注記は画面を汚し、
体験を鈍くする。代わりに次で対処する。

| 手段 | 内容 |
|------|------|
| 閾値 | `away_seconds = 30.0`。短時間の静止では `away` にしない |
| 最小継続時間 | `min_dwell_seconds.away = 5.0`。頻繁な出入りを抑える |
| 復帰の速さ | 動きが戻れば次の窓で `idle` に戻る（`away` からの復帰に遅延を入れない） |
| 記録 | 限界の説明は本書と README にのみ書く。画面には出さない |

### 10.2 表現の禁止

ログ・ドキュメント・UI のいずれでも次を書かない。

- 「不在」「在席していない」「席にいません」— 人の所在を断定する表現
- 「サボっている」「離席が多い」— 行動を評価する表現

「動きを検出していない」と書く。

## 11. 版 1.0 からの移行表

Codex が既存実装を改修する際の対応表。

| 版 1.0 | 版 2.0 |
|--------|--------|
| `DeskStatus.WORKING` | `DeskStatus.IDLE` に統合 |
| `DeskStatus.ORGANIZING` | `DeskStatus.IDLE` に統合 |
| `DeskStatus.SHORT_BREAK` | `DeskStatus.IDLE` に統合 |
| `DeskStatus.TRANSITION` | 廃止 |
| `DeskStatus.NO_MOTION` | `DeskStatus.AWAY` に改名 |
| `DeskStatus.UNKNOWN` | 廃止（`IDLE` がフォールバック） |
| `SystemStatus.SHARING_OFF` | 廃止 |
| `Approachability` 全体 | 廃止（共有画面とともに削除） |
| `AnimationId` 9 種 | `RUNNING` / `SITTING` / `SLEEPING` / `BREAK` の 4 種 |
| `ShapeCharacterRenderer` | `GifCharacterRenderer` に置換 |
| `change_score` | 廃止 |
| `TRANSITION_TABLE` | 廃止 |
| `ui/share_window.py` | 削除 |
| `pipeline/approachability.py` | 削除 |
| `QUIET_VARIANTS_JA` / `STATUS_LABELS_SHORT_JA` | 廃止（ラベルは 1 種類のみ） |
| `display_confidence_floor` | 廃止（降格表示をしない） |
| – | `pipeline/break_tracker.py` を新規追加 |
| – | `input/metavision_source.py` を新規追加 |
