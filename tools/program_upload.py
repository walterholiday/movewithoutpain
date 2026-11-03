#!/usr/bin/env python3
"""Upload Felix's program videos (Morning Routine, Week 1) to Mux, PUBLIC playback.

    cd ~/dev/movewithoutpain-backend
    export MUX_TOKEN_ID=...  MUX_TOKEN_SECRET=...
    python3 tools/program_upload.py ~/Downloads/"Felix Week 1"

Writes program_playback_ids.json in the repo root ({key: public playback id}),
which programs.py reads. Commit that file and push to deploy.

Week 1 is free, so like the intro clips it uses public playback ids: the app
streams https://stream.mux.com/{id}.m3u8 with no signing round-trip. (Premium
weeks, later, will go through signed playback like the exercise videos.)

The ambient track is optional: put Felix's audio file in the same folder under
one of the AMBIENT names and run again. Audio-only files become audio-only
assets on Mux; the app mixes them under the videos with an on/off toggle.

Idempotent: keys already in program_playback_ids.json are skipped.
"""

from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from intro_upload import api, curl, die, load, save  # noqa: E402  (shared Mux helpers)

# key -> file name in the folder given on the command line (Felix's names).
MANIFEST = {
    "morning-w1-meditation": "meditacion-1.mp4",
    "morning-w1-movement": "Morning-exerciseW1.mp4",
}
# Optional: first of these found in the folder is uploaded as "morning-ambient".
AMBIENT = ("ambient.m4a", "ambient.mp3", "ambient.wav", "musica.mp3", "musica.m4a")

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IDS_FILE = os.path.join(REPO, "program_playback_ids.json")


def upload(key: str, path: str) -> str:
    print(f"↑ {key}  ←  {os.path.basename(path)}  ({os.path.getsize(path) / 1e6:.0f} MB)", flush=True)
    up = api("POST", "/video/v1/uploads", {
        "cors_origin": "*",
        "new_asset_settings": {
            "playback_policies": ["public"],
            "video_quality": "basic",
            "passthrough": f"program:{key}",
        },
    })
    curl(["-X", "PUT", "-T", path, "-o", "/dev/null", up["url"]], auth=False)

    asset_id = None
    for _ in range(180):
        u = api("GET", f"/video/v1/uploads/{up['id']}")
        if u.get("status") == "errored":
            die(f"Upload errored for {key}: {u.get('error')}")
        asset_id = u.get("asset_id")
        if asset_id:
            break
        time.sleep(5)
    if not asset_id:
        die(f"Timed out waiting for the asset for {key}")

    for _ in range(360):
        asset = api("GET", f"/video/v1/assets/{asset_id}")
        if asset["status"] == "ready":
            break
        if asset["status"] == "errored":
            die(f"Mux could not process {key}: {asset.get('errors')}")
        time.sleep(5)
    else:
        die(f"Timed out waiting for {key} to finish processing")

    public = [p["id"] for p in asset.get("playback_ids") or [] if p.get("policy") == "public"]
    if not public:
        die(f"{key} has no public playback id (asset {asset_id}).")
    print(f"  ✓ ready — public playback id {public[0]}  ({asset.get('duration', 0):.0f}s, asset {asset_id})", flush=True)
    return public[0]


def main() -> None:
    if not (os.environ.get("MUX_TOKEN_ID") and os.environ.get("MUX_TOKEN_SECRET")):
        die("Set MUX_TOKEN_ID and MUX_TOKEN_SECRET first.")
    if len(sys.argv) < 2:
        die("Give the folder that holds Felix's Week 1 files.")
    folder = os.path.expanduser(sys.argv[1])
    missing = [f for f in MANIFEST.values() if not os.path.isfile(os.path.join(folder, f))]
    if missing:
        die(f"Missing in {folder}: {missing}")

    jobs = dict(MANIFEST)
    ambient = next((f for f in AMBIENT if os.path.isfile(os.path.join(folder, f))), None)
    if ambient:
        jobs["morning-ambient"] = ambient
    else:
        print("· no ambient track in the folder (optional) — the app hides the music toggle")

    ids = load(IDS_FILE)
    for key, name in jobs.items():
        if ids.get(key):
            print(f"· {key}: already uploaded ({ids[key]})")
            continue
        ids[key] = upload(key, os.path.join(folder, name))
        save(IDS_FILE, ids)

    print(f"\nDone. {len(ids)} ids in {os.path.relpath(IDS_FILE)}. Commit it and push to deploy.")


if __name__ == "__main__":
    main()
