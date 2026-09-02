#!/usr/bin/env python3
"""Datagame MSX-VTX DG 1.1 - behavioral Python reimplementation.

Based on static reverse engineering of DATAGAME.ROM (16 KiB MSX cartridge ROM).
This is not a Z80 emulator. It recreates the firmware's user-facing terminal/modem
workflow using modern Python, while preserving ROM-derived labels and settings.
"""
from __future__ import annotations

import argparse
import queue
import socket
import threading
import time
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import messagebox, simpledialog

ROM_SIZE = 16_384
ROM_BASE = 0x4000


@dataclass
class ModemConfig:
    baud_rate: str = "1200/75"
    data_bits: int = 7
    parity: str = "PAR"
    stop_bits: int = 1
    standard: str = "CCITT"
    echo: bool = True
    cr_receive: str = "CR/LF"
    cr_transmit: str = "CR"


class Transport:
    """Abstracts the original modem hardware.

    Simulation mode is the default. TCP mode is useful for connecting the recreated
    terminal to a local BBS/telnet-style service without pretending to emulate the
    original analog modem electrically.
    """
    def __init__(self, rx_queue: queue.Queue[str]):
        self.rx_queue = rx_queue
        self.sock: socket.socket | None = None
        self.connected = False
        self.simulated = True

    def connect_tcp(self, host: str, port: int) -> None:
        self.close()
        s = socket.create_connection((host, port), timeout=8)
        s.settimeout(0.5)
        self.sock = s
        self.connected = True
        self.simulated = False
        threading.Thread(target=self._reader, daemon=True).start()

    def connect_simulated(self) -> None:
        self.close()
        self.connected = True
        self.simulated = True
        self.rx_queue.put("\r\nCONECTOU!\r\n")

    def _reader(self) -> None:
        assert self.sock is not None
        while self.connected and self.sock:
            try:
                data = self.sock.recv(4096)
                if not data:
                    break
                self.rx_queue.put(data.decode("latin-1", errors="replace"))
            except socket.timeout:
                continue
            except OSError:
                break
        if self.connected:
            self.rx_queue.put("\r\nDESCONECTADO!\r\n")
        self.close()

    def send(self, text: str) -> None:
        if not self.connected:
            return
        if self.simulated:
            self.rx_queue.put(text)
        elif self.sock:
            try:
                self.sock.sendall(text.encode("latin-1", errors="replace"))
            except OSError:
                self.close()

    def close(self) -> None:
        self.connected = False
        if self.sock:
            try:
                self.sock.close()
            except OSError:
                pass
        self.sock = None


class DatagameApp:
    COLS = 40
    ROWS = 24

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("DATAGAME MSX-VTX DG 1.1 - Python")
        self.cfg = ModemConfig()
        self.rx_queue: queue.Queue[str] = queue.Queue()
        self.transport = Transport(self.rx_queue)
        self.status_var = tk.StringVar(value="DESCONECTADO!")
        self._build_ui()
        self.show_main_menu()
        self.root.after(50, self._poll_rx)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def _build_ui(self) -> None:
        top = tk.Frame(self.root)
        top.pack(fill="both", expand=True, padx=8, pady=8)

        self.screen = tk.Text(
            top,
            width=self.COLS,
            height=self.ROWS,
            font=("Courier New", 14),
            wrap="char",
            undo=False,
        )
        self.screen.pack(fill="both", expand=True)
        self.screen.bind("<Key>", self._terminal_key)

        bar = tk.Frame(self.root)
        bar.pack(fill="x", padx=8, pady=(0, 8))
        tk.Label(bar, textvariable=self.status_var, anchor="w").pack(side="left", fill="x", expand=True)
        tk.Button(bar, text="Configuração", command=self.show_config).pack(side="left", padx=2)
        tk.Button(bar, text="Comunicação", command=self.show_communication).pack(side="left", padx=2)
        tk.Button(bar, text="Terminal", command=self.enter_terminal).pack(side="left", padx=2)
        tk.Button(bar, text="Desconectar", command=self.disconnect).pack(side="left", padx=2)

    def clear(self) -> None:
        self.screen.delete("1.0", "end")

    def write(self, text: str) -> None:
        self.screen.insert("end", text)
        self.screen.see("end")

    def show_main_menu(self) -> None:
        self.clear()
        self.write(
            "      --------------------\n"
            "      DDX-MODEM / TERMINAL\n"
            "      --------------------\n\n"
            "MSX-VTX DG versão 1.1\n"
            "DATAGAME\n\n"
            "[1] CONFIGURAÇÃO\n"
            "[2] COMUNICAÇÃO\n"
            "[3] TERMINAL\n\n"
            "Use os botões abaixo ou as teclas 1-3.\n"
        )
        self.screen.focus_set()

    def show_config(self) -> None:
        while True:
            c = self.cfg
            prompt = (
                "DDX-MODEM / TERMINAL\n\n"
                f"[1] - BAUD-RATE  : {c.baud_rate}\n"
                f"[2] - NO.DE BITS : {c.data_bits}\n"
                f"[3] - PARIDADE   : {c.parity}\n"
                f"[4] - STOP BITS  : {c.stop_bits}\n"
                f"[5] - PADRAO     : {c.standard}\n"
                f"[6] - ECHO       : {'SIM' if c.echo else 'NAO'}\n"
                f"[7] - CR REC.    : {c.cr_receive}\n"
                f"[8] - CR TRANSM. : {c.cr_transmit}\n"
                "[9] - COMUNICACAO\n\n"
                "Escolha 1-9. Cancelar volta ao menu."
            )
            choice = simpledialog.askstring("Configuração", prompt, parent=self.root)
            if choice is None:
                self.show_main_menu(); return
            choice = choice.strip()
            if choice == "1": c.baud_rate = self._cycle(c.baud_rate, ["1200/75", "300/300", "1200/1200"])
            elif choice == "2": c.data_bits = 8 if c.data_bits == 7 else 7
            elif choice == "3": c.parity = self._cycle(c.parity, ["SEM", "IMPAR", "PAR"])
            elif choice == "4": c.stop_bits = 2 if c.stop_bits == 1 else 1
            elif choice == "5": c.standard = self._cycle(c.standard, ["CCITT", "BELL"])
            elif choice == "6": c.echo = not c.echo
            elif choice == "7": c.cr_receive = self._cycle(c.cr_receive, ["CR", "CR/LF"])
            elif choice == "8": c.cr_transmit = self._cycle(c.cr_transmit, ["CR", "CR/LF"])
            elif choice == "9": self.show_communication(); return

    @staticmethod
    def _cycle(value, values):
        return values[(values.index(value) + 1) % len(values)]

    def show_communication(self) -> None:
        self.clear()
        self.write(
            "[1] - CONECTA EM \"ORIGINATE\"\n"
            "[2] - CONECTA EM \"ANSWER\"\n"
            "[3] - AGUARDA LIGACAO\n"
            "[4] - DISCA\n"
            "[5] - VOLTA AO MENU ANTERIOR\n\n"
            "Python: use 1 para conexão simulada, 4 para discar,\n"
            "ou T para conectar a um host TCP.\n"
        )
        self.screen.focus_set()

    def dial(self) -> None:
        number = simpledialog.askstring("Discagem", "NUMERO:", parent=self.root)
        if not number:
            self.status_var.set("CANCELADO")
            return
        self._status_sequence([
            "AGUARDANDO TOM DE DISCAR",
            f"DISCANDO: {number}",
            "AGUARDANDO RESPOSTA",
            "ACESSANDO A LINHA",
        ], self._connected_simulated)

    def _status_sequence(self, states: list[str], done) -> None:
        def step(i=0):
            if i >= len(states):
                done(); return
            self.status_var.set(states[i])
            self.write(f"\n{states[i]}\n")
            self.root.after(450, lambda: step(i + 1))
        step()

    def _connected_simulated(self) -> None:
        self.transport.connect_simulated()
        self.status_var.set("CONECTOU!")
        self.enter_terminal()

    def connect_tcp_dialog(self) -> None:
        host = simpledialog.askstring("TCP", "Host:", parent=self.root)
        if not host: return
        port = simpledialog.askinteger("TCP", "Porta:", initialvalue=23, minvalue=1, maxvalue=65535, parent=self.root)
        if not port: return
        self.status_var.set("ACESSANDO A LINHA")
        try:
            self.transport.connect_tcp(host, port)
            self.status_var.set(f"CONECTOU! {host}:{port}")
            self.enter_terminal()
        except OSError as exc:
            self.status_var.set("SEM RESPOSTA")
            messagebox.showerror("Conexão", str(exc), parent=self.root)

    def enter_terminal(self) -> None:
        self.clear()
        self.write("VIDEOTEXTO / TERMINAL\n")
        self.write("=" * 40 + "\n")
        if not self.transport.connected:
            self.write("DESCONECTADO! Digite T para TCP ou D para discar.\n")
        else:
            self.write("CONECTOU!\n")
        self.write("\n")
        self.screen.focus_set()

    def disconnect(self) -> None:
        self.transport.close()
        self.status_var.set("DESCONECTADO!")
        self.write("\nDESCONECTADO!\n")

    def _terminal_key(self, event):
        ch = event.char
        key = event.keysym
        # Menu shortcuts when not connected / generic navigation.
        if not self.transport.connected:
            if ch == "1": self.show_config(); return "break"
            if ch == "2": self.show_communication(); return "break"
            if ch == "3": self.enter_terminal(); return "break"
            if ch.lower() == "d": self.dial(); return "break"
            if ch.lower() == "t": self.connect_tcp_dialog(); return "break"
            if ch == "4": self.dial(); return "break"
            if ch == "5": self.show_main_menu(); return "break"
        if self.transport.connected:
            if key == "Return":
                out = "\r\n" if self.cfg.cr_transmit == "CR/LF" else "\r"
                self.transport.send(out)
                if self.cfg.echo: self.write("\n")
                return "break"
            if key == "BackSpace":
                self.transport.send("\b")
                if self.cfg.echo:
                    try: self.screen.delete("end-2c", "end-1c")
                    except tk.TclError: pass
                return "break"
            if ch and ch >= " ":
                self.transport.send(ch)
                if self.cfg.echo: self.write(ch)
                return "break"
        return None

    def _poll_rx(self) -> None:
        try:
            while True:
                text = self.rx_queue.get_nowait()
                if self.cfg.cr_receive == "CR/LF":
                    text = text.replace("\r\n", "\n").replace("\r", "\n")
                else:
                    text = text.replace("\r", "\n")
                self.write(text)
        except queue.Empty:
            pass
        self.root.after(50, self._poll_rx)

    def close(self) -> None:
        self.transport.close()
        self.root.destroy()


def inspect_rom(path: str | Path) -> dict:
    data = Path(path).read_bytes()
    if len(data) != ROM_SIZE or data[:2] != b"AB":
        raise ValueError("Arquivo não parece ser esta ROM MSX de 16 KiB")
    word = lambda off: data[off] | (data[off+1] << 8)
    return {
        "size": len(data),
        "signature": data[:2].decode("ascii"),
        "init": word(2),
        "statement": word(4),
        "device": word(6),
        "text": word(8),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Datagame MSX-VTX DG behavioral Python port")
    ap.add_argument("--inspect", metavar="ROM", help="inspeciona o cabeçalho da ROM e sai")
    args = ap.parse_args()
    if args.inspect:
        info = inspect_rom(args.inspect)
        for k, v in info.items():
            print(f"{k}: 0x{v:04X}" if isinstance(v, int) and k not in {"size"} else f"{k}: {v}")
        return
    root = tk.Tk()
    DatagameApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
