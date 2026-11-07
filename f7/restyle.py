"""F7 restyle for Yapfast.

Run on a clean checkout of Yapfast, from anywhere:    python3 f7/restyle.py
It rewrites the interface in place (colours, square corners, monospace font, no shadows,
F7 instead of logos). Nothing here depends on line numbers, so it survives most upstream
updates. If something it expects is gone, it stops and says what, instead of building a
half-styled app.
"""
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
UI = ROOT / "ui"
ASSETS = HERE / "assets"

FONT_SCALE = 0.9      # monospace is wider than the original typeface; text shrinks a little to keep widths
BRAND = "F7"

# ---------------------------------------------------------------- palettes
# #35363a graphite / #e5e8e2 paper, the same pair as the Windows setup.
DARK = dict(
    rail="#27282b", sidebar="#2e2f33", panel="#2a2b2e", chat="#35363a", stage="#35363a",
    raised="#3e3f44", field="#3d3e43", sunken="#232427", hover="#3b3c41", active="#45464b",
    row_hover="#393a3f", line="#4b4c52", edge="#1f2022",
    outline="#4b4c52", outline_chat="#4b4c52", outline_field="#4b4c52",
    text="#e5e8e2", secondary="#c4c7c1", muted="#a1a49f", faint="#7e8183",
    accent="#e5e8e2", accent_hover="#f4f6f1", on_accent="#35363a", accent_soft="#e5e8e22a",
    danger="#c97272", danger_hover="#d68686", on_danger="#241818",
    live="#8fbf9a", loud="#d1a869", link="#b9cde3",
    button_default="#46474c", button_default_hover="#505157",
    overlay="#ffffff", shimmer="#ffffff14", reply_spine="#5e5f65", tooltip="#202123", avatar="#63646a",
)
PAPER = dict(
    rail="#d1d4ce", sidebar="#dcdfd9", panel="#d6d9d3", chat="#e5e8e2", stage="#e5e8e2",
    raised="#eef0eb", field="#eff1ec", sunken="#cbcec8", hover="#d8dbd5", active="#ccd0c9",
    row_hover="#e0e3dd", line="#b8bbb5", edge="#c2c5bf",
    outline="#b8bbb5", outline_chat="#b8bbb5", outline_field="#b8bbb5",
    text="#35363a", secondary="#505156", muted="#666870", faint="#7d7f84",
    accent="#35363a", accent_hover="#4b4c51", on_accent="#e5e8e2", accent_soft="#35363a1f",
    danger="#a44a4a", danger_hover="#8f3d3d", on_danger="#f1f3ee",
    live="#4c7a56", loud="#96662a", link="#3d5a80",
    button_default="#d0d3cd", button_default_hover="#c5c8c2",
    overlay="#35363a", shimmer="#ffffffa0", reply_spine="#b3b6b0", tooltip="#f1f3ee", avatar="#a3a6a1",
)

report = []


def die(message):
    print(f"F7 restyle: STOP: {message}", file=sys.stderr)
    sys.exit(1)


def note(what, count):
    report.append((what, count))


def read(path):
    return path.read_text(encoding="utf-8")


def write(path, text):
    path.write_text(text, encoding="utf-8", newline="\n")


# ---------------------------------------------------------------- 1. colours
def rust_colour(value):
    h = value.lstrip("#").lower()
    return f"rgb(0x{h})" if len(h) == 6 else f"rgba(0x{h})"


def themes():
    path = ROOT / "src" / "ui" / "theme.rs"
    text = read(path)
    for const, palette, old, new in (("YAP", DARK, "Yap", "F7 Dark"), ("SAKURA", PAPER, "Sakura", "F7 Paper")):
        m = re.search(r"((?:pub )?const %s: Theme = Theme \{\n)(.*?)(\n\};)" % const, text, re.S)
        if not m:
            die(f"theme {const} not found in src/ui/theme.rs")
        body = m.group(2)
        fields = re.findall(r"^\s+([a-z_]+):", body, re.M)
        lines = []
        for name in fields:
            if name == "dark":
                lines.append("    " + re.search(r"^\s+(dark: (?:true|false),)", body, re.M).group(1))
            elif name in palette:
                lines.append(f"    {name}: {rust_colour(palette[name])},")
            else:
                die(f"theme {const} has a colour my palette lacks: {name}")
        missing = set(palette) - set(fields)
        if missing:
            die(f"my palette has colours theme {const} no longer has: {sorted(missing)}")
        text = text[: m.start(2)] + "\n".join(lines) + text[m.end(2):]
        text, n = re.subn(r'name: "%s",' % re.escape(old), f'name: "{new}",', text, count=1)
        if n != 1:
            die(f'built-in theme name "{old}" not found')
    write(path, text)
    note("built-in themes rewritten (Yap -> F7 Dark, Sakura -> F7 Paper)", 2)

    # first frame colours in ui/theme.slint
    path = UI / "theme.slint"
    text = read(path)
    count = 0

    def put(m):
        nonlocal count
        key = m.group(2).replace("-", "_")
        if key not in DARK:
            return m.group(0)
        count += 1
        return f"{m.group(1)}{DARK[key]};"

    text = re.sub(r"(in-out property <color> ([a-z-]+): )#[0-9a-fA-F]{6,8};", put, text)
    if count < len(DARK) - 1:
        die(f"only {count} of {len(DARK)} colours found in ui/theme.slint")
    write(path, text)
    note("ui/theme.slint defaults", count)


# ---------------------------------------------------------------- helpers for Slint text
def mask_text(text):
    """Same length as text, with comments and string contents blanked, so braces can be counted."""
    return re.sub(r'//[^\n]*|/\*.*?\*/|"(?:[^"\\]|\\.)*"', lambda m: "x" * len(m.group(0)), text, flags=re.S)


def element_span(mask, pos):
    depth, i, start = 0, pos, None
    while i > 0:
        i -= 1
        c = mask[i]
        if c == "}":
            depth += 1
        elif c == "{":
            if depth == 0:
                start = i
                break
            depth -= 1
    depth, j, end = 0, pos, None
    while j < len(mask):
        c = mask[j]
        if c == "{":
            depth += 1
        elif c == "}":
            if depth == 0:
                end = j
                break
            depth -= 1
        j += 1
    if start is None or end is None:
        return None
    return start, end


def own_text(mask, start, end):
    """The element's own statements, with its children's blocks cut out."""
    out, depth = [], 0
    for c in mask[start + 1:end]:
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        elif depth == 0:
            out.append(c)
    return "".join(out)


# ---------------------------------------------------------------- 2. square, flat, monospace
RADIUS = re.compile(r"(border(?:-(?:top|bottom)-(?:left|right))?-radius)\s*:\s*[^;]+;")
RADIUS_PROP = re.compile(r"(?<![\w-])radius\s*:\s*\d+(?:\.\d+)?px")
SHADOW = re.compile(r"(?:drop-shadow-(?:blur|color|offset-x|offset-y)\s*:\s*[^;]+;[ \t]*)+")
FONT_SIZE = re.compile(r"(?<![\w-])((?:default-)?font-size\s*:\s*)([^;]+);")
PX = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)px")


def scale_font(m):
    def one(px):
        n = float(px.group(1))
        return px.group(0) if n < 11 else f"{max(10, round(n * FONT_SCALE))}px"

    return m.group(1) + PX.sub(one, m.group(2)) + ";"


def restyle_slint():
    totals = dict(radius=0, shadow_border=0, shadow_gone=0, fonts=0, brand=0)
    for path in sorted(UI.glob("*.slint")):
        if path.name == "theme.slint":
            continue
        text = read(path)

        text, n = RADIUS.subn(r"\1: 0px;", text)
        totals["radius"] += n
        text, n = RADIUS_PROP.subn("radius: 0px", text)
        totals["radius"] += n

        text, n = FONT_SIZE.subn(scale_font, text)
        totals["fonts"] += n

        # shadows: a 1px line where the element can take one, nothing where it cannot
        mask = mask_text(text)
        pieces, last = [], 0
        for m in SHADOW.finditer(mask):
            span = element_span(mask, m.start())
            border_ok = False
            if span:
                head = mask[: span[0]].rstrip()
                kind = re.search(r"([A-Za-z_][\w]*)$", head)
                own = own_text(mask, *span)
                border_ok = bool(kind and kind.group(1) == "Rectangle" and "border-width" not in own and "border-color" not in own)
            pieces.append(text[last:m.start()])
            if border_ok:
                pieces.append("border-width: 1px; border-color: Theme.line; ")
                totals["shadow_border"] += 1
            else:
                totals["shadow_gone"] += 1
            last = m.end()
        pieces.append(text[last:])
        text = "".join(pieces)

        # the product name inside strings the user reads
        lines = []
        for line in text.split("\n"):
            if not line.lstrip().startswith("//"):
                line, n = re.subn(
                    r'"(?:[^"\\]|\\.)*"',
                    lambda m: m.group(0).replace("Yapfast", BRAND),
                    line,
                )
                totals["brand"] += line.count(BRAND)
            lines.append(line)
        text = "\n".join(lines)
        write(path, text)
    note("corners made square", totals["radius"])
    note("font sizes scaled", totals["fonts"])
    note("shadows -> 1px lines", totals["shadow_border"])
    note("shadows removed", totals["shadow_gone"])
    note('product name -> "F7" in strings', totals["brand"])


def fonts():
    folder = UI / "fonts"
    for f in sorted((ASSETS / "fonts").iterdir()):
        shutil.copy2(f, folder / f.name)
    path = UI / "yapfast.slint"
    text = read(path)
    if 'default-font-family: "Atkinson Hyperlegible Next";' not in text:
        die("default-font-family of ui/yapfast.slint changed")
    imports = "".join(
        f'import "fonts/JetBrainsMono-{w}.ttf";\n'
        for w in ("Regular", "Italic", "Medium", "Bold", "BoldItalic", "ExtraBold")
    )
    anchor = 'import "fonts/AtkinsonHyperlegibleNext-ExtraBold.ttf";\n'
    if anchor not in text:
        die("font imports of ui/yapfast.slint changed")
    text = text.replace(anchor, anchor + imports, 1)
    text = text.replace('default-font-family: "Atkinson Hyperlegible Next";', 'default-font-family: "JetBrains Mono";', 1)
    write(path, text)

    # emoji bitmaps are fitted to the UI typeface's vertical metrics
    path = ROOT / "src" / "emoji_font_tables.rs"
    text = read(path)
    for old, new in (
        ("const ASCENDER: i16 = 984;", "const ASCENDER: i16 = 1020;"),
        ("const DESCENDER: i16 = -316;", "const DESCENDER: i16 = -300;"),
        ("bearing_y: 102 + MARGIN as i8,", "bearing_y: 100 + MARGIN as i8,"),
    ):
        if old not in text:
            die(f"emoji metrics changed: {old}")
        text = text.replace(old, new, 1)
    write(path, text)
    note("font: JetBrains Mono + emoji metrics", 1)


# ---------------------------------------------------------------- 3. F7 instead of logos
def logos():
    for src, dst in (
        (ASSETS / "icons" / "logo.svg", UI / "icons" / "logo.svg"),
        (ASSETS / "icons" / "discord.svg", UI / "icons" / "discord.svg"),
        (ASSETS / "icon.svg", ROOT / "packaging" / "icon.svg"),
        (ASSETS / "yapfast.ico", ROOT / "packaging" / "windows" / "yapfast.ico"),
    ):
        if not dst.exists():
            die(f"{dst.relative_to(ROOT)} not found (moved upstream?)")
        shutil.copy2(src, dst)
    # the tray icon is painted in the old accent colours
    path = ROOT / "src" / "tray.rs"
    text = read(path)
    for old, new in (("#ffbf47", DARK["accent"]), ("#f0545e", DARK["danger"])):
        if old not in text:
            die(f"tray colours changed: {old}")
        text = text.replace(old, new)
    write(path, text)
    note("logos, app icon, tray icon", 5)


def main():
    if not (ROOT / "ui" / "yapfast.slint").exists():
        die("run this from a Yapfast checkout that has f7/ in it")
    themes()
    restyle_slint()
    fonts()
    logos()
    print("F7 restyle done:")
    for what, count in report:
        print(f"  {count:5d}  {what}")


if __name__ == "__main__":
    main()
