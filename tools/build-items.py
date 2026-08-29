"""Regenerate items.js + icons.png for the item picker.

Run Factorio once to dump its prototypes, with the mod set you want the picker to cover:

    Factorio.exe --dump-data --mod-directory "<your mods folder>"

That writes script-output/data-raw-dump.json under Factorio's write-data path. Point DUMP at it,
DATA at the Factorio data folder, MODS at the same mod folder, then:

    pip install pillow
    python tools/build-items.py

Everything below is read from the game: stack sizes and icon paths from the dump, English names
from the locale .cfg files in the base game and every mod, icons composited layer by layer out of
the mod zips. Nothing here is transcribed by hand.
"""
import json, os, re, sys, zipfile, io
from PIL import Image

DUMP = r"C:\Users\Boris\Downloads\Factorio\SE\benchmarks\runtime\script-output\data-raw-dump.json"
DATA = r"D:\SteamLibrary\steamapps\common\Factorio\data"
MODS = r"C:\Users\Boris\AppData\Roaming\Factorio\mods SE"
OUT  = r"C:\Users\Boris\Downloads\se-rocket-logistics-calculators"

CELL = 32          # rendered icon size in the sheet
COLS = 32

ITEM_TYPES = ["item","ammo","capsule","gun","module","tool","armor","repair-tool",
              "mining-tool","item-with-entity-data","rail-planner"]

# ---------------------------------------------------------------- sources
class Sources:
    """Resolves __mod__/path/to.png against the base data dirs and the mod zips."""
    def __init__(self):
        self.dirs, self.zips = {}, {}
        for d in os.listdir(DATA):
            p = os.path.join(DATA, d)
            if os.path.isdir(p):
                self.dirs[d] = p
        for f in os.listdir(MODS):
            full = os.path.join(MODS, f)
            if f.endswith(".zip"):
                name = f[:-4].rsplit("_", 1)[0]
                self.zips[name] = full
            elif os.path.isdir(full):
                self.dirs.setdefault(f.rsplit("_", 1)[0], full)
        self._open = {}
        self._index = {}

    def read(self, path):
        m = re.match(r"__([^_].*?)__/(.*)", path)
        if not m:
            return None
        mod, rel = m.group(1), m.group(2)
        if mod in self.dirs:
            p = os.path.join(self.dirs[mod], rel.replace("/", os.sep))
            return open(p, "rb").read() if os.path.exists(p) else None
        if mod in self.zips:
            z = self._open.get(mod) or self._open.setdefault(mod, zipfile.ZipFile(self.zips[mod]))
            # The folder inside a mod zip is not reliably "<name>_<version>" - aai-containers
            # ships plain "aai-containers/" - so index by the path below the first slash instead
            # of guessing the root.
            idx = self._index.get(mod)
            if idx is None:
                idx = self._index[mod] = {}
                for n in z.namelist():
                    if "/" in n:
                        idx.setdefault(n.split("/", 1)[1], n)
            hit = idx.get(rel)
            if hit:
                return z.read(hit)
        return None

    def listdir_cfgs(self):
        """Every locale/en/*.cfg, base first and mods after.

        Order is load-bearing: a mod renaming a base item must win. AAI Industry turns
        electric-engine-unit into "Big electric motor" and engine-unit into "Multi-cylinder
        engine", and the caller has to overwrite rather than setdefault for that to take.
        """
        for mod, d in self.dirs.items():
            loc = os.path.join(d, "locale", "en")
            if os.path.isdir(loc):
                for f in sorted(os.listdir(loc)):
                    if f.endswith(".cfg"):
                        yield open(os.path.join(loc, f), encoding="utf-8", errors="replace").read()
        for mod, zp in self.zips.items():
            z = self._open.get(mod) or self._open.setdefault(mod, zipfile.ZipFile(zp))
            for n in z.namelist():
                if "/locale/en/" in n and n.endswith(".cfg"):
                    yield z.read(n).decode("utf-8", "replace")

src = Sources()

# ---------------------------------------------------------------- locale
loc = {}
for text in src.listdir_cfgs():
    section = ""
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith(";"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
        elif "=" in line and section:
            k, v = line.split("=", 1)
            # Last writer wins, because listdir_cfgs yields base before mods. setdefault had it
            # backwards and made the base game unoverridable, so every item a mod renamed kept
            # its vanilla name in the picker.
            loc[section + "." + k.strip()] = v.strip()
print("locale keys:", len(loc))

CTRL = re.compile(r"__[A-Z_]+__|\[[^\]]*\]")
UNLOCALISED = []
def pretty(internal, proto):
    for key in ("item-name." + internal, "entity-name." + internal,
                "equipment-name." + internal, "fluid-name." + internal):
        if key in loc:
            return CTRL.sub("", loc[key]).strip()
    pr = proto.get("place_result") or proto.get("placed_as_equipment_result")
    if pr:
        for key in ("entity-name." + pr, "equipment-name." + pr):
            if key in loc:
                return CTRL.sub("", loc[key]).strip()
    # barrels are named by a locale template, "__1__ barrel" over the fluid's own name
    if internal.endswith("-barrel"):
        fluid = "fluid-name." + internal[:-7]
        if fluid in loc:
            return CTRL.sub("", loc[fluid]).strip() + " barrel"
    # se-core-fragment-<resource> is templated the same way, over the resource's name
    if internal.startswith("se-core-fragment-"):
        res = internal[len("se-core-fragment-"):]
        for key in ("item-name." + res, "entity-name." + res, "fluid-name." + res,
                    "item-name.se-" + res, "entity-name.se-" + res):
            if key in loc:
                return CTRL.sub("", loc[key]).strip() + " core fragment"
    UNLOCALISED.append(internal)
    return internal.replace("-", " ").replace("se ", "").strip().capitalize()

# ---------------------------------------------------------------- icons
def layers_of(p):
    if p.get("icons"):
        return p["icons"], p.get("icon_size")
    return [{"icon": p["icon"], "icon_size": p.get("icon_size")}], p.get("icon_size")

def as_rgba(blob):
    return Image.open(io.BytesIO(blob)).convert("RGBA")

def render(proto):
    """Composite one item's icon layers onto a CELL x CELL RGBA tile."""
    tile = Image.new("RGBA", (CELL, CELL), (0, 0, 0, 0))
    lay, parent_size = layers_of(proto)
    drew = False
    for l in lay:
        path = l.get("icon")
        if not path:
            continue
        blob = src.read(path)
        if blob is None:
            continue
        size = l.get("icon_size") or parent_size or 64
        img = as_rgba(blob)
        # icon files often carry a mipmap chain to the right; the full-res icon is the first square
        if img.width > size or img.height > size:
            img = img.crop((0, 0, min(size, img.width), min(size, img.height)))
        scale = l.get("scale", 32.0 / size)          # game default renders a 64px icon at 32px
        px = max(1, int(round(size * scale * CELL / 32.0)))
        img = img.resize((px, px), Image.LANCZOS)
        tint = l.get("tint")
        if tint:
            def ch(v):
                v = float(v)
                return v / 255.0 if v > 1.0 else v
            # a Color is either {r,g,b,a} or a positional [r,g,b,a]
            if isinstance(tint, dict):
                vals = [tint.get(k, 1) for k in ("r", "g", "b", "a")]
            else:
                vals = list(tint) + [1] * (4 - len(tint))
            r, g, b, a = (ch(v) for v in vals[:4])
            R, G, B, A = img.split()
            img = Image.merge("RGBA", (
                R.point(lambda v: int(v * r)), G.point(lambda v: int(v * g)),
                B.point(lambda v: int(v * b)), A.point(lambda v: int(v * a))))
        shift = l.get("shift") or [0, 0]
        if isinstance(shift, dict):
            shift = [shift.get("x", 0), shift.get("y", 0)]
        ox = int(round((CELL - px) / 2 + float(shift[0]) * CELL / 32.0))
        oy = int(round((CELL - px) / 2 + float(shift[1]) * CELL / 32.0))
        tile.alpha_composite(img, (max(0, ox), max(0, oy)))
        drew = True
    return tile if drew else None

# ---------------------------------------------------------------- build
raw = json.load(open(DUMP, encoding="utf-8"))
records, tiles, missing = [], [], []
for t in ITEM_TYPES:
    for name, p in sorted(raw.get(t, {}).items()):
        if p.get("hidden") or p.get("hidden_in_factoriopedia"):
            continue
        if "icon" not in p and "icons" not in p:
            continue
        if name.startswith("parameter-"):        # blueprint parameter dummies, not real cargo
            continue
        tile = render(p)
        if tile is None:
            missing.append(name)
            continue
        records.append({"n": name, "l": pretty(name, p), "s": p.get("stack_size") or 1,
                        "i": len(tiles), "g": p.get("subgroup", ""), "o": p.get("order", "")})
        tiles.append(tile)

records.sort(key=lambda r: (r["g"], r["o"], r["l"]))
remap = {}
sheet_rows = (len(tiles) + COLS - 1) // COLS
sheet = Image.new("RGBA", (COLS * CELL, sheet_rows * CELL), (0, 0, 0, 0))
for new_i, r in enumerate(records):
    sheet.paste(tiles[r["i"]], ((new_i % COLS) * CELL, (new_i // COLS) * CELL))
    r["i"] = new_i

sheet.save(os.path.join(OUT, "icons.png"), optimize=True)

payload = [[r["n"], r["l"], r["s"], r["i"]] for r in records]
js = ("// Generated from Factorio --dump-data with the SE mod set. Do not edit by hand.\n"
      "// [internal name, English name, stack size, sprite index]\n"
      "window.ITEMS=" + json.dumps(payload, separators=(",", ":"), ensure_ascii=False) + ";\n"
      "window.ITEM_SHEET={cell:%d,cols:%d};\n" % (CELL, COLS))
open(os.path.join(OUT, "items.js"), "w", encoding="utf-8").write(js)

print("items:", len(records), " sheet:", sheet.size,
      " icons.png:", os.path.getsize(os.path.join(OUT, "icons.png")) // 1024, "KB",
      " items.js:", os.path.getsize(os.path.join(OUT, "items.js")) // 1024, "KB")
if missing:
    print("no icon rendered for", len(missing), "items:", missing[:10])
print("names from locale:", len(records) - len(UNLOCALISED), "/", len(records),
      ("- fell back for: " + ", ".join(UNLOCALISED)) if UNLOCALISED else "")
for r in records[:8]:
    print("   %-34s %-30s stack %s" % (r["n"], r["l"], r["s"]))
