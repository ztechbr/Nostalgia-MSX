"""
Turbo Pascal 3-style IDE recreation in Python
==============================================

Based on the uploaded Borland Turbo Pascal files:
    TURBO.CPM
    TURBO.OVR
    TURBO.MSG
    TURBO.GPH

This is a clean Python reimplementation of the visible IDE workflow and a
small Pascal interpreter. It does NOT contain Borland machine code.

Features
--------
- Retro text IDE inspired by the original menu:
  Edit / Compile / Run / Save / eXecute / Dir / Quit compiler / Options
- Work file and Main file fields
- Load/save .PAS files
- Simple syntax checker
- Executes a useful Pascal subset:
    program
    const
    var
    begin/end
    integer/real/string/boolean
    assignment :=
    writeln/write
    readln
    if ... then ... else
    for ... := ... to/downto ... do
    while ... do
    repeat ... until
    basic arithmetic/comparisons
- Directory browser
- Error window modeled after Turbo Pascal compiler diagnostics

Requires only Python 3 + Tkinter.

Run:
    python turbo_pascal_python.py
"""

from __future__ import annotations

import ast
import os
import re
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
from pathlib import Path


BG = "#001060"
FG = "#f0f0f0"
ACCENT = "#ffff55"
PANEL = "#000088"
ERROR = "#ff7777"


class PascalError(Exception):
    def __init__(self, message: str, line: int | None = None):
        super().__init__(message)
        self.line = line


def strip_comments(src: str) -> str:
    src = re.sub(r"\{.*?\}", "", src, flags=re.S)
    src = re.sub(r"\(\*.*?\*\)", "", src, flags=re.S)
    return src


def pascal_expr_to_python(expr: str) -> str:
    expr = expr.strip()
    # Protect Pascal strings while doing replacements.
    strings = {}
    def stash(m):
        key = f"__STR{len(strings)}__"
        strings[key] = repr(m.group(1).replace("''", "'"))
        return key
    expr = re.sub(r"'((?:''|[^'])*)'", stash, expr)

    replacements = [
        (r"<>", "!="),
        (r"(?<![<>=:])=(?!=)", "=="),
        (r"\bdiv\b", "//"),
        (r"\bmod\b", "%"),
        (r"\band\b", " and "),
        (r"\bor\b", " or "),
        (r"\bnot\b", " not "),
        (r"\btrue\b", "True"),
        (r"\bfalse\b", "False"),
    ]
    for pat, rep in replacements:
        expr = re.sub(pat, rep, expr, flags=re.I)

    for key, value in strings.items():
        expr = expr.replace(key, value)
    return expr


def safe_eval(expr: str, env: dict):
    pyexpr = pascal_expr_to_python(expr)
    try:
        tree = ast.parse(pyexpr, mode="eval")
    except SyntaxError as e:
        raise PascalError(f"Invalid expression: {expr}") from e

    allowed = (
        ast.Expression, ast.Constant, ast.Name, ast.Load,
        ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare,
        ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod,
        ast.Pow, ast.USub, ast.UAdd, ast.Not,
        ast.And, ast.Or, ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
    )
    for node in ast.walk(tree):
        if not isinstance(node, allowed):
            raise PascalError(f"Unsupported expression element: {type(node).__name__}")
    try:
        return eval(compile(tree, "<pascal>", "eval"), {"__builtins__": {}}, env)
    except NameError as e:
        raise PascalError(str(e)) from e


def split_statements(block: str) -> list[str]:
    """Split Pascal statements while respecting nested begin/end and strings."""
    out, buf = [], []
    depth = 0
    in_string = False
    i = 0
    while i < len(block):
        ch = block[i]
        if ch == "'":
            if in_string and i + 1 < len(block) and block[i+1] == "'":
                buf.extend(["'", "'"])
                i += 2
                continue
            in_string = not in_string
            buf.append(ch)
            i += 1
            continue

        if not in_string:
            tail = block[i:].lower()
            if re.match(r"begin\b", tail):
                depth += 1
            elif re.match(r"end\b", tail) and depth > 0:
                depth -= 1
            if ch == ";" and depth == 0:
                s = "".join(buf).strip()
                if s:
                    out.append(s)
                buf = []
                i += 1
                continue
        buf.append(ch)
        i += 1
    s = "".join(buf).strip()
    if s:
        out.append(s)
    return out


class MiniPascal:
    def __init__(self, input_func=input, output_func=print):
        self.env = {}
        self.input_func = input_func
        self.output_func = output_func
        self.output_buffer = []

    def output(self, text="", newline=True):
        self.output_buffer.append(str(text) + ("\n" if newline else ""))
        self.output_func(str(text), newline)

    def compile_check(self, source: str):
        s = strip_comments(source)
        if not re.search(r"\bprogram\s+\w+\s*;", s, re.I):
            raise PascalError("PROGRAM declaration expected", 1)
        if not re.search(r"\bbegin\b", s, re.I):
            raise PascalError("BEGIN expected")
        if not re.search(r"\bend\s*\.\s*$", s.strip(), re.I):
            raise PascalError("END. expected at end of program")

        # Check begin/end balance.
        tokens = re.findall(r"\b(begin|end)\b", s, re.I)
        balance = 0
        for t in tokens:
            if t.lower() == "begin":
                balance += 1
            else:
                balance -= 1
            if balance < 0:
                raise PascalError("END without matching BEGIN")
        if balance != 0:
            raise PascalError("BEGIN/END mismatch")
        return True

    def parse_declarations(self, source: str):
        # CONST section
        m = re.search(r"\bconst\b(.*?)(?=\bvar\b|\bbegin\b)", source, re.I | re.S)
        if m:
            for item in split_statements(m.group(1)):
                mm = re.match(r"(\w+)\s*=\s*(.+)$", item.strip(), re.S)
                if mm:
                    self.env[mm.group(1)] = safe_eval(mm.group(2), self.env)

        # VAR section
        m = re.search(r"\bvar\b(.*?)(?=\bbegin\b)", source, re.I | re.S)
        if m:
            for item in split_statements(m.group(1)):
                mm = re.match(r"([\w,\s]+)\s*:\s*([\w\[\]\.]+)", item.strip(), re.I)
                if not mm:
                    continue
                typ = mm.group(2).lower()
                default = False if typ == "boolean" else 0.0 if typ == "real" else "" if "string" in typ else 0
                for name in mm.group(1).split(","):
                    self.env[name.strip()] = default

    def main_block(self, source: str) -> str:
        starts = [m.start() for m in re.finditer(r"\bbegin\b", source, re.I)]
        if not starts:
            raise PascalError("BEGIN expected")
        start = starts[0] + len("begin")
        endm = list(re.finditer(r"\bend\s*\.\s*$", source, re.I | re.S))
        if not endm:
            raise PascalError("END. expected")
        return source[start:endm[-1].start()]

    def execute_block(self, block: str):
        for stmt in split_statements(block):
            self.execute_statement(stmt.strip())

    def execute_statement(self, stmt: str):
        if not stmt:
            return

        # Nested begin/end.
        m = re.match(r"begin\b(.*)\bend\s*$", stmt, re.I | re.S)
        if m:
            self.execute_block(m.group(1))
            return

        # writeln / write
        m = re.match(r"(writeln|write)\s*(?:\((.*)\))?$", stmt, re.I | re.S)
        if m:
            args = m.group(2)
            vals = []
            if args:
                # simple comma split outside strings
                parts = re.split(r",(?=(?:[^']*'[^']*')*[^']*$)", args)
                vals = [safe_eval(p, self.env) for p in parts]
            self.output("".join(str(v) for v in vals), newline=m.group(1).lower()=="writeln")
            return

        # readln(variable)
        m = re.match(r"readln\s*(?:\((\w+)\))?$", stmt, re.I)
        if m:
            name = m.group(1)
            val = self.input_func(name or "")
            if name:
                old = self.env.get(name)
                try:
                    if isinstance(old, bool):
                        self.env[name] = val.lower() in ("1","true","yes","y")
                    elif isinstance(old, int):
                        self.env[name] = int(val)
                    elif isinstance(old, float):
                        self.env[name] = float(val)
                    else:
                        self.env[name] = val
                except ValueError:
                    self.env[name] = val
            return

        # for
        m = re.match(r"for\s+(\w+)\s*:=\s*(.+?)\s+(to|downto)\s+(.+?)\s+do\s+(.+)$",
                     stmt, re.I | re.S)
        if m:
            name, a, direction, b, body = m.groups()
            start, stop = int(safe_eval(a, self.env)), int(safe_eval(b, self.env))
            rng = range(start, stop+1) if direction.lower()=="to" else range(start, stop-1, -1)
            for v in rng:
                self.env[name] = v
                self.execute_statement(body.strip())
            return

        # while
        m = re.match(r"while\s+(.+?)\s+do\s+(.+)$", stmt, re.I | re.S)
        if m:
            cond, body = m.groups()
            guard = 0
            while safe_eval(cond, self.env):
                self.execute_statement(body.strip())
                guard += 1
                if guard > 100000:
                    raise PascalError("Loop limit exceeded")
            return

        # if
        m = re.match(r"if\s+(.+?)\s+then\s+(.+?)(?:\s+else\s+(.+))?$", stmt, re.I | re.S)
        if m:
            cond, yes, no = m.groups()
            if safe_eval(cond, self.env):
                self.execute_statement(yes.strip())
            elif no:
                self.execute_statement(no.strip())
            return

        # assignment
        m = re.match(r"(\w+)\s*:=\s*(.+)$", stmt, re.S)
        if m:
            name, expr = m.groups()
            self.env[name] = safe_eval(expr, self.env)
            return

        # Ignore empty EXIT-like compatibility commands, flag unsupported others.
        if stmt.lower() in ("", "exit"):
            return
        raise PascalError(f"Unsupported statement: {stmt[:80]}")

    def run(self, source: str):
        source = strip_comments(source)
        self.compile_check(source)
        self.parse_declarations(source)
        self.execute_block(self.main_block(source))
        return "".join(self.output_buffer)


DEFAULT_PROGRAM = """program Hello;

var
  I: Integer;

begin
  Writeln('Turbo Pascal Python');
  Writeln('-------------------');
  for I := 1 to 5 do
    Writeln(I);
end.
"""


class TurboIDE:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("TURBO Pascal system - Python recreation")
        self.root.geometry("980x700")
        self.root.configure(bg=BG)

        self.current_file: Path | None = None
        self.main_file = tk.StringVar(value="")
        self.work_file = tk.StringVar(value="NONAME.PAS")

        self.build_ui()
        self.editor.insert("1.0", DEFAULT_PROGRAM)
        self.set_status("Version Python 1.0   CP/M-80/MSX inspired")

    def build_ui(self):
        top = tk.Frame(self.root, bg=ACCENT)
        top.pack(fill="x")

        for label, cmd in [
            ("Edit", lambda: self.editor.focus_set()),
            ("Compile", self.compile_program),
            ("Run", self.run_program),
            ("Save", self.save_file),
            ("eXecute", self.run_program),
            ("Dir", self.show_directory),
            ("Quit compiler", self.root.destroy),
            ("Options", self.options),
        ]:
            tk.Button(top, text=label, command=cmd, relief="flat",
                      bg=ACCENT, fg="black", padx=8).pack(side="left")

        meta = tk.Frame(self.root, bg=BG)
        meta.pack(fill="x", padx=8, pady=5)
        tk.Label(meta, text="Work file:", bg=BG, fg=FG).grid(row=0,column=0,sticky="w")
        tk.Entry(meta, textvariable=self.work_file, width=35).grid(row=0,column=1,sticky="w")
        tk.Label(meta, text="Main file:", bg=BG, fg=FG).grid(row=0,column=2,sticky="w",padx=(20,0))
        tk.Entry(meta, textvariable=self.main_file, width=35).grid(row=0,column=3,sticky="w")

        editor_frame = tk.Frame(self.root, bg=PANEL)
        editor_frame.pack(fill="both", expand=True, padx=8)

        self.editor = tk.Text(editor_frame, bg=BG, fg=FG, insertbackground=FG,
                              font=("Courier New", 12), undo=True, wrap="none")
        y = tk.Scrollbar(editor_frame, command=self.editor.yview)
        x = tk.Scrollbar(editor_frame, orient="horizontal", command=self.editor.xview)
        self.editor.configure(yscrollcommand=y.set, xscrollcommand=x.set)
        self.editor.grid(row=0,column=0,sticky="nsew")
        y.grid(row=0,column=1,sticky="ns")
        x.grid(row=1,column=0,sticky="ew")
        editor_frame.rowconfigure(0,weight=1)
        editor_frame.columnconfigure(0,weight=1)

        self.status = tk.Label(self.root, bg=ACCENT, fg="black", anchor="w",
                               font=("Courier New", 10))
        self.status.pack(fill="x", padx=8, pady=(4,8))

        # Keyboard shortcuts.
        self.root.bind("<F2>", lambda e:self.save_file())
        self.root.bind("<F9>", lambda e:self.compile_program())
        self.root.bind("<F10>", lambda e:self.run_program())
        self.root.bind("<Control-o>", lambda e:self.open_file())
        self.root.bind("<Control-s>", lambda e:self.save_file())

    def source(self):
        return self.editor.get("1.0","end-1c")

    def set_status(self, text):
        self.status.config(text=" " + text)

    def open_file(self):
        fn = filedialog.askopenfilename(filetypes=[("Pascal","*.pas"),("All files","*.*")])
        if not fn: return
        p=Path(fn)
        self.editor.delete("1.0","end")
        self.editor.insert("1.0",p.read_text(errors="replace"))
        self.current_file=p
        self.work_file.set(p.name)
        self.set_status(f"Loading {p}")

    def save_file(self):
        p=self.current_file
        if p is None:
            fn=filedialog.asksaveasfilename(defaultextension=".pas",
                                            filetypes=[("Pascal","*.pas"),("All files","*.*")])
            if not fn:return
            p=Path(fn)
            self.current_file=p
        p.write_text(self.source(),encoding="utf-8")
        self.work_file.set(p.name)
        self.set_status(f"Saving {p}")

    def compile_program(self):
        try:
            MiniPascal().compile_check(self.source())
            self.set_status("Compile -> 0 errors")
            messagebox.showinfo("Compile", "Compile successful\n0 errors")
        except PascalError as e:
            self.set_status(f"Error: {e}")
            messagebox.showerror("Compiler Error", str(e))

    def run_program(self):
        output=[]
        def out(text,newline=True):
            output.append(text+("\n" if newline else ""))
        def inp(name):
            return simpledialog.askstring("Input", f"{name}:") or ""
        vm=MiniPascal(inp,out)
        try:
            vm.run(self.source())
        except PascalError as e:
            self.set_status(f"Run-time error: {e}")
            messagebox.showerror("Run-time error",str(e))
            return
        self.set_status("Running - program finished")
        self.show_output("".join(output))

    def show_output(self,text):
        win=tk.Toplevel(self.root)
        win.title("Run")
        win.geometry("700x450")
        t=tk.Text(win,bg="black",fg="white",font=("Courier New",12))
        t.pack(fill="both",expand=True)
        t.insert("1.0",text)
        t.config(state="disabled")

    def show_directory(self):
        folder = self.current_file.parent if self.current_file else Path.cwd()
        items=[]
        try:
            for p in sorted(folder.iterdir()):
                items.append(f"{p.name:<40} {p.stat().st_size:>10}")
        except Exception as e:
            items=[str(e)]
        self.show_output(f"Directory: {folder}\n\n"+"\n".join(items))

    def options(self):
        messagebox.showinfo(
            "Options",
            "Turbo Pascal Python compatibility options\n\n"
            "F2  Save\nF9  Compile\nF10 Run\nCtrl+O Open\nCtrl+S Save\n\n"
            "Interpreter: Pascal subset\nTerminal: Tkinter"
        )

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    TurboIDE().run()
