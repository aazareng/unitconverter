"""
Unit Converter / calculator — Python replacement for A.Azar's AHK converter.

Type a unit-aware expression and it evaluates to a base unit, then shows
conversions within that dimension. Click any row (or its copy button) to copy.

Examples
--------
    12mm+1ft-2in      -> 266 mm      (length, base = mm)
    1ft 2in           -> 355.6 mm    (adjacent quantities add)
    (3+2)*4in         -> 508 mm
    72F               -> 22.22 C     (temperature, base = C)
    5kg-200g          -> 10.582 lb   (mass, base = lb)
    12mm/3mm          -> 4           (a ratio: dimensionless)
    45                -> shows the old "interpret as everything" table

Base units: length = mm, temperature = C, mass = lb.

Rules
-----
  +  -   operands must share a dimension (can't add length to mass).
  *  /   quantity times/over a plain number keeps the dimension;
         quantity / quantity of the same dimension gives a ratio (a number).
  Two quantities written next to each other are added (1ft 2in).

Extra units can be defined in `unit_converter.ini` (see the auto-generated
sample). No third-party packages required — tkinter ships with Python.
"""

import configparser
import sys
import tkinter as tk
from pathlib import Path

INI_NAME = "unit_converter.ini"
DECIMALS = 4

# --- unit registry --------------------------------------------------------
# Linear units: base_value = value * factor.  Base per dimension:
#   length -> mm,  mass -> lb.
LINEAR_UNITS = {
    # length (to mm)
    "mm": ("length", 1.0), "millimeter": ("length", 1.0), "millimeters": ("length", 1.0),
    "cm": ("length", 10.0), "centimeter": ("length", 10.0),
    "m": ("length", 1000.0), "meter": ("length", 1000.0), "metre": ("length", 1000.0),
    "km": ("length", 1_000_000.0),
    "um": ("length", 0.001), "micron": ("length", 0.001),
    "in": ("length", 25.4), "inch": ("length", 25.4), "inches": ("length", 25.4), '"': ("length", 25.4),
    "ft": ("length", 304.8), "foot": ("length", 304.8), "feet": ("length", 304.8), "'": ("length", 304.8),
    "yd": ("length", 914.4), "yard": ("length", 914.4),
    "thou": ("length", 0.0254), "mil": ("length", 0.0254),
    # mass / weight (to lb)
    "lb": ("mass", 1.0), "lbs": ("mass", 1.0), "pound": ("mass", 1.0), "pounds": ("mass", 1.0),
    "oz": ("mass", 0.0625), "ounce": ("mass", 0.0625), "ounces": ("mass", 0.0625),
    "g": ("mass", 0.00220462262185), "gram": ("mass", 0.00220462262185), "grams": ("mass", 0.00220462262185),
    "kg": ("mass", 2.20462262185), "kilogram": ("mass", 2.20462262185),
    "mg": ("mass", 2.20462262185e-6),
    "st": ("mass", 14.0), "stone": ("mass", 14.0),
    "ton": ("mass", 2000.0),       # US short ton
    "tonne": ("mass", 2204.62262), "t": ("mass", 2204.62262),  # metric tonne
}

# Temperature is affine, so it needs explicit to/from-base (base = C).
TEMP_UNITS = {
    "c": (lambda v: v, lambda b: b),
    "f": (lambda v: (v - 32) / 1.8, lambda b: b * 1.8 + 32),
    "k": (lambda v: v - 273.15, lambda b: b + 273.15),
}

# Ordered conversions to display for each dimension: (label, unit key).
LENGTH_OUT = [("mm", "mm"), ("cm", "cm"), ("m", "m"),
              ("in", "in"), ("ft", "ft"), ("yd", "yd"), ("thou", "thou")]
MASS_OUT = [("lb", "lb"), ("oz", "oz"), ("g", "g"), ("kg", "kg")]
TEMP_OUT = [("°C", "c"), ("°F", "f"), ("K", "k")]

DIM_LABEL = {"length": "length", "mass": "mass/weight", "temperature": "temperature"}


class Quantity:
    """A magnitude expressed in its dimension's base unit. dim=None means a
    plain number (dimensionless)."""
    __slots__ = ("base", "dim")

    def __init__(self, base, dim):
        self.base = base
        self.dim = dim


# --- tokenizer ------------------------------------------------------------
def tokenize(text):
    tokens = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch.isspace():
            i += 1
            continue
        if ch in "+-*/()":
            tokens.append(("op", ch))
            i += 1
            continue
        if ch.isdigit() or ch == ".":
            j = i
            while j < n and (text[j].isdigit() or text[j] == "."):
                j += 1
            num = text[i:j]
            try:
                value = float(num)
            except ValueError:
                raise ValueError(f"bad number '{num}'")
            i = j
            # optional unit right after the number
            k = i
            while k < n and (text[k].isalpha() or text[k] in "°'\"µ"):
                k += 1
            unit = text[i:k]
            i = k
            tokens.append(("num", value, unit or None))
            continue
        raise ValueError(f"unexpected character '{ch}'")
    return tokens


def unit_to_quantity(value, unit):
    if unit is None:
        return Quantity(value, None)
    u = unit.replace("°", "").replace("µ", "u")
    key = u.lower() if u not in ("'", '"') else u
    if key in TEMP_UNITS:
        to_base, _ = TEMP_UNITS[key]
        return Quantity(to_base(value), "temperature")
    if key in LINEAR_UNITS:
        dim, factor = LINEAR_UNITS[key]
        return Quantity(value * factor, dim)
    raise ValueError(f"unknown unit '{unit}'")


# --- recursive-descent parser --------------------------------------------
class Parser:
    def __init__(self, tokens):
        self.toks = tokens
        self.pos = 0

    def peek(self):
        return self.toks[self.pos] if self.pos < len(self.toks) else None

    def next(self):
        t = self.toks[self.pos]
        self.pos += 1
        return t

    def parse(self):
        v = self.expr()
        if self.peek() is not None:
            raise ValueError("unexpected trailing input")
        return v

    def expr(self):
        left = self.term()
        while True:
            t = self.peek()
            if t and t[0] == "op" and t[1] in "+-":
                self.next()
                right = self.term()
                left = add_sub(left, right, t[1])
            elif t and t[0] == "num":          # adjacency -> implicit addition
                right = self.term()
                left = add_sub(left, right, "+")
            else:
                break
        return left

    def term(self):
        left = self.factor()
        while True:
            t = self.peek()
            if t and t[0] == "op" and t[1] in "*/":
                self.next()
                right = self.factor()
                left = mul_div(left, right, t[1])
            else:
                break
        return left

    def factor(self):
        t = self.peek()
        if t is None:
            raise ValueError("unexpected end of input")
        if t[0] == "op" and t[1] == "(":
            self.next()
            v = self.expr()
            close = self.peek()
            if not (close and close[0] == "op" and close[1] == ")"):
                raise ValueError("missing ')'")
            self.next()
            return v
        if t[0] == "op" and t[1] in "+-":
            self.next()
            v = self.factor()
            if t[1] == "-":
                return Quantity(-v.base, v.dim)
            return v
        if t[0] == "num":
            self.next()
            return unit_to_quantity(t[1], t[2])
        raise ValueError("expected a value")


def _friendly(dim):
    return DIM_LABEL.get(dim, "number")


def add_sub(a, b, op):
    # A number written with no unit is assumed to already be in the base unit
    # of whatever it's combined with, so "12.7 + .5in" == 25.4 mm.
    if a.dim is not None and b.dim is not None and a.dim != b.dim:
        raise ValueError(f"can't add/subtract {_friendly(a.dim)} and {_friendly(b.dim)}")
    dim = a.dim if a.dim is not None else b.dim
    return Quantity(a.base + b.base if op == "+" else a.base - b.base, dim)


def mul_div(a, b, op):
    if op == "*":
        if a.dim is None:
            return Quantity(a.base * b.base, b.dim)
        if b.dim is None:
            return Quantity(a.base * b.base, a.dim)
        raise ValueError("can't multiply two units together")
    # division
    if b.dim is None:
        if b.base == 0:
            raise ValueError("divide by zero")
        return Quantity(a.base / b.base, a.dim)
    if a.dim == b.dim:
        if b.base == 0:
            raise ValueError("divide by zero")
        return Quantity(a.base / b.base, None)   # ratio -> plain number
    raise ValueError(f"can't divide {_friendly(a.dim)} by {_friendly(b.dim)}")


def evaluate(text):
    """Return (Quantity, had_unit). Raises ValueError on bad input."""
    tokens = tokenize(text)
    if not tokens:
        raise ValueError("empty")
    had_unit = any(t[0] == "num" and t[2] is not None for t in tokens)
    return Parser(tokens).parse(), had_unit


# --- formatting & conversion output --------------------------------------
def fmt(value):
    s = f"{round(value, DECIMALS):.{DECIMALS}f}".rstrip("0").rstrip(".")
    return "0" if s in ("", "-0") else s


def from_base_linear(base, key):
    _, factor = LINEAR_UNITS[key]
    return base / factor


def conversions_for(q, had_unit):
    """Return (headline, rows) where rows is a list of (label, value_str)."""
    if q.dim == "length":
        rows = [(lbl, fmt(from_base_linear(q.base, key))) for lbl, key in LENGTH_OUT]
        return (f"= {fmt(q.base)} mm  (length)", rows)
    if q.dim == "mass":
        rows = [(lbl, fmt(from_base_linear(q.base, key))) for lbl, key in MASS_OUT]
        return (f"= {fmt(q.base)} lb  (mass)", rows)
    if q.dim == "temperature":
        rows = [(lbl, fmt(TEMP_UNITS[key][1](q.base))) for lbl, key in TEMP_OUT]
        return (f"= {fmt(q.base)} °C  (temperature)", rows)
    # dimensionless
    if had_unit:
        # a ratio like 12mm/3mm -> just the number
        return (f"= {fmt(q.base)}", [("value", fmt(q.base))])
    # bare number: replay the old "interpret as everything" table
    v = q.base
    rows = [
        ("mm → in", fmt(v / 25.4)),
        ("in → mm", fmt(v * 25.4)),
        ("°F → °C", fmt((v - 32) / 1.8)),
        ("°C → °F", fmt(v * 1.8 + 32)),
        ("g → oz", fmt(v * 0.0352739619)),
        ("oz → g", fmt(v * 28.349523125)),
        ("lb → kg", fmt(v * 0.45359237)),
        ("kg → lb", fmt(v * 2.20462262185)),
    ]
    return (f"{fmt(v)}  (no unit — showing all interpretations)", rows)


# --- config (optional extra units) ---------------------------------------
def load_custom_units(ini_path):
    if not ini_path.exists():
        ini_path.write_text(
            "; Add your own units here. Factor converts TO the base unit.\n"
            "; Base units: length = mm, mass = lb.  (temperature is built in)\n"
            "[LENGTH]\n"
            "; pt = 0.352778     ; typographic point -> mm\n"
            "[MASS]\n"
            "; grain = 0.000142857  ; grain -> lb\n",
            encoding="utf-8",
        )
        return
    parser = configparser.ConfigParser()
    try:
        parser.read(ini_path, encoding="utf-8")
    except configparser.Error:
        return
    for section, dim in (("LENGTH", "length"), ("MASS", "mass")):
        if parser.has_section(section):
            for alias, raw in parser.items(section):
                try:
                    LINEAR_UNITS[alias.lower()] = (dim, float(raw))
                except ValueError:
                    continue


# --- clipboard & paths ----------------------------------------------------
def set_clipboard(text):
    """Copy text to the Windows clipboard via the Win32 API so it persists
    after the app closes. (Tk's own clipboard can be lost on exit.) Returns
    True on success; caller falls back to Tk otherwise."""
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        CF_UNICODETEXT, GMEM_MOVEABLE = 13, 0x0002
        k32, u32 = ctypes.windll.kernel32, ctypes.windll.user32
        k32.GlobalAlloc.restype = ctypes.c_void_p
        k32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
        k32.GlobalLock.restype = ctypes.c_void_p
        k32.GlobalLock.argtypes = [ctypes.c_void_p]
        k32.GlobalUnlock.argtypes = [ctypes.c_void_p]
        u32.OpenClipboard.argtypes = [ctypes.c_void_p]
        u32.SetClipboardData.restype = ctypes.c_void_p
        u32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
        data = text.encode("utf-16-le") + b"\x00\x00"
        if not u32.OpenClipboard(None):
            return False
        try:
            u32.EmptyClipboard()
            handle = k32.GlobalAlloc(GMEM_MOVEABLE, len(data))
            ptr = k32.GlobalLock(handle)
            ctypes.memmove(ptr, data, len(data))
            k32.GlobalUnlock(handle)
            u32.SetClipboardData(CF_UNICODETEXT, handle)
        finally:
            u32.CloseClipboard()
        return True
    except Exception:
        return False


def app_dir():
    """Folder holding the script — or the .exe when frozen by PyInstaller."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


# --- GUI ------------------------------------------------------------------
class ConverterApp:
    def __init__(self, root):
        self.root = root
        root.title("Unit Converter")
        root.attributes("-topmost", True)
        root.resizable(False, False)
        root.minsize(300, 120)

        top = tk.Frame(root)
        top.pack(fill="x", padx=8, pady=(8, 4))
        tk.Label(top, text="Expression:").pack(side="left")
        self.entry = tk.Entry(top, width=24, font=("Consolas", 12))
        self.entry.pack(side="left", fill="x", expand=True, padx=(6, 0))
        self.entry.bind("<KeyRelease>", lambda _e: self.recompute())
        self.entry.focus_set()

        self.headline = tk.Label(root, text="", font=("Segoe UI", 10, "bold"),
                                 anchor="w", fg="#0a5")
        self.headline.pack(fill="x", padx=8)

        self.rows_frame = tk.Frame(root)
        self.rows_frame.pack(fill="both", expand=True, padx=8, pady=4)

        self.status = tk.Label(root, text="Enter to copy result · Esc to quit",
                               fg="gray", anchor="w")
        self.status.pack(fill="x", padx=8, pady=(0, 6))

        root.bind("<Escape>", lambda _e: root.destroy())
        root.bind("<Return>", lambda _e: self.copy_first())
        self.first_value = None
        self.recompute()

    def clear_rows(self):
        for w in self.rows_frame.winfo_children():
            w.destroy()

    def recompute(self):
        self.clear_rows()
        text = self.entry.get().strip()
        if not text:
            self.headline.config(text="", fg="#0a5")
            self.first_value = None
            return
        try:
            q, had_unit = evaluate(text)
        except ValueError as e:
            self.headline.config(text=f"⚠ {e}", fg="#c00")
            self.first_value = None
            return
        headline, rows = conversions_for(q, had_unit)
        self.headline.config(text=headline, fg="#0a5")
        self.first_value = rows[0][1] if rows else None
        for label, value in rows:
            self.add_row(label, value)

    def add_row(self, label, value):
        row = tk.Frame(self.rows_frame)
        row.pack(fill="x", pady=1)
        tk.Label(row, text=label, width=10, anchor="w").pack(side="left")
        val = tk.Label(row, text=value, width=16, anchor="w",
                       font=("Consolas", 11), bg="white", relief="sunken", bd=1)
        val.pack(side="left", fill="x", expand=True, padx=(0, 6))
        tk.Button(row, text="copy", width=6,
                  command=lambda v=value: self.copy(v)).pack(side="left")
        # click the value box itself to copy too
        val.bind("<Button-1>", lambda _e, v=value: self.copy(v))

    def copy(self, value):
        if not set_clipboard(value):          # non-Windows fallback
            self.root.clipboard_clear()
            self.root.clipboard_append(value)
            self.root.update()
        self.root.destroy()                   # copy closes the app

    def copy_first(self):
        if self.first_value is not None:
            self.copy(self.first_value)


def main():
    ini_path = app_dir() / INI_NAME
    load_custom_units(ini_path)
    root = tk.Tk()
    ConverterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
