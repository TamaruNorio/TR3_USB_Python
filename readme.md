# TR3_USB_Python

タカヤ製 RFID リーダ／ライタ **TR3 シリーズ（HF 13.56MHz）** を  
Python から制御するための **Windows向けサンプルプログラム** です。

USB 経由のシリアル通信（仮想 COM ポート）を利用し、  
ROM バージョン取得、動作モード制御、Inventory2、ブザー制御を  
GUI（Tkinter）で体験できます。

---

## 主な特徴

- ✅ **Tkinter GUI** による直感的な操作  
- ✅ **pyserial** のみ依存（軽量構成）  
- ✅ **16進ログ出力**で通信プロトコルを学習可能  
- ✅ TR3 の代表コマンド（ROM / Mode / Inventory2 / Buzzer）を実装  
- ✅ **PyInstaller ビルドバッチ付き**（`build_exe.bat`）

---

## フォルダ構成

```
TR3_USB_Python/
├─ tr3_usb_gui.py        ← メインGUIスクリプト
├─ build_exe.bat         ← exeビルド用バッチ（PyInstaller）
├─ README.md             ← この説明ファイル
└─ .gitignore
```

---

## 動作環境

| 項目 | 内容 |
| ---- | ---- |
| OS | Windows 10 / 11 (64bit) |
| Python | 3.9 以上（推奨 3.11） |
| 依存ライブラリ | `pyserial` |
| ハードウェア | TR3 シリーズ（HF 13.56MHz / USBモデル） |

> ※ LANモデルを制御する場合は、ソケット通信部分をTR3XM LAN版サンプルを参考に差し替えてください。

---

## 事前準備

1. Python をインストール（インストーラで “Add python.exe to PATH” にチェック）  
2. 必要ライブラリを導入：
   ```powershell
   py -m pip install pyserial
   ```

---

## 実行方法

```powershell
cd <本リポジトリのパス>
py tr3_usb_gui.py
```

### GUIでできること

- COMポートとボーレートをドロップダウンで選択  
- ROMバージョンの取得  
- 動作モードの読み取り／コマンドモードへの変更  
- Inventory2 の実行とタグ検出  
- タグ検出時にブザー制御（ピー／ピッピッピ）  
- 下部ログエリアに送受信フレームを16進で表示  

---

## EXE ビルド手順（Windows）

1. VS Code で本フォルダを開く  
2. ターミナルで以下を実行：
   ```bat
   build_exe.bat
   ```
3. 成功すると `dist\tr3_usb_gui.exe` が生成されます。

> GUIアプリなのでコンソールは表示されません。  
> コンソール版にしたい場合は `build_exe.bat` 内の `--noconsole` を削除してください。

---

## トラブルシューティング

| 症状 | 主な原因 | 対処 |
| ---- | -------- | ---- |
| COMポートが開けない | ポート番号誤り／占有中 | デバイスマネージャで確認し、他アプリを終了 |
| NACK応答 | コマンド誤り／チェックサム不一致 | ログ出力で送受信フレームを確認 |
| タイムアウト | ケーブル抜け／ボーレート不一致 | ボーレートを既定値（19200bps）に合わせる |

---

## GitHub Actions（自動ビルド）

タグを `vX.Y.Z` 形式で push すると、Windowsランナーで自動的に  
`tr3_usb_gui.exe` をビルドして Release に添付することができます。

→ `.github/workflows/build-win.yml` を参照。

---

## ライセンス

MIT License  
Copyright (c) 2025 Norio Tamaru

---

## 関連リポジトリ

- [TR3_USB_CPP](https://github.com/TamaruNorio/TR3_USB_CPP) — C++版（Win32 API）
- [TR3_LAN_CPP](https://github.com/TamaruNorio/TR3_LAN_CPP) — LAN版（ソケット通信）
- [UTR_USB_Python](https://github.com/TamaruNorio/UTR_USB_Python) — UHF帯 UTRシリーズ
- [UTR_LAN_Python](https://github.com/TamaruNorio/UTR_LAN_Python) — UHF帯 LAN版

---

## 参考資料

- [通信プロトコル説明書（HF帯製品）](https://www.takaya.co.jp/product/rfid/hf/hf_list/)
- [TR3RWManager ユーティリティ](https://www.takaya.co.jp/product/rfid/hf/hf_utility/)
- [タカヤ株式会社 RFID製品ページ](https://www.product.takaya.co.jp/rfid/)
