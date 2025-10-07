# TR3 USB / LAN Reader Writer Sample Collection

タカヤ製 RFID リーダ／ライタ（TR3 シリーズ・HF 13.56MHz）を **Windows 環境**で制御するための C++ / Python 学習用サンプル集です。USB 経由のシリアル通信を前提とし、必要最小限の依存関係でプロトコルの流れと実装手順を理解できる構成になっています。

教育現場や新人エンジニア向けの教材としても利用できるよう、コードは丁寧な日本語コメントと実行ログを備え、TR3 の基本コマンド（ROM バージョン取得・動作モード制御・Inventory2・ブザー制御）を一通り体験できます。

---

## 主な機能

- ✅ C++（Win32 API）によるシリアル通信ラッパーと TR3 プロトコル実装
- ✅ 対話式コンソールアプリ（COM ポート選択、ボーレート設定、Inventory2）
- ✅ Python + Tkinter の GUI サンプル（pyserial のみ依存）
- ✅ 送受信フレームの 16 進ログ表示と簡潔なエラーハンドリング
- ✅ 教材として読みやすい日本語コメントとコード構成

---

## リポジトリ構成

```
TR3_USB_CPP/
├─ build/                 ← 生成物（.exe / .obj / .pdb など）を集約
├─ include/
│   ├─ serial_port.hpp
│   └─ tr3_protocol.hpp
├─ src/
│   ├─ main.cpp           ← 実行エントリ（対話 UI）
│   ├─ serial_port.cpp    ← シリアル I/O（Win32 API）
│   └─ tr3_protocol.cpp   ← TR3 プロトコル（ROM 版取得・動作モード・Inventory2・ブザー）
├─ python/
│   └─ tr3_gui.py         ← Python + Tkinter 版 GUI サンプル
├─ build_msvc.bat         ← MSVC 向けビルドバッチ
└─ README.md
```

---

## 動作環境

| 項目 | 推奨 | 備考 |
| ---- | ---- | ---- |
| OS | Windows 10 / 11 (64bit) | USB 経由で TR3 を接続 |
| 開発環境 (C++) | Visual Studio 2022 + MSVC | x64 Native Tools Command Prompt を使用 |
| Python | 3.9 以上 | `pyserial` のみ追加インストール |
| ハードウェア | TR3 シリーズ（HF 13.56MHz） | USB または仮想 COM ポート |

> LAN モデルを利用する場合は、別途ソケット通信部分を差し替えてご利用ください。本サンプルは USB シリアル接続を想定しています。

---

## C++ サンプルのビルド手順

1. Visual Studio 2022（C++ 開発ワークロード）をインストール済みであることを確認します。
2. **x64 Native Tools Command Prompt for VS 2022** を起動します。
3. 本リポジトリのフォルダへ移動し、以下のコマンドを実行します。

### Debug ビルド（既定）
```bat
build_msvc.bat
```

### Release ビルド
```bat
build_msvc.bat release
```

### クリーン（生成物を削除）
```bat
build_msvc.bat clean
```

> 生成物はすべて `build/` フォルダに出力され、ルート直下が散らからない構成になっています。

---

## 実行ファイルと典型ログ

- 実行ファイル: `build\tr3_usb.exe`
- 中間ファイル: `build\*.obj`, `build\*.pdb`, `build\*.ilk` など（`clean` で削除可能）

### ビルド直後の出力例
```bat
C:\Users\example\TR3_USB_CPP>build_msvc.bat
[BUILD] Compiling ...
main.cpp
serial_port.cpp
tr3_protocol.cpp
コードを生成中...
[SUCCESS] Output: C:\Users\example\TR3_USB_CPP\build\tr3_usb.exe
Run: "C:\Users\example\TR3_USB_CPP\build\tr3_usb.exe"
```

### 実行時の典型ログ
```
=== 利用可能なCOMポート ===
  [0] COM3
  [1] COM5
使用する番号（Enterで0）: 0
=== ボーレート（Enterで19200） ===
  [0] 19200 bps
  [1] 38400 bps
番号を入力: 0
インベントリの試行回数（Enterで1）:
```

- 起動直後に **ROM バージョン**を取得して疎通確認を行います。
- 続いて **リーダ／ライタ動作モード**を読み取り、**「モードのみ」コマンドモード (0x00)** へ変更します（アンチコリジョン・ブザー設定・通信速度は現状維持）。
- **Inventory2** を指定回数実行し、タグ検出結果に応じてブザー音を切り替えます。
  - タグ検出時: **ピー (0x00)**
  - 検出なし／エラー: **ピッピッピ (0x01)**
- 送受信フレームは 16 進表記でログ出力されるため、プロトコル学習に活用できます。

---

## Python GUI サンプル `python/tr3_gui.py`

Windows 上で Python から TR3 を操作できる Tkinter ベースのサンプルです。シリアル通信は `pyserial` を利用し、C++ 版と同等の機能を GUI で体験できます。

### 事前準備
1. Python 3.9 以上をインストール（公式インストーラ推奨、`Add python.exe to PATH` を有効化）。
2. 依存ライブラリをインストール。
   ```powershell
   py -m pip install pyserial
   ```

### 実行方法（PowerShell）
```powershell
cd <本リポジトリのパス>
py python\tr3_gui.py
```

### GUI でできること
- COM ポートとボーレートをドロップダウンで選択し接続
- ROM バージョン表示と動作モードの読み取り・変更
- Inventory2 を任意回数実行し、取得 UID を一覧表示
- タグ検出状況に応じたブザー制御（ピー / ピッピッピ）
- 左下ログに送受信フレームを 16 進表示（教育用途向け）

---

## Visual Studio Code で Python サンプルを実行する手順

1. **Visual Studio Code** を起動し、`TR3_USB_CPP` フォルダを開きます（`File > Open Folder...`）。
2. 拡張機能「**Python (ms-python.python)**」をインストールします。
3. `Ctrl+Shift+P` でコマンドパレットを開き、`Python: Select Interpreter` から使用するインタープリタ（例: `Python 3.11 (64-bit)`) を選択します。
4. VS Code のターミナル（`Ctrl+Shift+` キー）で依存ライブラリを導入します。
   ```powershell
   py -m pip install pyserial
   ```
   > 仮想環境を利用する場合は `python -m venv .venv` で環境を作成し、`powershell -ExecutionPolicy Bypass -File .\.venv\Scripts\Activate.ps1` などで有効化したうえで同じコマンドを実行してください。
5. `python/tr3_gui.py` をエディタで開き、右上の **▶ Run Python File** または 実行メニューから **Python: Current File** を選択して `F5` を押します。
6. 画面右下のステータスバーで選択中のインタープリタを確認し、GUI が起動したら COM ポート・ボーレートを選んで接続します。

---

## トラブルシューティング

| 症状 | 主な原因 | 対処 |
| ---- | -------- | ---- |
| シリアルポートをオープンできない | ポート番号誤り / 占有中 / 権限不足 | デバイスマネージャでポート番号を確認し、他アプリを終了 | 
| NACK 応答 | コマンド種別やチェックサム不一致 | ログの 16 進出力でフレームを確認。ブザーは `CMD:0x42`、動作モード書き込みは `CMD:0x4E / Mode Detail 0x00` を使用 |
| タイムアウト | ケーブル抜け・距離・タグ枚数・ボーレート不一致 | 接続状態を確認し、ボーレートが 19200 bps（既定）で一致しているか確認 |

> それでも解決しない場合は、通信プロトコル説明書とロガーの出力を突き合わせて原因を切り分けてください。

---

## ライセンスと免責

- 本サンプルは学習・検証目的で提供しています。ご利用は自己責任でお願いします。
- 当社製品の詳細な通信仕様については公開資料（通信プロトコル説明書）をご参照ください。
- 非公開 API や社内固有情報、ネットワーク設定は一切含めていません。

教育目的でのご利用や改変は自由です。フィードバックや改善提案があれば Issue / Pull Request でお知らせください。
