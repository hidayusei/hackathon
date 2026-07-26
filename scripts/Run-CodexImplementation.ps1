<#
.SYNOPSIS
    DeskMate を Codex で一括実装させるためのドライバスクリプト。

.DESCRIPTION
    docs/implementation-plan.md の Step 0〜14 を順に Codex へ投げ、
    各ステップの後に pytest を実行して、失敗したらそこで止める。

    Codex CLI が PATH にあれば自動実行する。無ければプロンプトファイルだけを
    scripts/prompts/ に生成するので、Codex の IDE 拡張や Web にそのまま貼れる。

    設計書の数値や仕様はプロンプトに埋め込まない。プロンプトは docs/ を
    「読め」と指示するだけにしてある（設計書を唯一の正典に保つため）。

.PARAMETER Steps
    実行するステップ。"0-14"（範囲）、"3,4,5"（列挙）、"7"（単一）。既定は "0-14"。

.PARAMETER PromptsOnly
    Codex を起動せず、プロンプトファイルの生成だけを行う。

.PARAMETER Resume
    前回の進捗（scripts/.codex-progress.json）の続きから再開する。

.PARAMETER Model
    Codex に渡すモデル名。未指定なら Codex の既定値を使う。

.PARAMETER SkipTests
    各ステップ後の pytest をスキップする（デバッグ用。通常は使わない）。

.PARAMETER CodexCommand
    Codex CLI の実行ファイル名。既定 "codex"。

.EXAMPLE
    .\scripts\Run-CodexImplementation.ps1 -PromptsOnly
    プロンプトを全部作るだけ。まずこれで内容を確認する。

.EXAMPLE
    .\scripts\Run-CodexImplementation.ps1 -Steps 0-2
    Step 0〜2 だけ実装させる。

.EXAMPLE
    .\scripts\Run-CodexImplementation.ps1 -Resume
    途中で止まったところから再開する。

.NOTES
    このスクリプトは git commit / push を一切行わない。
    リポジトリ外のファイルにも触れない。
#>

[CmdletBinding()]
param(
    [string]$Steps = "0-14",
    [switch]$PromptsOnly,
    [switch]$Resume,
    [string]$Model = "",
    [switch]$SkipTests,
    [string]$CodexCommand = "codex"
)

$ErrorActionPreference = "Stop"

# ============================================================================
# パス
# ============================================================================
$ScriptDir    = $PSScriptRoot
$Root         = Split-Path -Parent $ScriptDir
$DocsDir      = Join-Path $Root "docs"
$PromptDir    = Join-Path $ScriptDir "prompts"
$LogDir       = Join-Path $ScriptDir "logs"
$ProgressFile = Join-Path $ScriptDir ".codex-progress.json"
$VenvPython   = Join-Path $Root ".venv\Scripts\python.exe"

# ============================================================================
# ステップ定義（docs/implementation-plan.md §2 と一対一で対応させること）
# ============================================================================
$StepTable = @(
    @{ Id = 0;  Name = "環境構築・雛形";
       Files = "pyproject.toml, requirements.txt, .gitignore, assets/character/README.md, data/.gitkeep";
       Tests = "" },

    @{ Id = 1;  Name = "core（enums / types / errors / clock）";
       Files = "src/deskmate/__init__.py, src/deskmate/core/__init__.py, core/enums.py, core/types.py, core/errors.py, core/clock.py";
       Tests = "" },

    @{ Id = 2;  Name = "config（schema / loader / default.yaml）";
       Files = "config/default.yaml, config/regions.sample.yaml, src/deskmate/config/__init__.py, config/schema.py, config/loader.py, tests/test_config.py";
       Tests = "tests/test_config.py" },

    @{ Id = 3;  Name = "input（base / scenarios / dummy / factory）";
       Files = "src/deskmate/input/__init__.py, input/base.py, input/scenarios.py, input/dummy_source.py, input/factory.py, tests/test_dummy_source.py";
       Tests = "tests/test_dummy_source.py" },

    @{ Id = 4;  Name = "pipeline 前半（windower / regions / features / history）";
       Files = "src/deskmate/pipeline/__init__.py, pipeline/windower.py, pipeline/regions.py, pipeline/features.py, pipeline/history.py, tests/test_windower.py, tests/test_regions.py, tests/test_features.py, tests/test_history.py";
       Tests = "tests/test_windower.py tests/test_regions.py tests/test_features.py tests/test_history.py" },

    @{ Id = 5;  Name = "pipeline 後半（estimator / rule / smoother / duration / approachability）";
       Files = "pipeline/estimator.py, pipeline/rule_estimator.py, pipeline/smoother.py, pipeline/duration.py, pipeline/approachability.py, tests/test_rule_estimator.py, tests/test_smoother.py, tests/test_duration.py, tests/test_approachability.py";
       Tests = "tests/test_rule_estimator.py tests/test_smoother.py tests/test_duration.py tests/test_approachability.py" },

    @{ Id = 6;  Name = "runner（スレッド統合・headless 動作確認）";
       Files = "pipeline/runner.py, src/deskmate/app.py, src/deskmate/__main__.py, src/deskmate/logging_setup.py（簡易版）, tests/test_runner.py";
       Tests = "tests/test_runner.py" },

    @{ Id = 7;  Name = "character（mapping / renderer）";
       Files = "src/deskmate/character/__init__.py, character/mapping.py, character/renderer.py, tests/test_character_mapping.py";
       Tests = "tests/test_character_mapping.py" },

    @{ Id = 8;  Name = "ui 基盤（labels / theme / bridge / character_view）";
       Files = "src/deskmate/ui/__init__.py, ui/labels.py, ui/theme.py, ui/bridge.py, ui/character_view.py, tests/test_labels.py";
       Tests = "tests/test_labels.py" },

    @{ Id = 9;  Name = "常駐ウィジェット";
       Files = "ui/widget_window.py";
       Tests = "" },

    @{ Id = 10; Name = "共有画面";
       Files = "ui/share_window.py";
       Tests = "" },

    @{ Id = 11; Name = "詳細画面";
       Files = "ui/detail_window.py, ui/panels/__init__.py, panels/event_scatter_panel.py, panels/motion_panel.py, panels/region_panel.py, panels/feature_table_panel.py, panels/history_panel.py";
       Tests = "" },

    @{ Id = 12; Name = "privacy / logging / トレイ / 異常系";
       Files = "src/deskmate/privacy/__init__.py, privacy/guard.py, ui/tray.py, logging_setup.py（完成）, runner.py の異常系, tests/test_privacy_guard.py, tests/test_source_failure.py";
       Tests = "tests/test_privacy_guard.py tests/test_source_failure.py" },

    @{ Id = 13; Name = "file_source・デモ通し確認";
       Files = "input/file_source.py, tests/test_file_source.py, tests/test_demo_sequence.py, tests/test_ui_smoke.py";
       Tests = "tests/test_file_source.py tests/test_demo_sequence.py tests/test_ui_smoke.py" },

    @{ Id = 14; Name = "骨組み（hdf5_source / ml_estimator / voxel）";
       Files = "input/hdf5_source.py, pipeline/ml_estimator.py, pipeline/voxel.py, tests/test_voxel.py";
       Tests = "tests/test_voxel.py" }
)

# ============================================================================
# 共通ルール（全プロンプトの末尾に付ける）
# ============================================================================
$CommonRules = @'
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
'@

# ============================================================================
# ヘルパ
# ============================================================================
function Write-Section {
    param([string]$Text)
    Write-Host ""
    Write-Host ("=" * 78) -ForegroundColor Cyan
    Write-Host $Text -ForegroundColor Cyan
    Write-Host ("=" * 78) -ForegroundColor Cyan
}

function Write-Info  { param([string]$m) Write-Host "[INFO ] $m" -ForegroundColor Gray }
function Write-Ok    { param([string]$m) Write-Host "[ OK  ] $m" -ForegroundColor Green }
function Write-Warn2 { param([string]$m) Write-Host "[WARN ] $m" -ForegroundColor Yellow }
function Write-Err2  { param([string]$m) Write-Host "[FAIL ] $m" -ForegroundColor Red }

function Parse-StepSpec {
    param([string]$Spec)
    $result = New-Object System.Collections.Generic.List[int]
    foreach ($part in $Spec.Split(",")) {
        $p = $part.Trim()
        if ($p -eq "") { continue }
        if ($p -match '^(\d+)\s*-\s*(\d+)$') {
            $a = [int]$Matches[1]; $b = [int]$Matches[2]
            if ($a -gt $b) { throw "ステップ範囲が逆です: $p" }
            for ($i = $a; $i -le $b; $i++) { $result.Add($i) }
        }
        elseif ($p -match '^\d+$') { $result.Add([int]$p) }
        else { throw "ステップ指定を解釈できません: '$p'（例: 0-14, 3,4,5, 7）" }
    }
    return ($result | Sort-Object -Unique)
}

function Get-Progress {
    if (Test-Path $ProgressFile) {
        try { return (Get-Content $ProgressFile -Raw | ConvertFrom-Json) }
        catch { Write-Warn2 "進捗ファイルを読めませんでした。無視します。" }
    }
    return $null
}

function Save-Progress {
    param([int]$LastCompleted, [string]$Status)
    $obj = [ordered]@{
        last_completed_step = $LastCompleted
        status              = $Status
        updated_at          = (Get-Date).ToString("s")
    }
    $obj | ConvertTo-Json | Out-File -FilePath $ProgressFile -Encoding utf8
}

function Build-Prompt {
    param([hashtable]$Step)

    $id    = $Step.Id
    $name  = $Step.Name
    $files = $Step.Files

    $header = @"
あなたは DeskMate プロジェクトの実装担当です。
作業ディレクトリ: $Root

# 今回のタスク: Step $id — $name

## 最初に必ず読むファイル

1. AGENTS.md                      … 実装ルール（最優先）
2. docs/implementation-plan.md    … 実装順序とテスト項目。**§3 の「Step $id」の節が今回の仕様**
3. docs/architecture.md           … 構造・クラス/関数シグネチャ・データ型・設定
4. docs/status-definition.md      … 状態・特徴量・閾値・表示文字列の**正典**
5. docs/requirements.md           … 目的と完成条件
6. docs/privacy-design.md         … プライバシー要件
7. docs/demo-scenario.md          … シナリオとデモ構成

## やること

docs/implementation-plan.md §3 の **Step $id** の節に書かれている内容を、そのとおりに実装する。

作成対象ファイル（目安。正確な一覧は implementation-plan.md の該当節を見ること）:
$files

同節の「テスト」の表に列挙されている項目を**すべて**テストとして実装する。
項目を減らしたり、まとめて 1 つにしたりしない。

実装が終わったら pytest を実行し、通ることを確認する。
"@

    $stepExtra = ""
    switch ($id) {
        0 {
            $stepExtra = @'

## Step 0 の補足

- 仮想環境の作成と pip install は**このスクリプトが後で行う**ので、あなたは実行しなくてよい。
  ファイル（pyproject.toml など）を正しく作ることに集中する。
- pyproject.toml の内容は docs/implementation-plan.md §1 にそのまま書いてある。
- data/ と logs/ は .gitignore に入れる。
'@
        }
        2 {
            $stepExtra = @'

## Step 2 の補足

- config/default.yaml は docs/architecture.md §15 の YAML を**そのまま**書き写す。
  値を変えない。コメントも残す。
- pydantic モデルは extra="forbid" にする。
- テスト #10（estimation の全閾値が docs/status-definition.md §5.2 と一致する）は、
  期待値をテストコードに直書きして比較すること。設定から読んだ値どうしを比べても意味がない。
'@
        }
        9 {
            $stepExtra = @'

## Step 9 の補足

- GUI なのでヘッドレステストは書かない（Step 13 の test_ui_smoke.py でまとめて検証する）。
- 実装後、python -m deskmate --demo が起動して常駐ウィジェットが表示されることを、
  可能であれば確認する。確認できない環境なら、その旨を報告する。
- docs/implementation-plan.md の「確認項目（手動）」は、コード上で担保できているかを
  自己チェックして報告する。
'@
        }
        10 {
            $stepExtra = @'

## Step 10 の補足

- **共有画面はプライバシー上もっとも重要な画面。** docs/privacy-design.md §3.3 の
  「表示不可」リストを必ず守る。
- share_window.py に FeatureFrame / DetailFrame / EventWindow を import しない。
- UiBridge の detail_updated シグナルに接続しない。
'@
        }
        11 {
            $stepExtra = @'

## Step 11 の補足

- パネルは docs/implementation-plan.md の Step 11「実装順序」の 1→7 の順に作る。
- 時間が足りない場合は逆順（7 から）に削ってよいが、削ったものを必ず報告する。
- 詳細画面を閉じたら bridge.close_detail() を呼び、DetailFrame の生成を止めること。
'@
        }
        14 {
            $stepExtra = @'

## Step 14 の補足

- voxel.py は「実装する」。数式は docs/status-definition.md §4.6 にある。
  参照リポジトリ EVENT_CAMERA のコードをコピーせず、数式から実装すること。
- np.add.at ではなく np.bincount を使う（テスト #11 の性能要件）。
- compute_centroid_trajectory は **(cx, cy) の順**で返す。参照実装とは逆なので注意。
- hdf5_source.py と ml_estimator.py は骨組みのみ。ただし
  ml_estimator.feature_vector() と FEATURE_NAMES は実装する。
'@
        }
    }

    if ($stepExtra -ne "") { $stepExtra = "`n" + $stepExtra }
    return ($header + $stepExtra + "`n`n" + $CommonRules)
}

function Invoke-Pytest {
    param([string]$TestPaths, [int]$StepId)

    if ($SkipTests) { Write-Warn2 "pytest をスキップしました（-SkipTests）"; return $true }
    if ([string]::IsNullOrWhiteSpace($TestPaths)) {
        Write-Info "このステップにはテストがありません。全体テストを実行します。"
        $TestPaths = "tests"
    }
    if (-not (Test-Path $VenvPython)) {
        Write-Warn2 "仮想環境が見つかりません（$VenvPython）。pytest をスキップします。"
        return $true
    }
    if (-not (Test-Path (Join-Path $Root "tests"))) {
        Write-Info "tests/ がまだありません。pytest をスキップします。"
        return $true
    }

    $env:QT_QPA_PLATFORM = "offscreen"
    $logFile = Join-Path $LogDir ("step-{0:d2}-pytest.log" -f $StepId)
    Write-Info "pytest 実行: $TestPaths"

    Push-Location $Root
    try {
        $argList = @("-m", "pytest", "-q") + ($TestPaths.Split(" ") | Where-Object { $_ -ne "" })
        & $VenvPython $argList 2>&1 | Tee-Object -FilePath $logFile
        $code = $LASTEXITCODE
    }
    finally { Pop-Location }

    if ($code -eq 0) { Write-Ok "pytest 成功"; return $true }
    Write-Err2 "pytest 失敗（exit $code）。ログ: $logFile"
    return $false
}

function Initialize-Venv {
    Write-Section "仮想環境のセットアップ"

    if (-not (Test-Path (Join-Path $Root "pyproject.toml"))) {
        Write-Warn2 "pyproject.toml がありません。Step 0 が未完了のようです。セットアップを飛ばします。"
        return $false
    }

    if (Test-Path $VenvPython) {
        Write-Info "仮想環境は既にあります: $VenvPython"
    }
    else {
        Write-Info "仮想環境を作成します..."
        Push-Location $Root
        try {
            & py -3.13 -m venv .venv
            if (-not $?) { & python -m venv .venv }
        }
        finally { Pop-Location }

        if (-not (Test-Path $VenvPython)) {
            Write-Err2 "仮想環境の作成に失敗しました。"
            return $false
        }
        Write-Ok "仮想環境を作成しました。"
    }

    Write-Info "依存関係をインストールします（数分かかります）..."
    Push-Location $Root
    try {
        & $VenvPython -m pip install --upgrade pip --quiet
        & $VenvPython -m pip install -e ".[dev]"
        $code = $LASTEXITCODE
    }
    finally { Pop-Location }

    if ($code -ne 0) {
        Write-Err2 "pip install に失敗しました（exit $code）。"
        return $false
    }
    Write-Ok "依存関係をインストールしました。"
    return $true
}

# ============================================================================
# 事前チェック
# ============================================================================
Write-Section "DeskMate 一括実装ドライバ"

Write-Info "リポジトリ: $Root"

$requiredDocs = @(
    "AGENTS.md", "CLAUDE.md", "README.md",
    "docs/requirements.md", "docs/architecture.md", "docs/implementation-plan.md",
    "docs/status-definition.md", "docs/privacy-design.md", "docs/demo-scenario.md"
)
$missing = @()
foreach ($d in $requiredDocs) {
    if (-not (Test-Path (Join-Path $Root $d))) { $missing += $d }
}
if ($missing.Count -gt 0) {
    Write-Err2 "設計書が足りません。ここは DeskMate リポジトリではないかもしれません。"
    foreach ($m in $missing) { Write-Host "        - $m" -ForegroundColor Red }
    exit 1
}
Write-Ok "設計書 9 本を確認しました。"

New-Item -ItemType Directory -Force -Path $PromptDir | Out-Null
New-Item -ItemType Directory -Force -Path $LogDir    | Out-Null

# Codex CLI の有無
$codexAvailable = $false
$codexPath = $null
try {
    $cmd = Get-Command $CodexCommand -ErrorAction Stop
    $codexAvailable = $true
    $codexPath = $cmd.Source
    Write-Ok "Codex CLI: $codexPath"
}
catch {
    Write-Warn2 "Codex CLI（$CodexCommand）が PATH にありません。"
    Write-Host ""
    Write-Host "  インストール:  npm install -g @openai/codex" -ForegroundColor Yellow
    Write-Host "  ログイン:      codex login" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  CLI 無しでも進められます。生成されたプロンプトを Codex の" -ForegroundColor Yellow
    Write-Host "  IDE 拡張 / Web に 1 ステップずつ貼り付けてください。" -ForegroundColor Yellow
    Write-Host ""
}

# 実行するステップ
$targetSteps = Parse-StepSpec -Spec $Steps

if ($Resume) {
    $prog = Get-Progress
    if ($null -ne $prog) {
        $last = [int]$prog.last_completed_step
        Write-Info "前回の完了ステップ: $last（$($prog.status)）"
        $targetSteps = $targetSteps | Where-Object { $_ -gt $last }
        if ($targetSteps.Count -eq 0) {
            Write-Ok "再開すべきステップがありません。すべて完了しています。"
            exit 0
        }
    }
    else { Write-Info "進捗ファイルがありません。最初から実行します。" }
}

$invalid = $targetSteps | Where-Object { $_ -lt 0 -or $_ -gt 14 }
if ($invalid.Count -gt 0) {
    Write-Err2 "存在しないステップです: $($invalid -join ', ')（有効範囲 0-14）"
    exit 1
}

Write-Info "対象ステップ: $($targetSteps -join ', ')"

# ============================================================================
# プロンプト生成
# ============================================================================
Write-Section "プロンプト生成"

foreach ($id in $targetSteps) {
    $step = $StepTable | Where-Object { $_.Id -eq $id }
    $prompt = Build-Prompt -Step $step
    $file = Join-Path $PromptDir ("step-{0:d2}.md" -f $id)
    $prompt | Out-File -FilePath $file -Encoding utf8
    Write-Ok ("step-{0:d2}.md — {1}" -f $id, $step.Name)
}

Write-Host ""
Write-Info "プロンプト: $PromptDir"

if ($PromptsOnly) {
    Write-Section "完了（プロンプト生成のみ）"
    Write-Host "次にやること:" -ForegroundColor Cyan
    Write-Host "  1. scripts/prompts/step-00.md の内容を確認する"
    Write-Host "  2. Codex に貼り付けて実行する（または CLI を入れて本スクリプトを再実行）"
    Write-Host "  3. 1 ステップ終わるごとに pytest を回して、通ってから次へ進む"
    exit 0
}

if (-not $codexAvailable) {
    Write-Section "Codex CLI が無いため、ここで停止します"
    Write-Host "プロンプトは生成済みです。手動で進める場合:" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  1. scripts/prompts/step-00.md を Codex に貼る"
    Write-Host "  2. Step 0 が終わったら次を実行して仮想環境を作る:"
    Write-Host "       py -3.13 -m venv .venv" -ForegroundColor Gray
    Write-Host "       .venv\Scripts\python -m pip install -e `".[dev]`"" -ForegroundColor Gray
    Write-Host "  3. 以降 step-01.md 〜 step-14.md を順に貼り、都度 pytest を回す:"
    Write-Host "       .venv\Scripts\python -m pytest -q" -ForegroundColor Gray
    exit 0
}

# ============================================================================
# 実行
# ============================================================================
$startedAt = Get-Date
$completed = @()
$failedAt  = $null

foreach ($id in $targetSteps) {
    $step = $StepTable | Where-Object { $_.Id -eq $id }
    Write-Section ("Step {0}: {1}" -f $id, $step.Name)

    $promptFile = Join-Path $PromptDir ("step-{0:d2}.md" -f $id)
    $logFile    = Join-Path $LogDir ("step-{0:d2}-codex.log" -f $id)
    $promptText = Get-Content $promptFile -Raw

    $codexArgs = @("exec", "--cd", $Root, "--full-auto")
    if ($Model -ne "") { $codexArgs += @("-m", $Model) }
    $codexArgs += $promptText

    Write-Info ("codex {0} <prompt>" -f (($codexArgs[0..($codexArgs.Count - 2)]) -join " "))
    Write-Info "ログ: $logFile"
    Write-Host ""

    & $CodexCommand $codexArgs 2>&1 | Tee-Object -FilePath $logFile
    $codexExit = $LASTEXITCODE

    if ($codexExit -ne 0) {
        Write-Err2 "Codex が異常終了しました（exit $codexExit）。"
        Write-Info "フラグが合わない場合は、スクリプト内の `$codexArgs を環境に合わせて調整してください。"
        $failedAt = $id
        break
    }
    Write-Ok "Codex 完了。"

    # Step 0 の直後に仮想環境を用意する
    if ($id -eq 0) {
        $ok = Initialize-Venv
        if (-not $ok) {
            Write-Err2 "仮想環境のセットアップに失敗しました。手動で作ってから -Resume してください。"
            $failedAt = $id
            break
        }
    }

    if (-not (Invoke-Pytest -TestPaths $step.Tests -StepId $id)) {
        Write-Err2 "Step $id のテストが通りませんでした。ここで停止します。"
        Write-Info "修正後、次で再開できます: .\scripts\Run-CodexImplementation.ps1 -Resume"
        $failedAt = $id
        break
    }

    $completed += $id
    Save-Progress -LastCompleted $id -Status "ok"
    Write-Ok "Step $id 完了。"
}

# ============================================================================
# まとめ
# ============================================================================
$elapsed = (Get-Date) - $startedAt

Write-Section "結果"
Write-Host ("経過時間     : {0:hh\:mm\:ss}" -f $elapsed)
Write-Host ("完了ステップ : {0}" -f $(if ($completed.Count -gt 0) { $completed -join ", " } else { "なし" }))

if ($null -ne $failedAt) {
    Write-Host ("停止ステップ : {0}" -f $failedAt) -ForegroundColor Red
    Save-Progress -LastCompleted $(if ($completed.Count -gt 0) { $completed[-1] } else { -1 }) -Status "failed_at_$failedAt"
    Write-Host ""
    Write-Host "次にやること:" -ForegroundColor Yellow
    Write-Host "  1. scripts/logs/ のログを見て原因を確認する"
    Write-Host "  2. 直してから: .\scripts\Run-CodexImplementation.ps1 -Resume"
    exit 1
}

Write-Ok "指定されたステップをすべて完了しました。"

if ($completed -contains 14) {
    Write-Host ""
    Write-Host "MVP の完了条件は docs/requirements.md §9（DoD-1〜12）を確認してください。" -ForegroundColor Cyan
    Write-Host "デモ前チェックは docs/demo-scenario.md §5 にあります。" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "起動:" -ForegroundColor Cyan
    Write-Host "  .venv\Scripts\python -m deskmate --demo" -ForegroundColor Gray
}
exit 0
