"""Sample the procedural activity clips into ``web/avatar_demo/clips.json``.

Usage: python3 tools/export_clips.py
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine.animation import activities as A  # noqa: E402

FPS = 30


def main():
    out = {'fps': FPS, 'bones': A.BONES, 'clips': {}}
    for name, (_, dur, travel, props, label) in A.CLIPS.items():
        frames = []
        for rot, off in A.sample(name, FPS):
            flat = [round(v, 1) for b in A.BONES for v in rot[b]]
            frames.append(flat + [round(v, 3) for v in off])
        out['clips'][name] = dict(label=label, duration=dur, travel=travel, props=props, frames=frames)
    path = os.path.join(ROOT, 'web', 'avatar_demo', 'clips.json')
    with open(path, 'w') as f:
        json.dump(out, f, separators=(',', ':'))
    print('wrote', path, os.path.getsize(path) // 1024, 'KB')


if __name__ == '__main__':
    main()
