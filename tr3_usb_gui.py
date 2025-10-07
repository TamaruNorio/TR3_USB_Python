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
    """pyserial を使ったシリアルポート簡易ラッパー."""

    def __init__(self, port_name: str, baudrate: int) -> None:
        self.port_name = port_name
        self.baudrate = baudrate
        self._serial: Optional[serial.Serial] = None
        self.last_error: str = ""

    def open(self) -> bool:
        """ポートをオープンする."""
        try:
            self.close()
            # timeout=0 でノンブロッキングにし、読み取り側でタイムアウト制御を行う
            self._serial = serial.Serial(
                port=self.port_name,
                baudrate=self.baudrate,
                timeout=0,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
            )
            self._serial.reset_input_buffer()
            self._serial.reset_output_buffer()
            return True
        except serial.SerialException as exc:  # pyserial の例外を保持
            self.last_error = str(exc)
            self._serial = None
            return False

    def close(self) -> None:
        """ポートを閉じる."""
        if self._serial and self._serial.is_open:
            self._serial.close()
        self._serial = None

    def write(self, data: Sequence[int]) -> bool:
        """バイナリデータを送信する."""
        if not self._serial or not self._serial.is_open:
            return False
        try:
            written = self._serial.write(bytes(data))
            return written == len(data)
        except serial.SerialException as exc:
            self.last_error = str(exc)
            return False

    def read_byte(self, timeout_ms: int) -> Optional[int]:
        """1 バイト読み取る（個別タイムアウト付き）."""
        if not self._serial or not self._serial.is_open:
            return None

        # timeout を一時的に設定（元に戻す）
        original_timeout = self._serial.timeout
        self._serial.timeout = timeout_ms / 1000.0
        try:
            chunk = self._serial.read(1)
            if chunk:
                return chunk[0]
            return None
        except serial.SerialException as exc:
            self.last_error = str(exc)
            return None
        finally:
            self._serial.timeout = original_timeout


# ===============================
# TR3 プロトコル関連の定数
# ===============================
STX = 0x02
ETX = 0x03
CR = 0x0D

ADDR_DEFAULT = 0x00

CMD_ACK = 0x30
CMD_NACK = 0x31
CMD_ROM_REQ = 0x4F
DETAIL_ROM = 0x90
CMD_MODE_RD = 0x4F
DETAIL_MODE_R = 0x00
CMD_MODE_WR = 0x4E
CMD_INV2 = 0x78
DETAIL_INV2_F0 = 0xF0
RSP_UID = 0x49
CMD_BUZZER = 0x42

HEADER_LEN = 4
FOOTER_LEN = 3


# ===============================
# データ構造（C++版と対応）
# ===============================
@dataclass
class ReaderModeRaw:
    bytes: List[int] = field(default_factory=list)


@dataclass
class ReaderModePretty:
    mode: str = ""
    anticollision: str = ""
    read_behavior: str = ""
    buzzer: str = ""
    tx_data: str = ""
    baud: str = ""


@dataclass
class InventoryItem:
    uid: List[int] = field(default_factory=list)
    dsfid: int = 0


@dataclass
class InventoryResult:
    items: List[InventoryItem] = field(default_factory=list)
    expected_count: int = 0
    error_message: str = ""


# ===============================
# ログ出力ヘルパー
# ===============================
def now_timestamp() -> str:
    dt = datetime.now()
    return dt.strftime("%m/%d %H:%M:%S.%f")[:-3]


def to_hex_string(data: Sequence[int]) -> str:
    return " ".join(f"{b:02X}" for b in data)


def log_line(tag: str, payload: str, callback: Optional[Callable[[str], None]] = None) -> None:
    line = f"{now_timestamp()}  [{tag}]  {payload}"
    print(line)
    if callback:
        callback(line)


# ===============================
# フレーム生成・検証
# ===============================
def calc_sum_until(data: Sequence[int], until: int) -> int:
    return sum(data[:until]) & 0xFF


def make_frame(addr: int, cmd: int, payload: Sequence[int]) -> List[int]:
    frame = [STX, addr & 0xFF, cmd & 0xFF, len(payload) & 0xFF]
    frame.extend(payload)
    frame.append(ETX)
    frame.append(calc_sum_until(frame, len(frame)) & 0xFF)
    frame.append(CR)
    return frame


def verify_frame(frame: Sequence[int]) -> bool:
    if len(frame) < HEADER_LEN + FOOTER_LEN:
        return False
    data_len = frame[3]
    need = HEADER_LEN + data_len + FOOTER_LEN
    if len(frame) != need:
        return False
    if frame[-1] != CR or frame[-3] != ETX:
        return False
    sum_expect = frame[-2]
    sum_calc = calc_sum_until(frame, len(frame) - 2)
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
    log_line("send", to_hex_string(command), logger)
    if not sp.write(command):
        log_line("cmt", "送信エラー", logger)
        return []

    rxbuf: List[int] = []
    out: List[int] = []
    deadline = time.monotonic() + timeout_ms / 1000.0

    while time.monotonic() < deadline:
        byte = sp.read_byte(10)
        if byte is not None:
            rxbuf.append(byte)
        else:
            time.sleep(0.001)
            continue

        # STX まで読み飛ばす
        while rxbuf and rxbuf[0] != STX:
            del rxbuf[0]
        if len(rxbuf) < HEADER_LEN:
            continue

        data_len = rxbuf[3]
        need = HEADER_LEN + data_len + FOOTER_LEN
        if len(rxbuf) < need:
            continue

        frame = rxbuf[:need]
        if not verify_frame(frame):
            del rxbuf[0]
            continue

        log_line("recv", to_hex_string(frame), logger)
        out.extend(frame)

        cmd = frame[2]
        if stop_on_ack and cmd in (CMD_ACK, CMD_NACK):
            return out

        del rxbuf[:need]

    log_line("cmt", "タイムアウト: レスポンスが一定時間内に受信されませんでした。", logger)
    return out


# ===============================
# ROM バージョン取得
# ===============================
def read_rom_version(sp: SerialConnection, timeout_ms: int, logger: Optional[Callable[[str], None]] = None) -> str:
    log_line("cmt", "/* ROMバージョンの読み取り */", logger)
    tx = make_frame(ADDR_DEFAULT, CMD_ROM_REQ, [DETAIL_ROM])
    rx = communicate(sp, tx, timeout_ms, True, logger)
    if not rx:
        return ""

    # 末尾フレームを抽出
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
    if not verify_frame(frame) or frame[2] != CMD_ACK or frame[4] != DETAIL_ROM:
        return ""

    ascii_bytes = [b for b in frame[5:-3] if 0x20 <= b <= 0x7E]
    ascii_str = bytes(ascii_bytes).decode("ascii", errors="ignore")
    pretty = ascii_str
    if len(ascii_str) >= 4:
        pretty = f"{ascii_str[0]}.{ascii_str[1:3]} {ascii_str[3:]}"
    log_line("cmt", f"ROMバージョン : {pretty}", logger)
    return pretty


# ===============================
# NACK 解析
# ===============================
def parse_nack_message(frame: Sequence[int]) -> str:
    if not verify_frame(frame) or frame[2] != CMD_NACK:
        return "Invalid NACK"
    code = frame[5] if len(frame) > HEADER_LEN + 1 else 0xFF
    if code == 0x42:
        return "SUM_ERROR: SUM不一致"
    if code == 0x44:
        return "FORMAT_ERROR: フォーマット/パラメータ不正"
    return "Unknown NACK error"


# ===============================
# 動作モード関連
# ===============================
def pretty_from_raw(raw: ReaderModeRaw) -> ReaderModePretty:
    p = ReaderModePretty()
    if len(raw.bytes) >= 4:
        mode = raw.bytes[0]
        flags = raw.bytes[2]
        spdb = raw.bytes[3]

        mode_map = {
            0x00: "コマンドモード",
            0x01: "オートスキャンモード",
            0x02: "トリガーモード",
            0x03: "ポーリングモード",
            0x24: "EASモード",
            0x50: "連続インベントリモード",
            0x58: "RDLOOPモード",
            0x59: "RDLOOPモード(実行中)",
            0x63: "EPCインベントリモード",
            0x64: "EPCインベントリリードモード",
        }
        p.mode = mode_map.get(mode, f"不明 (0x{mode:02X})")
        p.anticollision = "有効" if flags & (1 << 2) else "無効"
        p.read_behavior = "連続読み取り" if flags & (1 << 3) else "1回読み取り"
        p.buzzer = "鳴らす" if flags & (1 << 4) else "鳴らさない"
        p.tx_data = "ユーザデータ + UID" if flags & (1 << 5) else "ユーザデータのみ"

        baud_map = {
            0b00: "19200bps",
            0b01: "9600bps",
            0b10: "38400bps",
            0b11: "115200bps",
        }
        p.baud = baud_map.get((spdb >> 6) & 0x03, "不明")
    return p


def read_reader_mode(
    sp: SerialConnection,
    raw: ReaderModeRaw,
    pretty: ReaderModePretty,
    timeout_ms: int,
    logger: Optional[Callable[[str], None]] = None,
) -> bool:
    log_line("cmt", "/* リーダライタ動作モードの読み取り */", logger)
    tx = make_frame(ADDR_DEFAULT, CMD_MODE_RD, [DETAIL_MODE_R])
    rx = communicate(sp, tx, timeout_ms, True, logger)
    if not rx:
        return False

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
    if not verify_frame(frame) or frame[2] != CMD_ACK or frame[4] != DETAIL_MODE_R:
        return False

    raw.bytes = list(frame[5:-3])
    pretty_result = pretty_from_raw(raw)
    pretty.mode = pretty_result.mode
    pretty.anticollision = pretty_result.anticollision
    pretty.read_behavior = pretty_result.read_behavior
    pretty.buzzer = pretty_result.buzzer
    pretty.tx_data = pretty_result.tx_data
    pretty.baud = pretty_result.baud

    log_line("cmt", f"リーダライタ動作モード : {pretty.mode}", logger)
    log_line("cmt", f"アンチコリジョン       : {pretty.anticollision}", logger)
    log_line("cmt", f"読み取り動作           : {pretty.read_behavior}", logger)
    log_line("cmt", f"ブザー                 : {pretty.buzzer}", logger)
    log_line("cmt", f"送信データ             : {pretty.tx_data}", logger)
    log_line("cmt", f"通信速度               : {pretty.baud}", logger)
    return True


def write_reader_mode_to_command(
    sp: SerialConnection,
    current: ReaderModeRaw,
    timeout_ms: int,
    logger: Optional[Callable[[str], None]] = None,
) -> bool:
    if len(current.bytes) < 4:
        log_line("cmt", "現行モード情報が不十分です（読み取りレスポンスのデータ部が短い）", logger)
        return False

    flags = current.bytes[2]
    log_line("cmt", "/* コマンドモードへ設定します （他の設定は現状維持）*/", logger)

    payload = [
        0x00,  # 詳細: RAM
        0x00,  # 新モード: コマンドモード
        0x00,  # 予約
        flags,  # 各種設定パラメータ（読み取り値を維持）
        0x00,  # 予約
        0x00,  # ポーリング時間（上位）
        0x00,  # ポーリング時間（下位）
    ]

    tx = make_frame(ADDR_DEFAULT, CMD_MODE_WR, payload)
    rx = communicate(sp, tx, timeout_ms, True, logger)
    if not rx:
        return False

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
    if not verify_frame(frame):
        return False
    if frame[2] == CMD_NACK:
        log_line("cmt", f"NACK: {parse_nack_message(frame)}", logger)
        return False
    return frame[2] == CMD_ACK


# ===============================
# Inventory2
# ===============================
def run_inventory2(
    sp: SerialConnection,
    timeout_ms: int,
    logger: Optional[Callable[[str], None]] = None,
) -> InventoryResult:
    result = InventoryResult()
    log_line("cmt", "/* Inventory2 */", logger)
    tx = make_frame(ADDR_DEFAULT, CMD_INV2, [0xF0, 0x40, 0x01])

    log_line("send", to_hex_string(tx), logger)
    if not sp.write(tx):
        result.error_message = "送信エラー"
        return result

    buffer: List[int] = []
    t_end = time.monotonic() + timeout_ms / 1000.0
    t_quiet = time.monotonic()
    got_any_uid = False
    expected = -1

    while time.monotonic() < t_end:
        byte = sp.read_byte(10)
        if byte is not None:
            buffer.append(byte)
            t_quiet = time.monotonic()
        else:
            time.sleep(0.001)
            if got_any_uid and (time.monotonic() - t_quiet) > 0.12:
                break
            continue

        while buffer and buffer[0] != STX:
            del buffer[0]
        if len(buffer) < HEADER_LEN:
            continue

        data_len = buffer[3]
        need = HEADER_LEN + data_len + FOOTER_LEN
        if len(buffer) < need:
            continue

        frame = buffer[:need]
        if not verify_frame(frame):
            del buffer[0]
            continue

        log_line("recv", to_hex_string(frame), logger)
        cmd = frame[2]

        if cmd == CMD_ACK and frame[4] == DETAIL_INV2_F0:
            if len(frame) >= HEADER_LEN + FOOTER_LEN + 2:
                expected = frame[5]
                result.expected_count = expected
                log_line("cmt", f"UID数 : {expected}", logger)
        elif cmd == RSP_UID and len(frame) >= HEADER_LEN + FOOTER_LEN + 9:
            item = InventoryItem()
            item.dsfid = frame[4]
            uid_lsb = frame[5:13]
            item.uid = list(reversed(uid_lsb))
            result.items.append(item)
            got_any_uid = True

            log_line("cmt", f"DSFID : {item.dsfid:02X}", logger)
            log_line("cmt", f"UID   : {to_hex_string(item.uid)}", logger)
        elif cmd == CMD_NACK:
            result.error_message = parse_nack_message(frame)
            return result

        del buffer[:need]
        if expected >= 0 and len(result.items) >= expected:
            break

    if not result.items and not result.error_message:
        result.error_message = "UIDを取得できませんでした（タイムアウト/対象なし）"
    return result


# ===============================
# ブザー制御
# ===============================
def buzzer(
    sp: SerialConnection,
    response_type: int,
    sound_type: int,
    timeout_ms: int,
    logger: Optional[Callable[[str], None]] = None,
) -> bool:
    tone = "ピー" if sound_type == 0x00 else "ピッピッピ" if sound_type == 0x01 else f"type=0x{sound_type:02X}"
    log_line("cmt", f"/* ブザー制御: {tone} */", logger)

    payload = [response_type & 0xFF, sound_type & 0xFF]
    tx = make_frame(ADDR_DEFAULT, CMD_BUZZER, payload)
    rx = communicate(sp, tx, timeout_ms, True, logger)
    if not rx:
        return False

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
    if not verify_frame(frame):
        return False
    if frame[2] == CMD_NACK:
        log_line("cmt", f"NACK: {parse_nack_message(frame)}", logger)
        return False
    return frame[2] == CMD_ACK


# ===============================
# GUI アプリケーション
# ===============================
class Application(tk.Tk):
    """シンプルな GUI（Tkinter）で C++ サンプルの操作を再現."""

    def __init__(self) -> None:
        super().__init__()
        self.title("TR3 Python Sample")
        self.geometry("720x540")

        self.connection: Optional[SerialConnection] = None
        self.reader_mode_raw = ReaderModeRaw()
        self.reader_mode_pretty = ReaderModePretty()
        self._busy = False

        self._build_widgets()
        self.refresh_ports()

    # -------------------------------
    # UI 構築
    # -------------------------------
    def _build_widgets(self) -> None:
        frame = ttk.Frame(self, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)

        # COM ポート選択
        port_label = ttk.Label(frame, text="COMポート")
        port_label.grid(row=0, column=0, sticky=tk.W)
        self.port_var = tk.StringVar()
        self.port_combo = ttk.Combobox(frame, textvariable=self.port_var, width=20, state="readonly")
        self.port_combo.grid(row=0, column=1, sticky=tk.W)

        refresh_button = ttk.Button(frame, text="更新", command=self.refresh_ports)
        refresh_button.grid(row=0, column=2, padx=(5, 0))

        # ボーレート選択
        baud_label = ttk.Label(frame, text="ボーレート")
        baud_label.grid(row=1, column=0, sticky=tk.W)
        self.baud_var = tk.StringVar(value="19200")
        self.baud_combo = ttk.Combobox(
            frame,
            textvariable=self.baud_var,
            width=20,
            state="readonly",
            values=["19200", "38400", "57600", "115200", "9600"],
        )
        self.baud_combo.grid(row=1, column=1, sticky=tk.W)

        # 接続／切断ボタン
        self.connect_button = ttk.Button(frame, text="接続", command=self.connect)
        self.connect_button.grid(row=0, column=3, padx=(10, 0))
        self.disconnect_button = ttk.Button(frame, text="切断", command=self.disconnect, state=tk.DISABLED)
        self.disconnect_button.grid(row=0, column=4, padx=(5, 0))

        # インベントリ試行回数
        tries_label = ttk.Label(frame, text="インベントリ試行回数")
        tries_label.grid(row=2, column=0, sticky=tk.W)
        self.tries_var = tk.StringVar(value="1")
        self.tries_entry = ttk.Entry(frame, textvariable=self.tries_var, width=10)
        self.tries_entry.grid(row=2, column=1, sticky=tk.W)

        # 操作ボタン列
        buttons_frame = ttk.Frame(frame)
        buttons_frame.grid(row=3, column=0, columnspan=5, pady=(10, 5), sticky=tk.W)

        self.rom_button = ttk.Button(buttons_frame, text="ROM取得", command=self.handle_read_rom, state=tk.DISABLED)
        self.rom_button.grid(row=0, column=0, padx=(0, 5))

        self.mode_button = ttk.Button(buttons_frame, text="モード読取", command=self.handle_read_mode, state=tk.DISABLED)
        self.mode_button.grid(row=0, column=1, padx=(0, 5))

        self.mode_write_button = ttk.Button(buttons_frame, text="コマンドモードへ", command=self.handle_write_mode, state=tk.DISABLED)
        self.mode_write_button.grid(row=0, column=2, padx=(0, 5))

        self.inventory_button = ttk.Button(buttons_frame, text="Inventory2", command=self.handle_inventory, state=tk.DISABLED)
        self.inventory_button.grid(row=0, column=3, padx=(0, 5))

        self.buzzer_hit_button = ttk.Button(buttons_frame, text="ブザー(ピー)", command=lambda: self.handle_buzzer(0x00), state=tk.DISABLED)
        self.buzzer_hit_button.grid(row=0, column=4, padx=(0, 5))

        self.buzzer_miss_button = ttk.Button(buttons_frame, text="ブザー(ピッピッピ)", command=lambda: self.handle_buzzer(0x01), state=tk.DISABLED)
        self.buzzer_miss_button.grid(row=0, column=5, padx=(0, 5))

        # ログ表示
        log_label = ttk.Label(frame, text="通信ログ")
        log_label.grid(row=4, column=0, columnspan=5, sticky=tk.W, pady=(10, 0))

        self.log_text = tk.Text(frame, height=20, state=tk.DISABLED, font=("Consolas", 10))
        self.log_text.grid(row=5, column=0, columnspan=5, sticky=tk.NSEW)
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.log_text.yview)
        scrollbar.grid(row=5, column=5, sticky=tk.NS)
        self.log_text.configure(yscrollcommand=scrollbar.set)

        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(5, weight=1)

    # -------------------------------
    # ログ表示
    # -------------------------------
    def append_log(self, line: str) -> None:
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, line + "\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    # -------------------------------
    # COM ポート一覧の更新
    # -------------------------------
    def refresh_ports(self) -> None:
        ports = serial.tools.list_ports.comports()
        values = [port.device for port in ports]
        self.port_combo["values"] = values
        if values:
            self.port_combo.current(0)
        else:
            self.port_var.set("")

    # -------------------------------
    # 接続／切断
    # -------------------------------
    def connect(self) -> None:
        if self.connection:
            return
        port = self.port_var.get()
        if not port:
            messagebox.showwarning("接続エラー", "COMポートを選択してください。")
            return
        try:
            baud = int(self.baud_var.get())
        except ValueError:
            messagebox.showwarning("接続エラー", "ボーレートが正しくありません。")
            return

        conn = SerialConnection(port, baud)
        if not conn.open():
            messagebox.showerror("接続エラー", f"ポートを開けませんでした: {conn.last_error}")
            return

        self.connection = conn
        self.append_log(f"*** 接続しました: {port} / {baud}bps")
        self._set_connected_state(True)

    def disconnect(self) -> None:
        if self.connection:
            self.connection.close()
            self.connection = None
            self.append_log("*** 切断しました")
        self._set_connected_state(False)

    def _set_connected_state(self, connected: bool) -> None:
        state = tk.NORMAL if connected else tk.DISABLED
        self.disconnect_button.configure(state=tk.NORMAL if connected else tk.DISABLED)
        self.connect_button.configure(state=tk.DISABLED if connected else tk.NORMAL)
        self.rom_button.configure(state=state)
        self.mode_button.configure(state=state)
        self.mode_write_button.configure(state=state)
        self.inventory_button.configure(state=state)
        self.buzzer_hit_button.configure(state=state)
        self.buzzer_miss_button.configure(state=state)

    # -------------------------------
    # 非同期実行（通信が重いため）
    # -------------------------------
    def run_async(self, func: Callable[[], None]) -> None:
        if self._busy:
            messagebox.showinfo("実行中", "別の操作が完了するまでお待ちください。")
            return
        self._busy = True

        def task() -> None:
            try:
                func()
            finally:
                self.after(0, self._mark_idle)

        threading.Thread(target=task, daemon=True).start()

    def _mark_idle(self) -> None:
        self._busy = False

    # -------------------------------
    # 操作イベント
    # -------------------------------
    def handle_read_rom(self) -> None:
        if not self.connection:
            return

        def job() -> None:
            version = read_rom_version(self.connection, 600, self.append_log)
            if not version:
                self.after(0, lambda: messagebox.showwarning("ROM取得", "ROMバージョンの取得に失敗しました。"))

        self.run_async(job)

    def handle_read_mode(self) -> None:
        if not self.connection:
            return

        def job() -> None:
            success = read_reader_mode(self.connection, self.reader_mode_raw, self.reader_mode_pretty, 600, self.append_log)
            if not success:
                self.after(0, lambda: messagebox.showwarning("動作モード", "動作モードの取得に失敗しました。"))

        self.run_async(job)

    def handle_write_mode(self) -> None:
        if not self.connection:
            return

        def job() -> None:
            success = write_reader_mode_to_command(self.connection, self.reader_mode_raw, 600, self.append_log)
            if success:
                # 再度読み取り、結果を更新する
                read_reader_mode(self.connection, self.reader_mode_raw, self.reader_mode_pretty, 600, self.append_log)
            else:
                self.after(0, lambda: messagebox.showwarning("コマンドモード", "モード設定に失敗しました。"))

        self.run_async(job)

    def handle_inventory(self) -> None:
        if not self.connection:
            return
        try:
            tries = int(self.tries_var.get())
        except ValueError:
            messagebox.showwarning("Inventory2", "試行回数には 1 以上の整数を入力してください。")
            return
        tries = max(1, min(tries, 1000000))

        def job() -> None:
            for index in range(1, tries + 1):
                if tries > 1:
                    self.append_log(f"--- インベントリ試行 {index} / {tries} ---")
                result = run_inventory2(self.connection, 2000, self.append_log)
                if result.error_message:
                    self.append_log(f"NACK/エラー: {result.error_message}")
                    buzzer(self.connection, 0x01, 0x01, 600, self.append_log)
                else:
                    self.append_log(f"取得UID数: {len(result.items)}")
                    for i, item in enumerate(result.items):
                        self.append_log(f"  [{i}] {to_hex_string(item.uid)}")
                    if result.items:
                        buzzer(self.connection, 0x01, 0x00, 600, self.append_log)
                    else:
                        buzzer(self.connection, 0x01, 0x01, 600, self.append_log)
                if index < tries:
                    time.sleep(0.1)

        self.run_async(job)

    def handle_buzzer(self, sound_type: int) -> None:
        if not self.connection:
            return

        def job() -> None:
            success = buzzer(self.connection, 0x01, sound_type, 600, self.append_log)
            if not success:
                self.after(0, lambda: messagebox.showwarning("ブザー", "ブザー制御に失敗しました。"))

        self.run_async(job)


if __name__ == "__main__":
    app = Application()
    app.mainloop()