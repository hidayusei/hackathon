# DeskMate デモシナリオ設計書

版: 1.0 / 最終更新: 2026-07-26

本書は、実カメラなしで DeskMate の全機能を確認・実演するための
ダミー入力シナリオ、デモ時系列、デモ画面の構成、実演台本、確認チェックリストを定義する。

数値の根拠と閾値は [status-definition.md](status-definition.md)、
実装インターフェースは [architecture.md](architecture.md) §17 を参照。

---

## 1. ダミーシナリオ 8 種

`src/deskmate/input/scenarios.py` の `SCENARIOS` に定義する。
`ScenarioSpec` の各フィールドは [architecture.md](architecture.md) §17 を参照。
座標は正規化（0.0–1.0）で書き、`RegionMap` の既定矩形（[status-definition.md](status-definition.md) §3）と対応させる。

### S1 `keyboard_steady` — キーボード付近で一定した細かな動き

| 項目 | 値 |
|------|-----|
| `label` | キーボード付近で一定した細かな動き |
| `base_rate_eps` | 1400.0 |
| `rate_jitter` | 0.15 |
| `burst_period_s` | None（連続） |
| `burst_duty` | 1.0 |
| `centers` | `((0.50, 0.82),)` |
| `center_switch_s` | 0.0 |
| `sigma_px` | 22.0 |
| `drift_px_per_s` | 1.0 |
| `positive_ratio` | 0.50 |
| `uniform_noise_ratio` | 0.03 |
| `rate_decay_per_s` | 1.0 |
| `dropout` | False |

**期待される状態**: 開始 5 秒後から `focused`（集中傾向）。
根拠: `rate_short ≈ 1400 >= focus_min_eps(400)`、keyboard 領域の share ≈ 0.96 >= 0.60、
bbox が狭く `area_short ≈ 0.06 <= 0.20`、`rate_cv_10s ≈ 0.07 <= 0.60`。
**実測: 確定状態は `focused` 92% / `working` 8%、30 秒で状態変化 1 回。**

### S2 `mouse_intermittent` — マウス付近で断続的な動き

| 項目 | 値 |
|------|-----|
| `label` | マウス付近で断続的な動き |
| `base_rate_eps` | 2000.0 |
| `rate_jitter` | 0.25 |
| `burst_period_s` | 1.0 |
| `burst_duty` | 0.60 |
| `centers` | `((0.86, 0.80),)` |
| `center_switch_s` | 0.0 |
| `sigma_px` | 17.0 |
| `drift_px_per_s` | 3.0 |
| `positive_ratio` | 0.52 |
| `uniform_noise_ratio` | 0.03 |
| `rate_decay_per_s` | 1.0 |
| `dropout` | False |

**期待される状態**: `working`（作業中）。
断続的な動きなので `rate_cv_10s ≈ 0.75` となり `focus_max_activity_cv`（0.60）を超え、
`focused` の条件を満たさない。領域別活動量はマウス側に偏るが、状態は `作業中` に留まる。
**実測: `working` 100%、30 秒で状態変化 0 回。**

これは「動きが入力デバイス付近にあっても、断続的なら集中傾向とは判定しない」ことを
示すデモ材料になる。`burst_period_s` は `features.ema_short_seconds`（1.0 秒）より短くすること
（§5.5 の制約）。長くすると休止中に `rate_short` が落ちて `short_break` が誤発火する。

### S3 `desk_wide_active` — 机上の広い範囲で活発な動き

| 項目 | 値 |
|------|-----|
| `label` | 机上の広い範囲で活発な動き |
| `base_rate_eps` | 4000.0 |
| `rate_jitter` | 0.30 |
| `burst_period_s` | None |
| `burst_duty` | 1.0 |
| `centers` | `((0.20, 0.35), (0.50, 0.45), (0.80, 0.30), (0.45, 0.75))` |
| `center_switch_s` | 1.2 |
| `sigma_px` | 60.0 |
| `drift_px_per_s` | 22.0 |
| `positive_ratio` | 0.50 |
| `uniform_noise_ratio` | 0.06 |
| `rate_decay_per_s` | 1.0 |
| `dropout` | False |

**期待される状態**: `organizing`（机上整理中）。
根拠: `rate_short ≈ 4000 >= active_eps(2000)`、中心が 1.2 秒ごとに切り替わるため
`speed_short ≈ 149 px/s`、`sigma_px=60` により `area_short ≈ 0.36 >= 0.25`、`cell_short ≈ 0.56 >= 0.25`。
**実測: `organizing` 100%、30 秒で状態変化 0 回。**

### S4 `activity_decay` — 活動量が徐々に減少

| 項目 | 値 |
|------|-----|
| `label` | 活動量が徐々に減少 |
| `base_rate_eps` | 2000.0（開始時） |
| `rate_jitter` | 0.15 |
| `burst_period_s` | None |
| `burst_duty` | 1.0 |
| `centers` | `((0.50, 0.80),)` |
| `center_switch_s` | 0.0 |
| `sigma_px` | 25.0 |
| `drift_px_per_s` | 2.0 |
| `positive_ratio` | 0.50 |
| `uniform_noise_ratio` | 0.03 |
| `rate_decay_per_s` | 0.88（1 秒ごとに 12% 減衰） |
| `dropout` | False |

**期待される状態**: `focused` → `short_break`（小休止）→ さらに続けば `no_motion` へ。
開始直後はキーボード領域の安定した動きなので `focused` になり、減衰につれて `short_break` へ移る。
**実測: `short_break` 58% / `focused` 34% / `working` 8%、30 秒で状態変化 2 回。**
2000 eps から 0.88^t で減衰し、約 9 秒で 600 eps（`break_max_eps`）を下回る。
このとき `rate_long` はまだ高いので `rate_short <= 0.40 * rate_long` が成立し `short_break` になる。
約 23 秒で 100 eps（`idle_eps`）を下回り、そこから 20 秒後（開始から約 43 秒）に `no_motion`。

`rate_decay_per_s` はシナリオ開始からの経過時間に対して適用し、シナリオ切替でリセットする。

### S5 `quiet` — 一定時間動きがない

| 項目 | 値 |
|------|-----|
| `label` | 一定時間動きがない |
| `base_rate_eps` | 20.0（微小なセンサノイズのみ） |
| `rate_jitter` | 0.50 |
| `burst_period_s` | None |
| `burst_duty` | 1.0 |
| `centers` | `((0.50, 0.50),)` |
| `center_switch_s` | 0.0 |
| `sigma_px` | 110.0 |
| `drift_px_per_s` | 0.0 |
| `positive_ratio` | 0.50 |
| `uniform_noise_ratio` | 1.00（全面ノイズ） |
| `rate_decay_per_s` | 1.0 |
| `dropout` | False |

**期待される状態**: 20 秒（`no_motion_seconds`）後に `no_motion`。
キャラクターは `looking_around` → 120 秒後に `sleeping`。
表示は「一定時間、動きを検出していません」→ 120 秒後に「静かな状態が続いています」。

**重要**: このシナリオでも「離席中」とは表示しない。

### S6 `rapid_change` — 状態が短時間で変化する

| 項目 | 値 |
|------|-----|
| `label` | 状態が短時間で変化する |
| `base_rate_eps` | 3000.0 |
| `rate_jitter` | 0.55 |
| `burst_period_s` | 1.5 |
| `burst_duty` | 0.5 |
| `centers` | `((0.50, 0.82), (0.20, 0.30), (0.85, 0.35), (0.50, 0.45))` |
| `center_switch_s` | 0.8 |
| `sigma_px` | 40.0 |
| `drift_px_per_s` | 45.0 |
| `positive_ratio` | 0.50 |
| `uniform_noise_ratio` | 0.05 |
| `rate_decay_per_s` | 1.0 |
| `dropout` | False |

**期待される状態**: `transition`（状態が変化中）。
根拠: 中心と活動量が短周期で入れ替わるため `change_score >= 0.55`。
`transition_max_seconds`（6 秒）を超えると強制再評価され、`organizing` か `working` に落ち着く。
これは「平滑化が効いていて、状態が乱高下しない」ことを見せるデモ材料になる。

### S7 `noise_burst` — ノイズが大量に発生する

| 項目 | 値 |
|------|-----|
| `label` | ノイズが大量に発生する |
| `base_rate_eps` | 6000.0 |
| `rate_jitter` | 0.60 |
| `burst_period_s` | None |
| `burst_duty` | 1.0 |
| `centers` | `((0.50, 0.50),)` |
| `center_switch_s` | 0.0 |
| `sigma_px` | 150.0 |
| `drift_px_per_s` | 0.0 |
| `positive_ratio` | 0.50 |
| `uniform_noise_ratio` | 0.92（ほぼ全面ランダム） |
| `rate_decay_per_s` | 1.0 |
| `dropout` | False |

**期待される状態**: 活動量としては `organizing` の条件を満たすが、
`noise_ratio > noise_ratio_threshold(0.79)` により信頼度が 0.6 倍される。
その結果、表示信頼度が `display_confidence_floor`(0.45) を下回り「状態不明」と表示される。

**実測**: `noise_ratio ≈ 0.84 > 0.79` により信頼度が 0.6 倍され、表示信頼度が 0.45 を下回るため
**表示ラベルは常に「状態不明」**になる（内部の `DeskStatus` は `working` / `unknown`）。
信頼度が `enter_confidence`(0.50) を割るので `organizing` への遷移自体も起きない。

**デモでの説明**: 「照明のちらつきなどで全面にイベントが出た場合、DeskMate は
断定せずに『状態不明』と表示します」。断定回避の設計を示す材料。

### S8 `dropout` — 入力が途切れる

| 項目 | 値 |
|------|-----|
| `label` | 入力が途切れる |
| `base_rate_eps` | 0.0 |
| `dropout` | True（`read()` が `None` を返し続ける） |
| その他 | 未使用 |

**期待される挙動**:

| 経過 | 内部 | 本人画面 | 共有画面 |
|------|------|---------|---------|
| 0–1.5 秒 | `SourceStatus.STREAMING` のまま | 直前の状態 | 直前の状態 |
| 1.5 秒〜 | `STALLED`。空窓を刻み `idle_seconds` が伸びる | 直前の状態（数秒で `no_motion` へ向かう） | 同左 |
| 5.0 秒〜 | `SystemStatus.NO_SIGNAL`。空窓生成を停止 | 「入力が途切れています」 | 「現在の状態を判定できません」 |
| 復帰後 | `STARTING` から再ウォームアップ | 「起動中です（推定準備中）」 | 「準備中です」 |

---

## 2. デモ画面（詳細画面）で見せる推定過程 10 項目

要求仕様の 10 項目と、詳細画面のパネルの対応。
[architecture.md](architecture.md) §14.2 のレイアウトと同一。

| # | 見せるもの | パネル | 具体的な表示 |
|---|-----------|-------|------------|
| 1 | イベントカメラが取得した点群 | `EventScatterPanel` | 間引き点群（最大 5,000 点）。正極性=暖色、負極性=寒色。領域矩形を薄く重ねる |
| 2 | 点群を時間窓ごとにまとめた表示 | `EventScatterPanel` ヘッダ | 「窓 #1234 / 200 ms / 284 events」。窓が進むごとに更新 |
| 3 | 検出した動きの範囲 | `MotionPanel` | bbox の矩形描画 + 「幅 64 px / 高さ 32 px / 面積比 0.020」 |
| 4 | 動きの中心位置 | `MotionPanel` | 重心マーカー（十字）+ 直近 20 窓の軌跡（薄い線） |
| 5 | 動きの速度または変化量 | `MotionPanel` | `centroid_speed` [px/s]、`event_rate_delta` [eps]、`change_score`（0–1 のバー） |
| 6 | 机上の領域ごとの活動量 | `RegionPanel` | 6 領域の横棒（share %）+ eps の数値 + 16×16 グリッドのヒートマップ |
| 7 | 抽出した特徴量 | `FeatureTablePanel` | `FeatureFrame.to_display_dict()` の全 22 項目 + 平滑値の主要 8 項目 |
| 8 | DeskMate が推定した状態 | `StatusHeader` | 状態名・信頼度・適用ルール ID（例 `R4_focused`）・`reason` 文字列・平滑化前の候補状態・得票数 |
| 9 | PC 上で動く DeskMate のキャラクター | `CharacterView`（96px） | 現在のアニメーション。状態変化時に遷移演出 |
| 10 | 状態の継続時間 | `StatusHeader` + `HistoryPanel` | 「集中傾向 5分12秒」+ 直近 5 分の帯グラフ（状態を色分け）+ eps 折れ線 |

画面上部の固定表示: `PRIVACY_NOTICE_JA` / `PRIVACY_CAVEAT_JA` / 入力ソース名 / `SourceStatus` /
`PipelineStats`（処理時間・破棄バッチ数・キュー深さ）。

**この 10 項目により、「書類の文字・スマホの画面・PC 画面の内容を一切表示せずに、
机上の動きだけから状態を推定している」ことを視覚的に示せる。**

---

## 3. デモモードの時系列 `DEMO_SEQUENCE`

`input/scenarios.py` に定義する。合計 **340 秒（5 分 40 秒）** で 1 周し、
`input.dummy.loop: true` なら先頭へ戻る。

各ステップは最小状態継続時間（3 秒）の 5 倍以上を確保し、状態が確実に確定するようにしてある。

| # | シナリオ | 長さ | 期待される確定状態の推移 | 見どころ |
|:-:|---------|:----:|------------------------|---------|
| 1 | `keyboard_steady` | 45 s | `unknown` →(約 3 s) `working` →(約 8 s) `focused` | ウォームアップ → 集中傾向の確定。キャラクターが `typing` |
| 2 | `mouse_intermittent` | 40 s | `working` | 領域別活動量がマウス側へ移る。断続的な動きは集中傾向と判定しないことを示す |
| 3 | `rapid_change` | 25 s | `transition` →(6 s 後) `organizing` または `working` | 変化スコアと強制再評価。キャラクターが `transitioning` |
| 4 | `desk_wide_active` | 40 s | `organizing` | bbox とグリッドヒートマップが広がる。キャラクターが `organizing_desk` |
| 5 | `activity_decay` | 45 s | `focused` →(約 10 s) `short_break` →(約 43 s) `no_motion` | 活動量の減衰カーブ。キャラクターが `drinking_tea` → 末尾で `looking_around` |
| 6 | `quiet` | 50 s | `no_motion`（20 s 後） | 「一定時間、動きを検出していません」。キャラクターが `looking_around` |
| 7 | `keyboard_steady` | 35 s | `no_motion` → `working` → `focused` | 復帰の様子。`no_motion` から `focused` へ直接飛ばず `working` を経由することを示す |
| 8 | `activity_decay` | 25 s | `working` → `short_break` | **共有画面で「話しかけやすそう」が出る区間**（後述） |
| 9 | `noise_burst` | 20 s | 表示ラベルが「状態不明」（内部は `working` / `unknown`） | 断定回避の設計 |
| 10 | `dropout` | 15 s | `no_signal` | 入力途絶時の挙動。「入力が途切れています」 |

```python
DEMO_SEQUENCE = (
    DemoStep("keyboard_steady",   45.0),
    DemoStep("mouse_intermittent",40.0),
    DemoStep("rapid_change",      25.0),
    DemoStep("desk_wide_active",  40.0),
    DemoStep("activity_decay",    45.0),
    DemoStep("quiet",             50.0),
    DemoStep("keyboard_steady",   35.0),
    DemoStep("activity_decay",    25.0),
    DemoStep("noise_burst",       20.0),
    DemoStep("dropout",           15.0),
)
```

### 3.1 「話しかけやすそう」が出る区間

ステップ 8（`activity_decay`、開始 320 秒地点）で `short_break` が 10 秒続くと、
[status-definition.md](status-definition.md) §8.1 のルール 4 が成立して `likely_ok` になる。

その直前（ステップ 7）に `focused` の確定履歴があるため、
ステップ 8 の前半で `working` に落ちた時点でもルール 5（直近 120 秒以内に `focused` があり、それが終了している）
が成立して `likely_ok` になりうる。

デモでは「集中していた作業が一段落したので、話しかけやすそうと出ています」と説明できる。
逆にステップ 1–2 の `focused` 継続中は `prefer_later`（集中しているようです）になる。

---

## 4. デモ実演台本（5 分想定）

審査員向け。画面は「詳細画面（メイン画面）」「共有画面（サブ画面 or 別ウィンドウ）」
「常駐ウィジェット（右下に重ねて表示）」の 3 つを同時に出しておく。

| 時間 | 操作 | 話す内容 |
|------|------|---------|
| 0:00 | 3 画面を並べて表示。デモモードで起動済み | 「机の上には書類やスマホがあります。DeskMate は RGB カメラを使わず、輝度変化だけを取るイベントカメラで状態を推定します」 |
| 0:20 | 詳細画面の点群を指す（ステップ 1 中） | 「これがイベントカメラの生の点群です。文字も画面の内容も写りません。動きがあった画素だけが光ります」 |
| 0:45 | 特徴量テーブルと領域別活動量を指す | 「これを 200 ms ごとの時間窓にまとめ、イベント数・重心・広がり・領域別の活動量といった特徴量を出します」 |
| 1:05 | 状態表示（`focused`）とキャラクターを指す | 「ルールベースで状態を推定します。今はキーボード付近に一定した動きが続いているので『集中傾向』。キャラクターがタイピングしています」 |
| 1:20 | 共有画面を指す | 「同僚が見るのはこちらだけです。点群も特徴量も出しません。今は『集中しているようです』と出ています」 |
| 1:35 | ステップ 3–4（`rapid_change` → `desk_wide_active`） | 「動きのパターンが急に変わると『状態が変化中』。机の広い範囲で動くと『机上整理中』になります。bbox とヒートマップが広がっているのが分かります」 |
| 2:30 | ステップ 5（`activity_decay`） | 「活動量が下がってくると『小休止』。キャラクターがお茶を飲みます」 |
| 3:00 | ステップ 6（`quiet`）＋共有画面 | 「20 秒動きがないと、こう出ます。**『離席中』とは言いません**。イベントカメラでは、席を外したのか、じっとしているだけなのかを区別できないからです。だから観測した事実だけを書いています」 |
| 3:40 | ステップ 8（`short_break`）＋共有画面 | 「集中が一段落して活動量が下がると『話しかけやすそう』。これは直接観測した値ではなく、直前に集中していたことと、今の活動量が低いことから導いた二次的な指標です」 |
| 4:10 | ステップ 9（`noise_burst`） | 「照明のちらつきなどでノイズが乗ると、信頼度を下げて『状態不明』にします。無理に断定しません」 |
| 4:30 | 停止ボタン → 共有停止ボタン | 「本人はいつでも推定と共有を止められます。止めている間、共有画面に直前の状態は残りません」 |
| 4:45 | 詳細画面上部の注意書きを指す | 「RGB は使わず、生データも外に出しません。ただし『イベントカメラだから完全に安全』とは言いません。イベントデータからも動きの形状は推測されうるので、そこは明記しています」 |

台本中の「離席中とは言わない」「完全に安全とは言わない」の 2 点は、
本システムの設計思想を示す部分なので必ず話すこと。

---

## 5. デモ前チェックリスト

実演の直前に確認する。DoD-3 の確認手順も兼ねる。

### 起動確認

- [ ] `python -m deskmate --demo` で起動する
- [ ] 常駐ウィジェットが画面右下に最前面で表示される
- [ ] ウィジェットをドラッグして移動できる
- [ ] ウィジェットを最小化 → 復元できる

### 詳細画面（10 項目）

- [ ] 1. 点群が表示され、更新されている
- [ ] 2. 窓番号・窓長・イベント数が表示されている
- [ ] 3. 動きの範囲（bbox）が矩形で表示されている
- [ ] 4. 重心マーカーと軌跡が表示されている
- [ ] 5. 速度 / 変化量 / change_score が表示されている
- [ ] 6. 領域別活動量とヒートマップが表示されている
- [ ] 7. 特徴量テーブルが全項目表示されている
- [ ] 8. 推定状態・信頼度・ルール ID・候補状態が表示されている
- [ ] 9. キャラクターが状態に応じて動いている
- [ ] 10. 継続時間と状態履歴の帯グラフが表示されている
- [ ] 上部に `PRIVACY_NOTICE_JA` と `PRIVACY_CAVEAT_JA` が表示されている

### 状態の網羅（デモモード 1 周 = 340 秒）

- [ ] `focused`（集中傾向）が出た
- [ ] `working`（作業中）が出た
- [ ] `organizing`（机上整理中）が出た
- [ ] `short_break`（小休止）が出た
- [ ] `transition`（状態が変化中）が出た
- [ ] `no_motion`（一定時間、動きを検出していません）が出た
- [ ] `unknown`（状態不明）が出た（ステップ 9）
- [ ] `no_signal`（入力が途切れています）が出た（ステップ 10）

### 共有画面

- [ ] 点群・特徴量・イベント数・領域名が一切表示されていない
- [ ] `likely_ok`（話しかけやすそう）が出た
- [ ] `prefer_later`（集中しているようです）が出た
- [ ] `undetermined`（判断できません）が出た
- [ ] 最終更新時刻が更新されている

### 停止機能

- [ ] 推定停止ボタンで停止し、本人画面が「推定を停止しています」になる
- [ ] 停止中、共有画面が「共有を停止しています」になり、直前の状態が残らない
- [ ] 再開すると「起動中です（推定準備中）」を経て通常表示に戻る
- [ ] 共有停止だけを行うと、本人画面は通常表示のまま共有画面だけが停止表示になる

### 安定性

- [ ] 340 秒 1 周する間、状態が 3 秒未満で切り替わる箇所がない
- [ ] CPU 使用率が 1 コア換算 10% 未満（詳細画面を閉じた状態）
- [ ] 5 分連続動作で例外が発生しない
- [ ] `data/` 配下に新しいファイルが生成されていない

---

## 6. デバッグモード

`debug.enabled: true`（または `--debug`）のとき、詳細画面に以下が表示される。

| 操作 | 動作 |
|------|------|
| シナリオ選択コンボボックス | 8 シナリオを手動で選択。`PipelineRunner.set_scenario()` |
| 状態固定ボタン（7 状態 + 解除） | 推定を無視して `DeskStatus` を固定。`PipelineRunner.force_status()`。キャラクター・共有画面の見え方を即座に確認できる |
| ウォームアップスキップ | `warmup_seconds` を 0 にする |
| 特徴量 CSV 保存 | `privacy.save_features: true` のときのみ有効。無効時はボタンを非活性にして理由をツールチップ表示 |

状態固定中は、詳細画面と常駐ウィジェットに「デバッグ: 状態固定中」を赤字で表示する。
**共有画面にはこの表示を出さない**（共有画面の表示項目を増やさないため）が、
固定された状態がそのまま共有画面に反映される。デモ本番では `debug.enabled: false` にすること。

---

## 7. トラブル時の代替デモ

| 症状 | 代替手段 |
|------|---------|
| 状態が期待どおりに遷移しない | デバッグモードで状態を手動固定し、キャラクターと 3 画面の見え方だけを見せる |
| 詳細画面が重い / カクつく | `ui.detail.max_preview_points` を 2000、`refresh_hz` を 5 に下げる |
| 全体が不安定 | `input.dummy.mode: manual` にして単一シナリオ（`keyboard_steady`）で固定表示する |
| 時間が足りない | ステップ 1 → 6 → 8 だけを見せる（集中傾向 → 動きなし → 話しかけやすそう）。デバッグモードのシナリオ選択で直接飛ぶ |
