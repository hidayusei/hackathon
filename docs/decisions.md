## D-001: 起動時にイベント点群とキャラクターを表示する CLI モード
- 日付: 2026-07-31
- 背景: 設計書ではイベント点群を右クリックで開く詳細画面に表示するが、デモ時に起動直後からイベント点群とキャラクターを同時表示する方法が定義されていない。
- 選択肢: A: 詳細画面を起動時に開く CLI オプションを追加する / B: 常駐ウィジェットへ点群を追加する
- 決定: A
- 理由: 既存の詳細購読を再利用でき、常駐ウィジェットが L3 データだけを扱う PV-6 の境界を維持できるため。
- 影響範囲: `src/deskmate/__main__.py`、`src/deskmate/app.py`、`src/deskmate/ui/detail_window.py`
- 要確認: 設計担当（Claude Code）に確認が必要か（はい）

## D-004: Metavision 実機では手元領域の条件を無効化する
- 日付: 2026-08-01
- 背景: 再収録した `2.mp4` のタイピング中は `focus_share=0.11〜0.27`、`area_short=0.61〜0.71`、`rate_cv_10s=0.48〜2.78` であり、既定のダミー用条件（0.60 / 0.20 / 0.60）を満たさなかった。カメラ配置上、手元の絶対位置を集中条件にしない方針がユーザから指定された。その後、離席後の約 5,700 eps の残差ノイズでも集中になることが実機確認された。
- 選択肢: A: Metavision 専用プロファイルで位置条件を無効化し、広がりと変動幅を実測値へ合わせる / B: 全入力共通の閾値を変更する
- 決定: A
- 理由: 実機では活動量と継続性を中心に判定しつつ、ダミー入力のマウス断続・机上広域シナリオの既存判定を維持するため。実機の無活動境界を 10,000 eps、集中下限を 15,000 eps とし、離席後の残差ノイズを集中から除外する。
- 影響範囲: `config/default.yaml`、`src/deskmate/config/schema.py`、`src/deskmate/pipeline/runner.py`、`tests/test_config.py`、`tests/test_runner.py`
- 要確認: 設計担当（Claude Code）に確認が必要か（はい）

## D-002: 詳細表示の開始時に静止背景を10秒間学習して減算する
- 日付: 2026-08-01
- 背景: 実機では静止中にも多数の背景イベントが発生し、表示点数の制限だけでは動きとの区別がつかなかった。設計書には起動時キャリブレーションと背景減算が定義されていない。
- 選択肢: A: 詳細表示内で画素・極性別の平均イベント数を学習して表示から減算する / B: 推定入力そのものから減算する
- 決定: A
- 理由: ユーザ指定の10秒キャリブレーションを実現しつつ、未検証の背景モデルが状態推定と既存閾値へ影響することを避けるため。集計値は詳細画面の寿命内だけ保持し、保存しない。
- 影響範囲: `config/default.yaml`、`src/deskmate/config/schema.py`、`src/deskmate/ui/labels.py`、`src/deskmate/ui/detail_window.py`、`src/deskmate/ui/panels/event_scatter_panel.py`、`tests/test_ui_smoke.py`
- 要確認: 設計担当（Claude Code）に確認が必要か（はい）

## D-003: Metavision 推定入力にも背景減算と残差閾値を適用する
- 日付: 2026-08-01
- 背景: `2.mp4` では背景減算後の静止が約 1.5 万 eps、タイピングが約 2.1〜2.4 万 eps だったが、減算が表示専用のため推定状態には反映されなかった。1.8 万 eps での試行では動作中も残差が 0 件になる窓があり、連続活動時間がリセットされた。
- 選択肢: A: Metavision 入力だけ推定前に背景減算し、1.5 万 eps 相当の残差を背景として除外する / B: 生イベント特徴量の既存閾値だけを変更する
- 決定: A
- 理由: 生イベントは静止時とタイピング時の双方で 10 万 eps を超え、既存のイベント数閾値だけでは区別できないため。推定には残差のうち密度が高い画素を優先して残し、動きの空間特徴を維持する。1.5 万 eps は実測した静止残差の上端付近で、弱いタイピング窓を 0 件にしにくい値として再調整した。詳細表示には 1.5 万 eps の除外前（画素別背景減算後）のイベントを使い、手の動きを視認しやすくする。
- 影響範囲: `config/default.yaml`、`src/deskmate/config/schema.py`、`src/deskmate/core/types.py`、`src/deskmate/pipeline/features.py`、`src/deskmate/pipeline/runner.py`、`src/deskmate/ui/detail_window.py`、`src/deskmate/ui/panels/event_scatter_panel.py`
- 要確認: 設計担当（Claude Code）に確認が必要か（はい）

## D-005: UDP 有効時にも真となるプライバシー表示へ変更する
- 日付: 2026-08-01
- 背景: `status-definition.md` の既存文言「データはこの端末の外に出ません」は、UDP 生イベント転送を有効にした場合に事実ではなくなる。今回の編集許可に `status-definition.md` は含まれていない。
- 選択肢: A: 実装と許可対象のプライバシー設計だけを常に真となる文言へ変更する / B: UDP 有効時にも旧文言を表示する
- 決定: A
- 理由: 誤ったプライバシー表示を避ける、より制限的な選択であるため。
- 影響範囲: `src/deskmate/ui/labels.py`、`docs/privacy-design.md`、`docs/architecture.md`
- 要確認: 設計担当（Claude Code）に確認が必要か（はい。`docs/status-definition.md` の正典文言更新が必要）
