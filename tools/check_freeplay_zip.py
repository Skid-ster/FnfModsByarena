#!/usr/bin/env python3
"""Exercise two Freeplay list paths and the ZipFolderLibrary-style rewrite.

This models lookup and scan of one mod archive. It is not Codename Engine and
cannot establish what modName or enabled mods a particular engine build uses.
"""
import argparse
import posixpath
import zipfile
from pathlib import Path

import song_layout as layout

EXPECTED = [song['id'] for song in layout.SONGS]


def resolve(path, mod_name, rewrite):
    # ZipFolderLibrary.__parseAsset removes assets/ before interpreting LIB_.
    if not path.startswith('assets/'):
        return None
    path = path[len('assets/'):]
    directory, name = posixpath.split(path)
    stem, ext = posixpath.splitext(name)
    if rewrite and stem.startswith('LIB_'):
        if stem[4:] != mod_name:
            return None
        path = directory + ext
    return path.lower()


def simulate(zip_path, generation, mod_name, rewrite):
    with zipfile.ZipFile(zip_path) as z:
        entries = {name.lower(): name for name in z.namelist() if not name.endswith('/')}
        paths = ['config/freeplaySonglist', 'freeplaySonglist'] if generation == 'new' else ['freeplaySonglist']
        for path in paths:
            asset = f'assets/data/{path}/LIB_{mod_name}.txt'
            key = resolve(asset, mod_name, rewrite)
            if key in entries:
                data = z.read(entries[key]).decode('utf-8')
                songs = [line.strip() for line in data.splitlines()
                         if line.strip() and not line.strip().startswith('#')]
                return songs, entries[key]
        # getFolders('assets/songs/') is derived from zip entries, not explicit
        # directory members. Verify metadata rather than inventing song folders.
        prefix = 'songs/'
        folders = {name[len(prefix):].split('/')[0] for name in entries
                   if name.startswith(prefix) and '/' in name[len(prefix):]}
        for song in folders:
            if f'songs/{song}/meta.json' not in entries:
                raise AssertionError(f'scanned folder {song!r} has no meta.json')
        return sorted(folders), 'songs/ scan (order not guaranteed by engine)'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('zip', nargs='?', default='dist/TrollgeMod.zip')
    args = parser.parse_args()
    zip_path = Path(args.zip)
    for generation in ('old', 'new'):
        for rewrite in (False, True):
            songs, via = simulate(zip_path, generation, 'TrollgeMod', rewrite)
            if songs != EXPECTED:
                raise AssertionError((generation, rewrite, via, songs))
            print(f'{generation:3} rewrite={str(rewrite):5}: {via} -> {songs}')
        # A path-like modName creates subdirectories in the requested path;
        # test the scan fallback separately from a renamed single-component name.
        songs, via = simulate(zip_path, generation, './mods/trollge', True)
        if set(songs) != set(EXPECTED) or via.startswith('data/'):
            raise AssertionError((generation, via, songs))
        print(f'{generation:3} path-like modName: {via} -> {songs}')
        songs, via = simulate(zip_path, generation, 'renamed', True)
        if songs != EXPECTED or not via.startswith('data/'):
            raise AssertionError((generation, via, songs))
        print(f'{generation:3} renamed modName: {via} -> {songs}')
    print('Archive model passed; test actual freeplay on each target engine build.')


if __name__ == '__main__':
    main()
