## TAKAYA RFID リーダライタ サンプルプログラム ドキュメント

> **ドキュメントの全体像や他のサンプルプログラムについては、[こちらのランディングページ](https://TamaruNorio.github.io/TAKAYA-RFID-Sample-Docs/python/index.md)をご覧ください。**

# TR3_USB_Python

タカヤ製 RFID リーダ／ライタ **TR3 シリーズ（HF 13.56MHz）** を Python から制御するための **Windows向けサンプルプログラム** です。USB 経由のシリアル通信（仮想 COM ポート）を利用し、ROM バージョン取得、動作モード制御、Inventory2、ブザー制御を GUI（Tkinter）で体験できます。

## 概要

このサンプルプログラムは、Tkinter GUIによる直感的な操作を提供し、pyserialのみに依存する軽量な構成です。16進ログ出力で通信プロトコルを学習でき、TR3の代表コマンド（ROM / Mode / Inventory2 / Buzzer）を実装しています。PyInstallerビルドバッチ付きで、実行ファイル化も容易です。

## 動作環境

| 項目 | 内容 |
| ---- | ---- |
| OS | Windows 10 / 11 (64bit) |
| Python | 3.9 以上（推奨 3.11） |
| 依存ライブラリ | `pyserial` |
| ハードウェア | TR3 シリーズ（HF 13.56MHz / USBモデル） |

> ※ LANモデルを制御する場合は、ソケット通信部分をTR3XM LAN版サンプルを参考に差し替えてください。

## セットアップと実行方法

1.  **Python をインストール**: インストーラで “Add python.exe to PATH” にチェックを入れてください。
2.  **リポジトリのクローン**:
    ```powershell
    git clone https://github.com/TamaruNorio/TR3_USB_Python.git
    cd TR3_USB_Python
    ```
3.  **必要ライブラリを導入**:
    ```powershell
    py -m pip install pyserial
    ```
4.  **実行**:
    ```powershell
    py tr3_usb_gui.py
    ```
    GUIが起動し、COMポートとボーレートを選択して操作できます。ROMバージョン取得、動作モード制御、Inventory2、ブザー制御が可能です。

### EXE ビルド手順（Windows）

1.  VS Code で本フォルダを開く
2.  ターミナルで以下を実行:
    ```bat
    build_exe.bat
    ```
    成功すると `dist\tr3_usb_gui.exe` が生成されます。GUIアプリなのでコンソールは表示されません。コンソール版にしたい場合は `build_exe.bat` 内の `--noconsole` を削除してください。

## プロジェクト構成

```
TR3_USB_Python/
├─ tr3_usb_gui.py        ← メインGUIスクリプト
├─ build_exe.bat         ← exeビルド用バッチ（PyInstaller）
├─ README.md             ← この説明ファイル
└─ .gitignore
```

## ライセンス

MIT License  
Copyright (c) 2025 Norio Tamaru

