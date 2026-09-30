#!/usr/bin/env python3
"""Upload Sandy's videos to Mux with SIGNED playback and record the playback ids.

Run on the Mac from the backend repo:

    cd ~/dev/movewithoutpain-backend
    export MUX_TOKEN_ID=...  MUX_TOKEN_SECRET=...     # Mux → Settings → Access Tokens
    python3 tools/mux_upload.py                       # default: ~/Downloads/Felix Videos

It writes mux_playback_ids.json in the repo root ({exercise name_en: playback id}),
which premium_exercises.py reads. Commit that file and push to deploy.

- Standard library + curl only (curl sidesteps macOS python certificate problems).
- Idempotent: exercises already in mux_playback_ids.json are skipped, so a failed
  run can simply be re-run.
- Refuses any asset whose playback policy is not "signed". A public playback id
  would make a premium video watchable by anyone who has the id, forever.
- The token is passed to curl on stdin, never on the command line.

Asset IDs (useful for deleting/replacing in the Mux dashboard) are kept in
mux_assets.json next to the videos, not in the repo.
"""

from __future__ import annotations  # the Mac's system python3 is 3.9

import json
import os
import subprocess
import sys
import time

API = "https://api.mux.com"

# exercise name_en -> file, relative to the videos folder. The joined L+R clips
# were made with `ffmpeg -f concat -c copy` into mux-ready/.
MANIFEST = {
    "Wall Figure Four": "pared1.mp4",
    "Legs Up the Wall Hamstring Stretch": "mux-ready/wall-2_legs-up-wall_L+R.mp4",
    "Wall Leg Extensions": "pared4.mp4",
    "Wall Butterfly": "Pared5.mp4",
    "Psoas Lunge Pulses": "Psoas.mp4",
    "4-Minute Posterior Chain": "4min CadenaPosterior.mp4",
    # New footage for two exercises that are already free (they stay free):
    "Lying Leg Raise (Battement)": "mux-ready/lying-battement_R+L.mp4",
    "Glute Kick": "mux-ready/glute-kick_R+L.mp4",
}

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IDS_FILE = os.path.join(REPO, "mux_playback_ids.json")


def die(msg: str) -> None:
    print(f"✖ {msg}", file=sys.stderr)
    sys.exit(1)


def curl(args: list, auth: bool = True) -> str:
    cfg = ""
    if auth:
        cfg = f'user = "{os.environ["MUX_TOKEN_ID"]}:{os.environ["MUX_TOKEN_SECRET"]}"\n'
    res = subprocess.run(
        ["curl", "-sS", "--fail-with-body", "-K", "-"] + args,
        input=cfg, capture_output=True, text=True,
    )
    if res.returncode != 0:
        die(f"curl failed ({res.returncode}): {res.stderr.strip()} {res.stdout.strip()[:500]}")
    return res.stdout


def api(method: str, path: str, body: dict | None = None) -> dict:
    args = ["-X", method, f"{API}{path}", "-H", "Content-Type: application/json"]
    if body is not None:
        args += ["--data", json.dumps(body)]
    return json.loads(curl(args))["data"]


def load(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return {}


def save(path: str, data: dict) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False, sort_keys=True)
        fh.write("\n")
    os.replace(tmp, path)


def main() -> None:
    if not (os.environ.get("MUX_TOKEN_ID") and os.environ.get("MUX_TOKEN_SECRET")):
        die("Set MUX_TOKEN_ID and MUX_TOKEN_SECRET first (Mux → Settings → Access Tokens).")
    videos = os.path.expanduser(sys.argv[1] if len(sys.argv) > 1 else "~/Downloads/Felix Videos")
    missing = [f for f in MANIFEST.values() if not os.path.isfile(os.path.join(videos, f))]
    if missing:
        die(f"Missing in {videos}: {missing}")

    ids = load(IDS_FILE)
    assets_file = os.path.join(videos, "mux_assets.json")
    assets = load(assets_file)

    for name, rel in MANIFEST.items():
        if ids.get(name):
            print(f"· {name}: already uploaded ({ids[name]})")
            continue
        path = os.path.join(videos, rel)
        size_mb = os.path.getsize(path) / 1e6
        print(f"↑ {name}  ←  {rel}  ({size_mb:.0f} MB)")

        upload = api("POST", "/video/v1/uploads", {
            "cors_origin": "*",
            "new_asset_settings": {
                "playback_policy": ["signed"],
                "video_quality": "basic",
                "passthrough": name,
            },
        })
        curl(["-X", "PUT", "-T", path, "--progress-bar", "-o", "/dev/null", upload["url"]], auth=False)

        asset_id = None
        for _ in range(120):
            up = api("GET", f"/video/v1/uploads/{upload['id']}")
            if up.get("status") == "errored":
                die(f"Upload errored for {name}: {up.get('error')}")
            asset_id = up.get("asset_id")
            if asset_id:
                break
            time.sleep(5)
        if not asset_id:
            die(f"Timed out waiting for the asset for {name}")

        for _ in range(240):
            asset = api("GET", f"/video/v1/assets/{asset_id}")
            if asset["status"] == "ready":
                break
            if asset["status"] == "errored":
                die(f"Mux could not process {name}: {asset.get('errors')}")
            time.sleep(5)
        else:
            die(f"Timed out waiting for {name} to finish processing")

        playback = asset.get("playback_ids") or []
        public = [p["id"] for p in playback if p.get("policy") != "signed"]
        signed = [p["id"] for p in playback if p.get("policy") == "signed"]
        if public:
            die(f"{name} has a NON-signed playback id {public}. Delete it in the Mux dashboard (asset {asset_id}).")
        if not signed:
            die(f"{name} has no signed playback id (asset {asset_id}).")

        ids[name] = signed[0]
        assets[name] = {"asset_id": asset_id, "file": rel, "duration": asset.get("duration")}
        save(IDS_FILE, ids)          # after every video, so a crash loses nothing
        save(assets_file, assets)
        print(f"  ✓ ready — signed playback id {signed[0]}  ({asset.get('duration', 0):.0f}s)")

    print(f"\nDone. {len(ids)} ids in {os.path.relpath(IDS_FILE)}.")
    print("Next: git add mux_playback_ids.json && git commit -m 'Add Mux playback ids' && git push")


if __name__ == "__main__":
    main()
