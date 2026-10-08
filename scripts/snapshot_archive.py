"""Preserve the previous snapshot bytes before any same-day rerun replaces it."""
import hashlib
import json


def write_snapshot(path, payload):
    content=json.dumps(payload,ensure_ascii=False,indent=2).encode('utf-8')
    if path.exists():
        previous=path.read_bytes()
        if previous==content:return
        revision=path.parent/'revisions'/f'{path.stem}-{hashlib.sha256(previous).hexdigest()}.json'
        revision.parent.mkdir(parents=True,exist_ok=True)
        if not revision.exists():
            with revision.open('xb') as f:f.write(previous)
    path.write_bytes(content)
