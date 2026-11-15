#!/usr/bin/env python3
"""
Packages the mod the way Codename Engine expects zip mods to look:

    SuperScaryTrollge-v<version>.zip
        data/  images/  songs/  sounds/  mod.json

(drag the zip -- or the extracted folder -- straight into `mods/`).

Usage:  python3 tools/package_mod.py
"""

import json
import os
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOD = os.path.join(ROOT, "mods", "TrollgeMod")
DIST = os.path.join(ROOT, "dist")

#: Folders that belong in the shipped archive.
INCLUDE = ["data", "images", "songs", "sounds", "mod.json"]


def main():
    meta = json.load(open(os.path.join(MOD, "mod.json"), encoding="utf-8"))
    version = meta["version"]
    os.makedirs(DIST, exist_ok=True)
    target = os.path.join(DIST, "SuperScaryTrollge-v%s.zip" % version)

    count = 0
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for entry in INCLUDE:
            full = os.path.join(MOD, entry)
            if os.path.isfile(full):
                zf.write(full, entry)
                count += 1
                continue
            for base, _dirs, files in os.walk(full):
                for f in sorted(files):
                    if f.endswith((".pyc",)) or f.startswith("."):
                        continue
                    path = os.path.join(base, f)
                    zf.write(path, os.path.relpath(path, MOD))
                    count += 1

    size = os.path.getsize(target) / (1024 * 1024)
    print("Packaged %d files -> %s (%.1f MB)" % (count, os.path.relpath(target, ROOT), size))
    return 0


if __name__ == "__main__":
    sys.exit(main())
