#!/usr/bin/env python3
"""Upload Felix's introduction videos to Mux with PUBLIC playback.

    cd ~/dev/movewithoutpain-backend
    export MUX_TOKEN_ID=...  MUX_TOKEN_SECRET=...
    python3 tools/intro_upload.py /path/to/folder/with/the/mp4s

Writes intro_playback_ids.json in the repo root ({key: public playback id}),
which paths.py reads: one id per routine slug plus "app" for the general
introduction. Commit that file and push to deploy.

These are promotional clips, free for everyone before the paywall, so unlike the
exercise videos (tools/mux_upload.py, signed only) they use public playback ids:
the app streams https://stream.mux.com/{id}.m3u8 directly, with no signing
round-trip and no token that can expire mid-clip.

Idempotent: keys already in intro_playback_ids.json are skipped.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time

API = "https://api.mux.com"

# key -> file name in the folder given on the command line. The keys for routines
# are the path slugs in paths.py. "presentacion" is Felix's second general clip,
# kept so the app intro can be swapped by editing paths.py alone.
MANIFEST = {
    "app": "app-intro.mp4",
    "presentacion": "presentacion.mp4",
    "morning": "morning.mp4",
    "mobility": "mobility.mp4",
    "stretch": "flex.mp4",
    "strength": "streght.mp4",   # Felix's file name
    "night": "night.mp4",
}

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IDS_FILE = os.path.join(REPO, "intro_playback_ids.json")


def die(msg: str) -> None:
    print(f"✖ {msg}", file=sys.stderr)
    sys.exit(1)


def curl(args: list, auth: bool = True) -> str:
    cfg = ""
    if auth:
        cfg = f'user = "{os.environ["MUX_TOKEN_ID"]}:{os.environ["MUX_TOKEN_SECRET"]}"\n'
    res = subprocess.run(
        ["curl", "-sS", "--fail-with-body", "-K", "-"] + args,
        input=cfg, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
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
        die("Set MUX_TOKEN_ID and MUX_TOKEN_SECRET first.")
    if len(sys.argv) < 2:
        die("Give the folder that holds the intro mp4s.")
    folder = os.path.expanduser(sys.argv[1])
    missing = [f for f in MANIFEST.values() if not os.path.isfile(os.path.join(folder, f))]
    if missing:
        die(f"Missing in {folder}: {missing}")

    ids = load(IDS_FILE)
    for key, name in MANIFEST.items():
        if ids.get(key):
            print(f"· {key}: already uploaded ({ids[key]})")
            continue
        path = os.path.join(folder, name)
        print(f"↑ {key}  ←  {name}  ({os.path.getsize(path) / 1e6:.0f} MB)", flush=True)
        upload = api("POST", "/video/v1/uploads", {
            "cors_origin": "*",
            "new_asset_settings": {
                "playback_policies": ["public"],
                "video_quality": "basic",
                "passthrough": f"intro:{key}",
            },
        })
        curl(["-X", "PUT", "-T", path, "-o", "/dev/null", upload["url"]], auth=False)

        asset_id = None
        for _ in range(120):
            up = api("GET", f"/video/v1/uploads/{upload['id']}")
            if up.get("status") == "errored":
                die(f"Upload errored for {key}: {up.get('error')}")
            asset_id = up.get("asset_id")
            if asset_id:
                break
            time.sleep(5)
        if not asset_id:
            die(f"Timed out waiting for the asset for {key}")

        for _ in range(240):
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
        ids[key] = public[0]
        save(IDS_FILE, ids)
        print(f"  ✓ ready — public playback id {public[0]}  ({asset.get('duration', 0):.0f}s, asset {asset_id})", flush=True)

    print(f"\nDone. {len(ids)} ids in {os.path.relpath(IDS_FILE)}.")


if __name__ == "__main__":
    main()
