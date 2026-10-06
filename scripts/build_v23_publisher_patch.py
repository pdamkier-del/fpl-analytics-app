#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,zipfile,gzip
from pathlib import Path
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parents[1]
VERSION="2.3"
PATCH=ROOT/f"FPL_Analytics_v{VERSION}_repo_patch.zip"
STAGE=ROOT/"build"/"publisher-v2.3"
if STAGE.exists():
    import shutil;shutil.rmtree(STAGE)
(STAGE/"app").mkdir(parents=True)
(STAGE/"updates").mkdir(parents=True)
(STAGE/".github"/"workflows").mkdir(parents=True)
(STAGE/"scripts").mkdir(parents=True)

# Files that the repository publisher should overlay onto main.
copy=[
 ("app/index.html","app/index.html"),
 ("app/models.html","app/models.html"),
 ("app/nav.js","app/nav.js"),
 ("scripts/publish_fpl_update.py","scripts/publish_fpl_update.py"),
 (".github/workflows/publish-fpl-update.yml",".github/workflows/publish-fpl-update.yml"),
]
for src,dst in copy:
    p=ROOT/src
    q=STAGE/dst;q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(p.read_bytes())

# Build the app update consumed by updater.py after the repo patch lands on main.
appzip=STAGE/"updates"/f"app-{VERSION}.zip"
with zipfile.ZipFile(appzip,"w",zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for src in ("app/index.html","app/models.html","app/nav.js"):
        z.write(ROOT/src,src)

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
old_manifest=json.loads((ROOT/"updates"/"manifest.json").read_text(encoding="utf-8"))
manifest={
 "app_version":VERSION,
 "data_version":old_manifest.get("data_version",""),
 "published_utc":datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),
 "message":"Website v2.3: Expected XI, Model Explorer and automatic Publish FPL Update flow",
 "app":{
   "url":f"https://raw.githubusercontent.com/pdamkier-del/fpl-analytics-app/main/updates/app-{VERSION}.zip",
   "sha256":sha(appzip),
 },
 "data":old_manifest.get("data",{}),
}
(STAGE/"updates"/"manifest.json").write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
(STAGE/"VERSION.txt").write_text(VERSION+"\n",encoding="utf-8")
if (ROOT/"DATA_VERSION.txt").exists():
    (STAGE/"DATA_VERSION.txt").write_bytes((ROOT/"DATA_VERSION.txt").read_bytes())

with zipfile.ZipFile(PATCH,"w",zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for p in sorted(STAGE.rglob("*")):
        if p.is_file():z.write(p,p.relative_to(STAGE).as_posix())
print(PATCH)
print(sha(PATCH))
