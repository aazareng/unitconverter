"""Show where the bytes went in a PyInstaller onefile exe.

    python tools\\exe_report.py dist\\unit_converter.exe

Reads the bundle's table of contents and prints the largest entries plus a
category breakdown, so you can see what an exclude actually bought you
instead of guessing. Sizes are reported both as stored inside the exe
(what you pay) and raw (what gets unpacked to %TEMP% at launch).

Pure stdlib; runs on any OS against a Windows exe.
"""

import collections
import struct
import sys

COOKIE_MAGIC = b"MEI\014\013\012\013\016"


def read_toc(path):
    """Yield (stored_size, raw_size, typecode, name) for every bundled file."""
    with open(path, "rb") as fh:
        blob = fh.read()
    pos = blob.rfind(COOKIE_MAGIC)
    if pos < 0:
        raise SystemExit(f"{path}: not a PyInstaller onefile bundle "
                         "(a --onedir build has no embedded archive)")
    _, pkg_len, toc_off, toc_len, pyvers = struct.unpack(">8sIIII", blob[pos:pos + 24])
    pylib = blob[pos + 24:pos + 24 + 64].split(b"\0")[0].decode("latin1")
    start = len(blob) - pkg_len
    cur, end = start + toc_off, start + toc_off + toc_len
    entries = []
    while cur < end:
        elen, _epos, stored, raw, _flag, typ = struct.unpack("!iiiiBc", blob[cur:cur + 18])
        if elen <= 0:
            break
        name = blob[cur + 18:cur + elen].split(b"\0")[0].decode("latin1")
        entries.append((stored, raw, typ.decode("latin1"), name))
        cur += elen
    return entries, pylib, pyvers, len(blob)


def categorize(name):
    n = name.replace("\\", "/").lower()
    if "libcrypto" in n or "libssl" in n:
        return "OpenSSL (excludable)"
    if "tzdata" in n:
        return "Tcl timezone db (excludable)"
    if "/msgs/" in n:
        return "Tcl/Tk translations (excludable)"
    if n.endswith((".dll", ".pyd", ".so")):
        return "binaries (interpreter, Tk, C exts)"
    if n.endswith(".tcl") or "/encoding/" in n:
        return "Tcl scripts + encodings"
    return "Python code + misc"


def main(argv):
    if len(argv) != 2:
        raise SystemExit(__doc__)
    entries, pylib, pyvers, total = read_toc(argv[1])
    print(f"{argv[1]}: {total / 1e6:.2f} MB, {len(entries)} bundled files")
    # PyInstaller stores 3.10+ as major*100+minor, older as major*10+minor.
    major, minor = divmod(pyvers, 100 if pyvers >= 100 else 10)
    print(f"interpreter: {pylib} (Python {major}.{minor})\n")

    print("largest entries".center(64, "-"))
    for stored, raw, _typ, name in sorted(entries, reverse=True)[:12]:
        print(f"  {stored / 1e6:6.2f} MB in-exe  ({raw / 1e6:6.2f} MB raw)  {name}")

    by_kind = collections.Counter()
    raw_kind = collections.Counter()
    for stored, raw, _typ, name in entries:
        kind = categorize(name)
        by_kind[kind] += stored
        raw_kind[kind] += raw
    print("\n" + "breakdown".center(64, "-"))
    for kind, size in by_kind.most_common():
        print(f"  {kind:34} {size / 1e6:6.2f} MB  ({raw_kind[kind] / 1e6:6.2f} MB raw)")
    print(f"\n  {'TOTAL (archive)':34} {sum(by_kind.values()) / 1e6:6.2f} MB")


if __name__ == "__main__":
    main(sys.argv)
