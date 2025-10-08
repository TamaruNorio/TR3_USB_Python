
#!/usr/bin/env python3
"""TR3 HF リーダ／ライタを Python から操作する GUI サンプル."""

import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, List, Optional, Sequence

import serial  # type: ignore
import serial.tools.list_ports  # type: ignore
import tkinter as tk
from tkinter import messagebox, ttk


# ===============================
# シリアルポートラッパー
# ===============================
class SerialConnection:
    """pyserial を使ったシリアルポート簡易ラッパー.

    Attributes:
        port_name (str): 接続するシリアルポートの名前 (例: COM1, /dev/ttyUSB0)。
        baudrate (int): シリアル通信のボーレート (例: 115200)。
        _serial (Optional[serial.Serial]): pyserialのSerialオブジェクト。接続時に設定される。
        last_error (str): 最後に発生したエラーメッセージ。
    """

    def __init__(self, port_name: str, baudrate: int) -> None:
        """SerialConnectionのコンストラクタ。

        Args:
            port_name (str): 接続するシリアルポートの名前。
            baudrate (int): シリアル通信のボーレート。
        """
        self.port_name = port_name
        self.baudrate = baudrate
        self._serial: Optional[serial.Serial] = None
        self.last_error: str = ""

    def open(self) -> bool:
        """シリアルポートをオープンする。

        既存の接続があれば閉じ、新しい接続を確立する。
        timeout=0でノンブロッキングモードに設定し、読み取り側でタイムアウトを制御する。

        Returns:
            bool: ポートのオープンに成功した場合はTrue、失敗した場合はFalse。
        """
        try:
            self.close()
            self._serial = serial.Serial(
                port=self.port_name,
                baudrate=self.baudrate,
                timeout=0,  # ノンブロッキングモード
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
            )
            self._serial.reset_input_buffer()  # 入力バッファをクリア
            self._serial.reset_output_buffer() # 出力バッファをクリア
            return True
        except serial.SerialException as exc:  # pyserial の例外を捕捉
            self.last_error = str(exc)
            self._serial = None
            return False

    def close(self) -> None:
        """シリアルポートを閉じる。"""
        if self._serial and self._serial.is_open:
            self._serial.close()
        self._serial = None

    def write(self, data: Sequence[int]) -> bool:
        """バイナリデータをシリアルポートに送信する。

        Args:
            data (Sequence[int]): 送信するバイトデータのシーケンス。

        Returns:
            bool: 送信に成功した場合はTrue、失敗した場合はFalse。
        """
        if not self._serial or not self._serial.is_open:
            self.last_error = "シリアルポートがオープンされていません。"
            return False
        try:
            written = self._serial.write(bytes(data))
            return written == len(data)
        except serial.SerialException as exc:
            self.last_error = str(exc)
            return False

    def read_byte(self, timeout_ms: int) -> Optional[int]:
        """シリアルポートから1バイト読み取る（個別タイムアウト付き）。

        Args:
            timeout_ms (int): 読み取りのタイムアウト時間（ミリ秒）。

        Returns:
            Optional[int]: 読み取ったバイトデータ (int)。タイムアウトまたはエラーの場合はNone。
        """
        if not self._serial or not self._serial.is_open:
            self.last_error = "シリアルポートがオープンされていません。"
            return None

        # timeout を一時的に設定（読み取り後、元の設定に戻す）
        original_timeout = self._serial.timeout
        self._serial.timeout = timeout_ms / 1000.0  # 秒単位に変換
        try:
            chunk = self._serial.read(1)
            if chunk:
                return chunk[0]
            return None
        except serial.SerialException as exc:
            self.last_error = str(exc)
            return None
        finally:
            self._serial.timeout = original_timeout  # タイムアウト設定を元に戻す


# ===============================
# TR3 プロトコル関連の定数
# ===============================
STX = 0x02  # Start Text
ETX = 0x03  # End Text
CR = 0x0D   # Carriage Return

ADDR_DEFAULT = 0x00 # デフォルトのアドレス

CMD_ACK = 0x30      # 正常応答コマンド
CMD_NACK = 0x31     # エラー応答コマンド
CMD_ROM_REQ = 0x4F  # ROMバージョン要求コマンド
DETAIL_ROM = 0x90   # ROMバージョン詳細コマンド
CMD_MODE_RD = 0x4F  # 動作モード読み取りコマンド
DETAIL_MODE_R = 0x00 # 動作モード読み取り詳細コマンド
CMD_MODE_WR = 0x4E  # 動作モード書き込みコマンド
CMD_INV2 = 0x78     # Inventory2コマンド (HFタグ読み取り)
DETAIL_INV2_F0 = 0xF0 # Inventory2詳細コマンド (F0h: UIDのみ読み取り)
RSP_UID = 0x49      # UID応答コマンド
CMD_BUZZER = 0x42   # ブザー制御コマンド

HEADER_LEN = 4      # ヘッダーの長さ (STX, アドレス, コマンド, データ長)
FOOTER_LEN = 3      # フッターの長さ (ETX, SUM, CR)


# ===============================
# データ構造（C++版と対応）
# ===============================
@dataclass
class ReaderModeRaw:
    """リーダライタの動作モードの生バイトデータを保持するデータクラス。"""
    bytes: List[int] = field(default_factory=list)


@dataclass
class ReaderModePretty:
    """リーダライタの動作モードを人間が読みやすい形式で保持するデータクラス。"""
    mode: str = ""             # 動作モード (例: コマンドモード)
    anticollision: str = ""    # アンチコリジョン設定 (例: 有効/無効)
    read_behavior: str = ""    # 読み取り動作 (例: 連続読み取り/1回読み取り)
    buzzer: str = ""           # ブザー設定 (例: 鳴らす/鳴らさない)
    tx_data: str = ""          # 送信データ設定 (例: ユーザデータ + UID)
    baud: str = ""             # 通信速度 (例: 115200bps)


@dataclass
class InventoryItem:
    """インベントリで読み取られた個々のタグ情報を保持するデータクラス。"""
    uid: List[int] = field(default_factory=list) # タグのUID (バイト列のリスト)
    dsfid: int = 0                               # DSFID (Data Storage Format Identifier)


@dataclass
class InventoryResult:
    """インベントリ操作の結果全体を保持するデータクラス。"""
    items: List[InventoryItem] = field(default_factory=list) # 読み取られたタグアイテムのリスト
    expected_count: int = 0                                  # 期待される読み取りタグ数
    error_message: str = ""                                  # エラーメッセージ


# ===============================
# ログ出力ヘルパー
# ===============================
def now_timestamp() -> str:
    """現在のタイムスタンプを 'MM/DD HH:MM:SS.ms' 形式で返す。"""
    dt = datetime.now()
    return dt.strftime("%m/%d %H:%M:%S.%f")[:-3]


def to_hex_string(data: Sequence[int]) -> str:
    """バイトデータのシーケンスを16進数文字列に変換して返す。"""
    return " ".join(f"{b:02X}" for b in data)


def log_line(tag: str, payload: str, callback: Optional[Callable[[str], None]] = None) -> None:
    """指定されたタグとペイロードでログメッセージを生成し、表示する。

    Args:
        tag (str): ログメッセージのタグ (例: "send", "recv", "cmt")。
        payload (str): ログメッセージの本文。
        callback (Optional[Callable[[str], None]]): ログメッセージを処理するコールバック関数。
    """
    line = f"{now_timestamp()}  [{tag}]  {payload}"
    print(line)
    if callback:
        callback(line)


# ===============================
# フレーム生成・検証
# ===============================
def calc_sum_until(data: Sequence[int], until: int) -> int:
    """指定されたインデックスまでのバイトデータの合計値の下位1バイトを計算する。

    Args:
        data (Sequence[int]): バイトデータのシーケンス。
        until (int): 合計を計算する終端インデックス (このインデックスは含まれない)。

    Returns:
        int: 計算されたSUM値 (下位1バイト)。
    """
    return sum(data[:until]) & 0xFF


def make_frame(addr: int, cmd: int, payload: Sequence[int]) -> List[int]:
    """TR3プロトコルに基づいたコマンドフレームを生成する。

    Args:
        addr (int): アドレスバイト。
        cmd (int): コマンドバイト。
        payload (Sequence[int]): データ部のペイロード。

    Returns:
        List[int]: 生成された完全なコマンドフレーム (バイトのリスト)。
    """
    # ヘッダー部: STX, アドレス, コマンド, データ長
    frame = [STX, addr & 0xFF, cmd & 0xFF, len(payload) & 0xFF]
    frame.extend(payload) # ペイロードを追加
    frame.append(ETX)     # ETXを追加
    # SUM値を計算して追加 (STXからETXまで)
    frame.append(calc_sum_until(frame, len(frame)) & 0xFF)
    frame.append(CR)      # CRを追加
    return frame


def verify_frame(frame: Sequence[int]) -> bool:
    """受信したフレームがTR3プロトコルに準拠しているか検証する。

    Args:
        frame (Sequence[int]): 検証するフレーム (バイトのシーケンス)。

    Returns:
        bool: フレームが有効な場合はTrue、そうでない場合はFalse。
    """
    # フレームの最小長をチェック
    if len(frame) < HEADER_LEN + FOOTER_LEN:
        return False
    
    # データ長フィールドから期待されるフレーム長を計算
    data_len = frame[3]
    expected_len = HEADER_LEN + data_len + FOOTER_LEN
    if len(frame) != expected_len:
        return False
    
    # ETXとCRが正しい位置にあるかチェック
    if frame[-1] != CR or frame[-3] != ETX:
        return False
    
    # SUM値を検証
    sum_expect = frame[-2]
    sum_calc = calc_sum_until(frame, len(frame) - 2) # STXからETXまでのSUMを計算
    return sum_expect == sum_calc


# ===============================
# 通信（ACK で止める／止めない）
# ===============================
def communicate(
    sp: SerialConnection,
    command: Sequence[int],
    timeout_ms: int,
    stop_on_ack: bool = True,
    logger: Optional[Callable[[str], None]] = None,
) -> List[int]:
    """
    シリアルポートを介してコマンドを送信し、応答を受信する。
    受信したバイト列から有効なフレームを抽出し、リストとして返す。

    Args:
        sp (SerialConnection): シリアル接続オブジェクト。
        command (Sequence[int]): 送信するコマンド (バイトのシーケンス)。
        timeout_ms (int): 全体の通信タイムアウト時間（ミリ秒）。
        stop_on_ack (bool): ACKまたはNACKを受信したら処理を停止するかどうか。Trueの場合、停止する。
        logger (Optional[Callable[[str], None]]): ログ出力用のコールバック関数。

    Returns:
        List[int]: 受信した有効なフレームのバイトリスト。タイムアウトやエラーの場合は空リスト。
    """
    log_line("send", to_hex_string(command), logger)
    if not sp.write(command):
        log_line("cmt", f"送信エラー: {sp.last_error}", logger)
        return []

    rxbuf: List[int] = [] # 受信バイトを一時的に保持するバッファ
    out: List[int] = []   # 抽出された有効なフレームを格納するリスト
    deadline = time.monotonic() + timeout_ms / 1000.0 # 処理の最終期限

    while time.monotonic() < deadline:
        byte = sp.read_byte(10) # 10msのタイムアウトで1バイト読み取り
        if byte is not None:
            rxbuf.append(byte)
        else:
            time.sleep(0.001) # 読み取れなかった場合は少し待機
            continue

        # STXが見つかるまでバッファの先頭を読み飛ばす
        while rxbuf and rxbuf[0] != STX:
            del rxbuf[0]
        
        # ヘッダーがまだ完全でない場合は次のバイトを待つ
        if len(rxbuf) < HEADER_LEN:
            continue

        # データ長を取得し、期待されるフレーム長を計算
        data_len = rxbuf[3]
        need = HEADER_LEN + data_len + FOOTER_LEN
        
        # フレーム全体がバッファにない場合は次のバイトを待つ
        if len(rxbuf) < need:
            continue

        # フレームを抽出し、検証
        frame = rxbuf[:need]
        if not verify_frame(frame):
            del rxbuf[0] # 無効なフレームの場合は先頭バイトを削除して再試行
            continue

        log_line("recv", to_hex_string(frame), logger)
        out.extend(frame) # 有効なフレームを結果リストに追加

        cmd = frame[2]
        # ACKまたはNACKを受信し、かつstop_on_ackがTrueの場合は処理を終了
        if stop_on_ack and cmd in (CMD_ACK, CMD_NACK):
            return out

        del rxbuf[:need] # 処理済みのフレームをバッファから削除

    log_line("cmt", "タイムアウト: レスポンスが一定時間内に受信されませんでした。", logger)
    return out


# ===============================
# ROM バージョン取得
# ===============================
def read_rom_version(sp: SerialConnection, timeout_ms: int, logger: Optional[Callable[[str], None]] = None) -> str:
    """
    リーダライタのROMバージョンを読み取る。

    Args:
        sp (SerialConnection): シリアル接続オブジェクト。
        timeout_ms (int): 通信タイムアウト時間（ミリ秒）。
        logger (Optional[Callable[[str], None]]): ログ出力用のコールバック関数。

    Returns:
        str: ROMバージョンの文字列。取得できなかった場合は空文字列。
    """
    log_line("cmt", "/* ROMバージョンの読み取り */", logger)
    # ROMバージョン要求コマンドフレームを生成
    tx = make_frame(ADDR_DEFAULT, CMD_ROM_REQ, [DETAIL_ROM])
    # コマンドを送信し、応答を受信 (ACK/NACKで停止)
    rx = communicate(sp, tx, timeout_ms, True, logger)
    if not rx:
        return ""

    # 受信したバイト列から最後の有効なフレームを抽出
    index = 0
    last_start = 0
    while index + HEADER_LEN + FOOTER_LEN <= len(rx):
        data_len = rx[index + 3]
        need = HEADER_LEN + data_len + FOOTER_LEN
        if index + need > len(rx):
            break
        last_start = index
        index += need
    frame = rx[last_start:index]
    
    # フレームの検証と、コマンドがACKかつ詳細コマンドがROMバージョンであるかチェック
    if not verify_frame(frame) or frame[2] != CMD_ACK or frame[4] != DETAIL_ROM:
        return ""

    # ROMバージョン情報をASCII文字列に変換
    # データ部の5バイト目からETXの直前までを抽出し、表示可能なASCII文字のみを対象とする
    ascii_bytes = [b for b in frame[5:-3] if 0x20 <= b <= 0x7E]
    ascii_str = bytes(ascii_bytes).decode("ascii", errors="ignore")
    pretty = ascii_str
    # 特定のフォーマット (例: 
