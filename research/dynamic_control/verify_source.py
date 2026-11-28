"""Verify the historical archive and working source against the public commit."""
import argparse
from gzip import decompress
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
import subprocess
import sys

PIN = "6d875a65251fb62f691dc0386ea81aeb29d27c0f"
ROLLING = Path("analysis/results/legacy-rolling-recovery-v1")
RUNTIME = Path("analysis/results/legacy-season-technical-replay-v1")


def digest(data):
    return sha256(data).hexdigest()


def verify(source, pinned):
    def read(path):
        data = (source / path).read_bytes()
        expected = subprocess.check_output(
            ["git", "-C", str(pinned), "show", f"{PIN}:{path.as_posix()}"]
        )
        if data != expected:
            raise ValueError(f"Public source mismatch: {path}")
        return data

    rolling = json.loads(read(ROLLING / "manifest.json"))
    forecast = next(entry for entry in rolling["outputs"] if entry["name"] == "player_gw_forecasts")
    runtime = json.loads(read(RUNTIME / "runtime_input_manifest.json"))
    used = [entry for entry in runtime if Path(entry["runtime_path"]).name in {"merged_gw.csv", "players_raw.csv"}]
    archives = [(ROLLING, forecast, forecast["uncompressed_sha256"])]
    archives.extend((RUNTIME, entry, entry["sha256"]) for entry in used)
    hashes = {}
    for folder, entry, expected in archives:
        parts = []
        for part in entry["parts"]:
            path = folder / part["path"]
            data = (source / path).read_bytes()
            if digest(data) != part["sha256"]:
                raise ValueError(f"Archive part mismatch: {path}")
            parts.append(data)
        packed = b"".join(parts)
        compressed = entry.get("compressed_sha256")
        if (compressed is not None and digest(packed) != compressed) or digest(decompress(packed)) != expected:
            raise ValueError(f"Archive digest mismatch: {entry}")
        key = entry.get("name") or Path(entry["runtime_path"]).name
        hashes[key] = expected
    paths = list((source / "src/fpl_xpts").glob("*.py"))
    paths += [source / "scripts" / name for name in (
        "run_transfer_strategy_v3_replay.py", "run_horizon_policy_comparison.py",
        "run_transfer_strategy_v2_grid.py", "run_v4rc_experiment.py",
        "build_reproducible_role_benchmark.py", "benchmark_squad_minutes.py")]
    # Confirm every used module plus its sibling package modules against the pin.
    checked = {path.relative_to(source).as_posix(): digest(read(path.relative_to(source)))
               for path in sorted(paths)}
    return dict(public_commit=PIN, python=sys.version.split()[0],
                libraries={name: version(name) for name in ("pandas", "numpy", "scipy", "scikit-learn", "matplotlib")},
                archive_sha256=hashes, source_sha256=checked)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--pinned", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.source.resolve(), (args.pinned or args.source).resolve()), indent=2))
