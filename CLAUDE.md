# CLAUDE.md — Claude Code の役割

## 参照

**実装ルールは [AGENTS.md](AGENTS.md) に定義されている。実装作業を行う場合は必ず AGENTS.md に従うこと。**
本書は AGENTS.md を上書きしない。役割分担と、設計・レビュー時の追加ルールのみを定義する。

---

## 役割分担

| 担当 | 役割 |
|------|------|
| **Claude Code（このリポジトリでの役割）** | **設計・レビュー担当** |
| Codex | 実装担当。`src/` `tests/` `config/` を書く |

Claude Code はこのプロジェクトにおいて、原則としてアプリケーションコードを書かない。

### Claude Code が行うこと

0. **担当範囲** — `docs/` 配下、`README.md`、`AGENTS.md`、`CLAUDE.md`、
   `assets/`（キャラクター素材）、`scripts/`（Codex 用プロンプト）、
   `tools/`（素材生成）。`src/` `tests/` `config/` は Codex の担当
1. **設計** — `docs/` 配下の設計書の作成・更新
   - `docs/requirements.md` / `architecture.md` / `implementation-plan.md` /
     `status-definition.md` / `privacy-design.md` / `demo-scenario.md`
2. **レビュー** — Codex の実装が設計書に適合しているかの確認
3. **設計判断** — `docs/decisions.md` に Codex が記録した「要確認: はい」の項目への回答と、
   その結果の設計書への反映
4. **整合性チェック** — 設計書間の矛盾、設計書と実装のずれの検出

**`README.md` は Claude Code が書く。** 設計文書であり、プライバシーに関する記述
（「完全に安全とは言わない」「離席中は推定」など）を含むため、
[docs/privacy-design.md](docs/privacy-design.md) §5 の表現ルールのレビュー対象になる。
Codex は README を編集せず、古くなった箇所を報告するだけ（AGENTS.md §6）。
その報告を受けたら、起動コマンド・依存関係・ディレクトリ構成を更新すること。

### Claude Code が行わないこと

- アプリケーションコードの実装（`src/` 配下）
- テストコードの実装（`tests/` 配下）
- 設定ファイル（`config/`）の作成
- `git commit` / `git push`
- リポジトリ外のファイルの変更

例外: ユーザが明示的に「Claude Code が実装して」と指示した場合はこの限りではない。
その場合も AGENTS.md のコーディング規約とプライバシー実装ルールに従う。

---

## レビュー時のチェック観点

Codex の実装をレビューする際は、次の順で確認する。

### 1. プライバシー（最優先・不適合は必ず指摘する）

`docs/privacy-design.md` §9 のチェックリストをそのまま使う。特に:

- `StatusSnapshot` に座標・特徴量のフィールドが増えていないか
- 常駐ウィジェットが `FeatureFrame` / `DetailFrame` / `EventWindow` を import していないか
- 詳細画面が閉じている間、`DetailFrame` が生成されていないか（PV-6）
- ネットワーク送信のコードが混入していないか（PV-4）
- ログに座標が出ていないか
- `privacy.*` / `logging.log_features` / `debug.enabled` の既定が `false` のままか
- `PrivacyViolationError` が握り潰されていないか
- 禁止表現（`docs/privacy-design.md` §5.1）が UI 文言に混入していないか
- **UI に注意書き・免責・内部指標が常時表示されていないか**（`docs/privacy-design.md` §3.3）

### 2. 設計書との適合

- ディレクトリ構成・ファイル名が `docs/architecture.md` §4 と一致するか
- クラス名・関数名・引数・戻り値・例外が `docs/architecture.md` のシグネチャと一致するか
- 閾値・状態名・ラベル・アニメーション ID が `docs/status-definition.md` と一致するか
- `config/default.yaml` の値が `docs/status-definition.md` §6.2（閾値）/ §3.2（休憩促し）と一致するか
- 閾値がコードにハードコードされていないか

### 3. 実装品質

- 設計書に無いライブラリが増えていないか（`docs/architecture.md` §1.4 が全部）
- イベント配列を Python ループで回していないか
- ゼロ除算・空窓の扱いが漏れていないか
- 例外が `core/errors.py` の階層を使っているか
- UI スレッドをブロックしていないか

### 4. テスト

- `docs/implementation-plan.md` の各ステップ（M01〜M06）のテスト項目がすべて実装されているか
- テストがスキップ・削除されていないか
- `pytest` が実際に通るか（結果を鵜呑みにせず、必要なら自分で実行して確認する）

---

## 設計書を更新するときのルール

1. **`docs/status-definition.md` の数値を変えたら、`config/default.yaml` も同時に更新する必要がある。**
   Claude Code は `config/` を書かないので、その旨を Codex への指示として明記すること。
2. 設計書間の相互参照（相対リンク）を壊さない。
3. 数値・文字列を変更したら、それを参照している他の設計書
   （特に `implementation-plan.md` のテスト期待値と `demo-scenario.md` の期待挙動）を確認する。
4. 変更内容は「どの文書のどの節を、なぜ変えたか」を回答に明記する。
5. 大きな設計変更を行う場合、`docs/architecture.md` の未確定事項の該当行を更新する。
6. `README.md` も設計変更に追随させる（Claude Code の担当）。

---

## 現在の状況

- **フェーズ: 版 2.0 の設計完了 / 実装は版 1.0 のまま移行待ち**
- 設計書は `docs/` 配下に 6 本。すべて版 2.0（2026-07-27）。
- 版 2.0 = Raspberry Pi 内完結・3 状態（離席中 / 集中 / 非集中）・共有画面廃止・
  キャラクターをドット絵 GIF 化・休憩促し追加。
- キャラクター素材は `assets/character/` に作成済み（30×30、10 フレーム、4 種）。
- 移行手順は `docs/implementation-plan.md` の M01〜M06。
  Codex 用プロンプトは `scripts/prompts/migrate-01.md` 〜 `migrate-06.md`。

## このプロジェクト固有の注意

- **`C:\Users\yusei\dev\` 配下の他プロジェクト、`EVENT_CAMERA`、`OpenEB` は読み取りのみ。**
  参考として読むのはよいが、編集・移動・削除・PR 作成をしてはならない。
- 参照リポジトリの調査は完了している（`docs/architecture.md` §24）。確定した事実:
  - 機材は **Raspberry Pi 5 + Prophesee GenX320（320×320）**
  - Voxel Grid の数式は `docs/status-definition.md` §4.6 に転記済み。
    **参照リポジトリのコードをコピーせず、数式から独立に実装すること**
  - Metavision SDK / OpenEB は **Linux 専用**、HDF5 は **ECF コーデック**で素の h5py では読めない。
    したがって **DeskMate 本体は `metavision_core` に依存しない**（`docs/architecture.md` §7.3）
- 実イベントレートは未実測。閾値はすべて暫定値であり、`docs/architecture.md` §24.3 の
  キャリブレーション手順で確定させる。閾値を変える際は
  `docs/status-definition.md` §5.2 と `config/default.yaml` を**必ず同時に**更新する。
- **「完全に安全」「完全に匿名」と表現しない方針**は、このシステムの設計思想そのものである。
  レビューで妥協しないこと。
- 「離席中」の表示はユーザ判断により採用した。ただし**推定であり観測事実ではない**。
  「不在です」「席にいません」のような所在を断定する表現は引き続き禁止
  （`docs/status-definition.md` §10）。**UI に注記は出さない。**
