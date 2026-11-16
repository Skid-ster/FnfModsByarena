#!/usr/bin/env python3
"""
Packages the mod the way Codename Engine expects zip mods to look:

    dist/TrollgeMod.zip
        data/  images/  music/  shaders/  songs/  sounds/  mod.json
    dist/SuperScaryTrollge-v<version>.zip
        (the same bytes, under the name a human wants to download)

Drop the zip -- or the extracted folder -- straight into `mods/`.

Why two names
-------------
Codename names a mod after the *file* it loads, not after `mod.json`:
`MainState` calls `loadLib(path, ModsFolder.currentModFolder)`, that libName is
lowercased into `ModsFolderLibrary.modName`, and freeplay then looks up
`config/freeplaySonglist/LIB_<modName>` (FreeplayState.hx, getSongsFromSource).
So `TrollgeMod.zip` is the installable artifact: it makes `modName` ==
`TrollgeMod`, which is the only way `LIB_TrollgeMod.txt` is ever read. A
`SuperScaryTrollge-v3.6.0.zip` names the mod `superscarytrollge-v3.6.0`, which
loses the freeplay list *and* makes `ModsFolder.init()` drop the saved mod on
the next launch (it compares the saved name against `getModsList()`), so the
player has to re-pick the mod every time.

The versioned copy is kept because a release asset should say what it is.

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
INCLUDE = ["data", "images", "music", "shaders", "songs", "sounds", "mod.json"]

#: Top-level entries that stay out of the archive on purpose.
EXCLUDE = {"README.md", "LICENSE", "preview.png"}

#: The name the engine must see. See the module docstring: this is not cosmetic.
INSTALL_NAME = "TrollgeMod"


def main():
    meta = json.load(open(os.path.join(MOD, "mod.json"), encoding="utf-8"))
    version = meta["version"]
    os.makedirs(DIST, exist_ok=True)
    target = os.path.join(DIST, "SuperScaryTrollge-v%s.zip" % version)
    install = os.path.join(DIST, INSTALL_NAME + ".zip")

    count = 0
    with zipfile.ZipFile(install, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
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

    # The release asset is the same archive under a human name. Copy rather than
    # re-zip so the two can never disagree about their contents.
    with open(install, "rb") as src_fh, open(target, "wb") as dst_fh:
        while True:
            chunk = src_fh.read(1024 * 1024)
            if not chunk:
                break
            dst_fh.write(chunk)

    size = os.path.getsize(target) / (1024 * 1024)
    print("Packaged %d files -> %s (%.1f MB)" % (count, os.path.relpath(target, ROOT), size))
    print("Install with %s -- the engine names a mod after this file, and"
          % os.path.relpath(install, ROOT))
    print("freeplay asks for config/freeplaySonglist/LIB_%s.txt, which the engine"
          % INSTALL_NAME)
    print("rewrites to config/freeplaySonglist.txt; both ship, so either build works.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
