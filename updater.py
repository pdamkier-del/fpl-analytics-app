from __future__ import annotations

from pathlib import Path
from urllib.request import Request, urlopen
import gzip
import hashlib
import io
import json
import os
import shutil
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parent
MANIFEST_URL = "https://raw.githubusercontent.com/pdamkier-del/fpl-analytics-app/main/updates/manifest.json"
USER_AGENT = "FPLAnalyticsDesktop/1.6"


def read_text(path: Path, default: str = "") -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except Exception:
        return default


def fetch_bytes(url: str, timeout: float = 8.0) -> bytes:
    req = Request(url, headers={"User-Agent": USER_AGENT, "Cache-Control": "no-cache"})
    with urlopen(req, timeout=timeout) as response:
        return response.read()


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def verify(raw: bytes, expected: str, label: str) -> None:
    actual = sha256(raw)
    if expected and actual.lower() != expected.lower():
        raise RuntimeError(f"{label} checksum mismatch")


def version_key(value: str) -> tuple[int, ...]:
    clean = value.strip().lower().lstrip("v")
    parts = []
    for bit in clean.split("."):
        digits = "".join(ch for ch in bit if ch.isdigit())
        parts.append(int(digits or 0))
    return tuple(parts)


def safe_extract_zip(raw: bytes) -> None:
    # App bundles deliberately contain only replaceable program files.
    forbidden = (
        "user/",
        "runtime/",
        "model/versions/",
        "model/runs/",
        "model/active.json",
        "updater.py",
        "Start FPL App.bat",
        "Install FPL Website.bat",
    )
    with tempfile.TemporaryDirectory(prefix="fpl-update-") as td:
        stage = Path(td)
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            for info in zf.infolist():
                name = info.filename.replace("\\", "/").lstrip("/")
                if not name or name.endswith("/"):
                    continue
                if ".." in Path(name).parts:
                    raise RuntimeError("Unsafe path in app update")
                if name == "updater.py" or any(name.startswith(x) for x in forbidden):
                    raise RuntimeError(f"Protected path in app update: {name}")
                target = (stage / name).resolve()
                if stage.resolve() not in target.parents:
                    raise RuntimeError("Unsafe app update path")
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info) as src, target.open("wb") as dst:
                    shutil.copyfileobj(src, dst)

        # Copy staged files over the installation only after the whole archive validates.
        for src in stage.rglob("*"):
            if not src.is_file():
                continue
            rel = src.relative_to(stage)
            dest = ROOT / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            tmp = dest.with_name(dest.name + ".update_tmp")
            shutil.copy2(src, tmp)
            os.replace(tmp, dest)


def install_data(raw_gz: bytes, expected_uncompressed_sha: str = "") -> None:
    raw = gzip.decompress(raw_gz)
    if expected_uncompressed_sha:
        verify(raw, expected_uncompressed_sha, "data payload")
    # Validate JSON before replacing the current data.
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict) or "meta" not in payload or "forecasts" not in payload:
        raise RuntimeError("Remote data payload does not look like FPL data")

    base_path = ROOT / "model" / "base_data.json"
    js_path = ROOT / "app" / "data.js"
    base_path.parent.mkdir(parents=True, exist_ok=True)
    js_path.parent.mkdir(parents=True, exist_ok=True)

    base_tmp = base_path.with_name(base_path.name + ".update_tmp")
    js_tmp = js_path.with_name(js_path.name + ".update_tmp")
    base_tmp.write_bytes(raw)
    js_tmp.write_text("window.FPL_DATA=" + raw.decode("utf-8") + ";\n", encoding="utf-8")
    os.replace(base_tmp, base_path)
    os.replace(js_tmp, js_path)


def main() -> int:
    local_app = read_text(ROOT / "VERSION.txt", "0")
    local_data = read_text(ROOT / "DATA_VERSION.txt", "")
    print(f"Checking FPL Analytics updates (app {local_app}, data {local_data or 'unknown'})...")

    try:
        manifest_raw = fetch_bytes(MANIFEST_URL)
        manifest = json.loads(manifest_raw.decode("utf-8"))
    except Exception as exc:
        print(f"Update check skipped: {exc}")
        return 0

    try:
        remote_app = str(manifest.get("app_version", local_app))
        app_info = manifest.get("app", {}) or {}
        if version_key(remote_app) > version_key(local_app):
            print(f"Updating app {local_app} -> {remote_app}...")
            raw = fetch_bytes(str(app_info["url"]), timeout=20.0)
            verify(raw, str(app_info.get("sha256", "")), "app bundle")
            safe_extract_zip(raw)
            (ROOT / "VERSION.txt").write_text(remote_app + "\n", encoding="utf-8")
            print("App update installed.")
        else:
            print("App is current.")

        remote_data = str(manifest.get("data_version", local_data))
        data_info = manifest.get("data", {}) or {}
        if remote_data and remote_data != local_data:
            print(f"Updating FPL data -> {remote_data}...")
            raw_gz = fetch_bytes(str(data_info["url"]), timeout=25.0)
            verify(raw_gz, str(data_info.get("sha256", "")), "compressed data")
            install_data(raw_gz, str(data_info.get("uncompressed_sha256", "")))
            (ROOT / "DATA_VERSION.txt").write_text(remote_data + "\n", encoding="utf-8")
            print("FPL data update installed.")
        else:
            print("FPL data is current.")

        state = {
            "ok": True,
            "app_version": read_text(ROOT / "VERSION.txt", local_app),
            "data_version": read_text(ROOT / "DATA_VERSION.txt", local_data),
            "published_utc": manifest.get("published_utc"),
            "message": manifest.get("message", ""),
        }
        (ROOT / "user").mkdir(exist_ok=True)
        (ROOT / "user" / "update_status.json").write_text(
            json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception as exc:
        print(f"Update failed; opening the existing app instead: {exc}")
        try:
            (ROOT / "user").mkdir(exist_ok=True)
            (ROOT / "user" / "update_status.json").write_text(
                json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
