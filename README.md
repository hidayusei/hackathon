# DeskMate

GenX320イベントカメラで机上の動きを取得し、Raspberry Pi内で特徴量抽出・状態推定・
画面表示まで行うアプリです。現在は次の3状態を表示します。

| 内部状態 | 画面表示 | キャラクター |
|---|---|---|
| `focused` | 集中 | 走る |
| `idle` | 非集中 | 座る |
| `away` | 離席中 | 寝る |

集中が25分続くと、状態は`focused`のまま休憩促しへ切り替わります。

Raspberry Pi向けの実行ファイル一式は`dist/DeskMate-Pi.zip`に入っています。

## Windowsで画面を確認する

Python 3.11〜3.13を使用します。

```powershell
py -3.13 -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -e ".[dev]"
```

環境構築後は、エクスプローラーで`Start-DeskMate.bat`をダブルクリックすると
ダミーデータのデモが起動します。

```powershell
Start-DeskMate.bat
```

PowerShellから起動する場合:

```powershell
.venv\Scripts\python -m deskmate --demo
```

休憩促しを約30秒で確認する場合:

```powershell
.venv\Scripts\python -m deskmate --demo --break-demo
```

テスト:

```powershell
.venv\Scripts\python -m pytest -q
```

## Raspberry PiでGenX320を接続する

Prophesee公式イメージ、GenX320ドライバ、OpenEB、Metavision SDKが入っており、
`metavision_viewer`が使える状態から始めます。

### 1. カメラを準備する

```bash
sudo dtoverlay genx320,cam0
cd ~/rpi-sensor-drivers
./rp5_setup_v4l.sh
export PSEE_VAR_V4L2_BSIZE=1
metavision_viewer
```

ライブ表示を確認したら、`metavision_viewer`を閉じます。ほかのアプリがカメラを
使用したままだとDeskMateは接続できません。

### 2-A. Pi用ZIPを使う場合

```bash
cd ~/DeskMate-Pi
bash install-pi.sh
./check-pi.sh
./run-pi.sh
```

`install-pi.sh`は`--system-site-packages`付きの`.venv`を作成します。これはOS側に
導入された`metavision_core`を仮想環境から読み込むために必要です。

`check-pi.sh`は次を確認します。

- Linux / 64-bit ARM
- Python仮想環境と実行時ライブラリ
- `metavision_core.event_io.EventsIterator`
- V4L2デバイス
- GUIセッション
- 設定ファイルと4種類のGIF

### 2-B. Gitリポジトリから直接動かす場合

```bash
cd ~/hackathon
python3 -m venv --system-site-packages .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e .
export PSEE_VAR_V4L2_BSIZE=1
.venv/bin/python -m deskmate --source metavision
```

カメラ取得に失敗したときダミー入力へ切り替わらないよう、Piでは
`--source metavision`を明示します。

### そのほかの起動方法

```bash
# カメラなしでUI確認
.venv/bin/python -m deskmate --demo --break-demo

# Metavision RAW録画を再生
.venv/bin/python -m deskmate --raw /path/to/recording.raw

# JSONLまたはNPZを再生
.venv/bin/python -m deskmate --replay /path/to/events.npz

# UIなしでライブ入力と状態遷移を確認
.venv/bin/python -m deskmate --headless --source metavision

# 全画面表示
.venv/bin/python -m deskmate --source metavision --fullscreen

# 起動時からイベントカメラ表示とキャラクターを開く
.venv/bin/python -m deskmate --source metavision --show-event-camera
```

## イベントカメラ側から渡すデータ

DeskMateのライブ入力は
`metavision_core.event_io.EventsIterator`からNumPyの構造化配列を受け取ります。
イベント1件には次の4フィールドが必要です。

| フィールド | 型 | 内容 |
|---|---|---|
| `x` | `uint16` | 横座標。GenX320では0〜319 |
| `y` | `uint16` | 縦座標。GenX320では0〜319 |
| `t` | `int64` | センサ基準の時刻。単位はマイクロ秒 |
| `p` | 整数 | 極性。正値を1、それ以外を0へ変換 |

必要条件:

- 解像度は320×320
- `t`はバッチ内で単調増加
- ライブ入力は既定20,000µs単位で取得
- DeskMate内部で200msの処理窓へまとめる
- RGB画像、フレーム画像、通信データへの変換は不要

カメラ入力を変更する場合は、主に次を確認します。

- `src/deskmate/input/metavision_source.py`: SDKから`EventBatch`へ変換
- `src/deskmate/input/base.py`: 入力ソースの共通インターフェース
- `src/deskmate/input/factory.py`: 入力モードの選択
- `config/default.yaml`: 解像度、取得間隔、領域、推定閾値

実カメラで最初に見るべき値は、詳細画面のイベント点群、イベントレート、
キーボード・マウス領域の活動割合です。設置位置を変えた場合は領域矩形と閾値を
再調整します。

## 画面の操作方法

### メイン画面

メイン画面にはキャラクター、現在状態、状態の継続時間が表示されます。

| 操作 | 動作 |
|---|---|
| 左ボタンでドラッグ | ウィンドウを移動 |
| ダブルクリック | キャラクターだけの表示へ切り替え |
| もう一度ダブルクリック | 状態名と継続時間を含む表示へ戻す |
| 右クリック | 操作メニューを開く |

キャラクターだけの表示へ切り替えても、キャラクター自体の大きさは変わりません。

### 右クリックメニュー

| 項目 | 動作 |
|---|---|
| `LIVE` / `REPLAY` / `DUMMY MODE` / `CAMERA ERROR` | 現在の入力を表示。選択操作はできません |
| 詳細 | 詳細・デモ画面を開く |
| 停止 | カメラ取得と推定を一時停止 |
| 再開 | 状態履歴をリセットして取得を再開 |
| UIデバッグ | 状態と休憩促しの見た目を手動確認 |
| 終了 | DeskMateを完全に終了 |

`UIデバッグ`では次を選択できます。

- 集中を表示
- 非集中を表示
- 離席中を表示
- 休憩促しを表示
- 自動判定に戻す

UIデバッグは表示だけを固定し、カメラ入力や実際の推定結果は変更しません。
入力更新が続いても選択した表示を保持し、「自動判定に戻す」で最新の推定表示へ戻ります。

メイン画面にフォーカスがあるときは、数字キーでも表示を切り替えられます。

| キー | UIデバッグ表示 |
|---|---|
| `1` | 集中 |
| `2` | 非集中 |
| `3` | 離席中 |
| `4` | 休憩促し |

### 休憩促し

集中が25分続くとキャラクターが休憩表示になり、画面内にバナーが出ます。

| ボタン | 動作 |
|---|---|
| あとで | バナーを閉じ、5分後に再表示 |
| 休憩する | 連続集中時間をリセット |

休憩促し中も内部状態は`focused`です。

### 詳細・デモ画面

右クリックの「詳細」から開きます。

- イベントカメラ表示
- 状態に対応するキャラクター

イベントカメラ表示には、`metavision_viewer`でも使われるOpenEB/Metavision SDKの
フレーム生成器と標準配色を使用します。イベントは1処理窓あたり最大20万件まで描画します。
`metavision_viewer`とDeskMateはカメラを同時に使用できないため、確認後は
`metavision_viewer`を閉じてからDeskMateを起動してください。

起動直後からこの画面を表示する場合は、`--show-event-camera`を指定します。

右上の閉じるボタンで詳細画面だけを閉じます。詳細画面を閉じると点群表示用データの
生成も止まり、メイン画面と状態推定はそのまま動き続けます。

## 接続できないとき

| 表示・症状 | 確認すること |
|---|---|
| `Metavision SDK: NG` | システムPythonで`metavision_core`をimportできるか |
| `V4L2デバイス: NG` | `dtoverlay`と`rp5_setup_v4l.sh`を実行したか |
| `GUIセッション: NG` | Piデスクトップ上のターミナルから実行しているか |
| `CAMERA ERROR` | `metavision_viewer`を閉じたか、ケーブル、権限、SDKを確認 |
| `DUMMY MODE` | `--demo`や`--source dummy`で起動していないか |
| 点群が出ない | `metavision_viewer`でイベントが出るか、照明変化があるか |
| 状態が合わない | カメラ位置、領域矩形、イベントレート、推定閾値を確認 |

Pi用ZIPでは次のコマンドを最初に実行すると、問題の場所をまとめて確認できます。

```bash
./check-pi.sh
```
