あなたは DeskMate プロジェクトの実装担当です。
作業ディレクトリ: C:\Users\yusei\dev\DeskMate

# 今回のタスク: Step 5 — pipeline 後半（estimator / rule / smoother / duration / approachability）

## 最初に必ず読むファイル

1. AGENTS.md                      … 実装ルール（最優先）
2. docs/implementation-plan.md    … 実装順序とテスト項目。**§3 の「Step 5」の節が今回の仕様**
3. docs/architecture.md           … 構造・クラス/関数シグネチャ・データ型・設定
4. docs/status-definition.md      … 状態・特徴量・閾値・表示文字列の**正典**
5. docs/requirements.md           … 目的と完成条件
6. docs/privacy-design.md         … プライバシー要件
7. docs/demo-scenario.md          … シナリオとデモ構成

## やること

docs/implementation-plan.md §3 の **Step 5** の節に書かれている内容を、そのとおりに実装する。

作成対象ファイル（目安。正確な一覧は implementation-plan.md の該当節を見ること）:
pipeline/estimator.py, pipeline/rule_estimator.py, pipeline/smoother.py, pipeline/duration.py, pipeline/approachability.py, tests/test_rule_estimator.py, tests/test_smoother.py, tests/test_duration.py, tests/test_approachability.py

同節の「テスト」の表に列挙されている項目を**すべて**テストとして実装する。
項目を減らしたり、まとめて 1 つにしたりしない。

実装が終わったら pytest を実行し、通ることを確認する。

## 守ること（全ステップ共通）

1. **設計書が唯一の正典。** 数値・クラス名・関数名・引数・戻り値・例外・設定キー・
   表示文字列は、すべて docs/ に書いてある。推測で決めない。
   矛盾を見つけたら AGENTS.md の優先順位に従う。
2. **閾値をコードにハードコードしない。** すべて AppConfig 経由で読む。
   docs/status-definition.md §5.2 の値と config/default.yaml の値は一致させる。
3. **プライバシー実装ルール（AGENTS.md §4）を必ず守る。** 特に:
   - StatusSnapshot に座標・特徴量のフィールドを足さない
   - share_window.py から FeatureFrame / DetailFrame / EventWindow を import しない
   - ログに座標を出さない
   - privacy.* / logging.log_features / debug.enabled の既定は false のまま
   - PrivacyViolationError を握り潰さない
   - mss / pyautogui / win32gui / requests / httpx / cv2 を import しない
4. **表示文言のルール**: 「離席中」「不在」「完全に安全」「完全に匿名」は使わない。
   日本語リテラルは src/deskmate/ui/labels.py にのみ置く。
5. **依存ライブラリを増やさない。** docs/architecture.md §1.4 の表が全部。
6. **numpy のベクトル演算で書く。** イベント配列を Python の for で回さない。
7. **設計書に無いファイルを作らない。** スクラッチ・メモ・サンプルを残さない。
8. **git commit / git push を実行しない。**
9. **このリポジトリの外を変更しない。** 特に EVENT_CAMERA と OpenEB は読み取りのみ。
   Voxel の処理は数式（docs/status-definition.md §4.6）から独立に実装し、
   参照リポジトリのコードをコピーしない。
10. **docs/ を書き換えない。** 判断が必要になったら docs/decisions.md に追記して続行する
    （AGENTS.md §5 の形式）。

## 完了したら報告すること

1. 作成・変更したファイルの一覧
2. pytest の結果（件数と成否。失敗があれば出力をそのまま貼る）
3. docs/implementation-plan.md に書かれた、このステップの完了条件のチェック結果
4. 設計書との差異があれば、その内容と理由
5. docs/decisions.md に追記した判断があれば、その ID

**テストが失敗しているのに成功したと報告しないこと。**
