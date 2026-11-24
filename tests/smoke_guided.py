"""Smoke test for GET /guided and the Coach safety note (FastAPI TestClient + SQLite).

    python3 tests/smoke_guided.py      (from the repo root; needs requirements.txt minus psycopg2)
"""
import os
import sys
import tempfile

db_file = os.path.join(tempfile.mkdtemp(), "smoke.db")
os.environ["DATABASE_URL"] = f"sqlite:///{db_file}"
os.environ.setdefault("SUBSCRIPTIONS_ENABLED", "true")
os.environ.pop("DEEPSEEK_API_KEY", None)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402

import models  # noqa: E402

models.Base.metadata.create_all(models.engine)
import main  # noqa: E402
import coach_safety  # noqa: E402

failures = []


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        failures.append(name)


with TestClient(main.app) as client:
    free = {"X-Device-Id": "smoke-device-1", "X-MWP-Api": "5"}
    r = client.get("/guided", headers=free)
    check("/guided 200", r.status_code == 200)
    g = r.json()
    cats = {c["slug"]: c for c in g["categories"]}
    check("three categories in order", [c["slug"] for c in g["categories"]] == ["mobility", "flexibility", "strength"])
    check("flexibility lists 'stretches'", cats["flexibility"]["exercise_category"] == "stretches")
    routines = {r["slug"]: r for c in g["categories"] for r in c["routines"]}
    check("six routines", len(routines) == 6)
    orders = lambda r: [s["exercise"]["order"] for s in r["steps"]]
    check("Hip Mobility = 1,2,3,4", orders(routines["hip-mobility"]) == [1, 2, 3, 4])
    check("General Mobility = 5,6,17", orders(routines["general-mobility"]) == [5, 6, 17])
    check("Hip Flexibility = 10,12,13,19", orders(routines["hip-flexibility"]) == [10, 12, 13, 19])
    check("Hip Opening = 14,15,18", orders(routines["hip-opening"]) == [14, 15, 18])
    check("Hamstrings = 11,16,20", orders(routines["hamstrings"]) == [11, 16, 20])
    check("Glute Strength = 7,8,9", orders(routines["glute-strength"]) == [7, 8, 9])
    check("free routine unlocked for non-subscriber", routines["hip-mobility"]["unlocked"] is True)
    check("routine with premium exercise locked for non-subscriber",
          routines["general-mobility"]["unlocked"] is False and routines["general-mobility"]["premium"] is True)
    locked_step = routines["general-mobility"]["steps"][2]["exercise"]
    check("locked step has no video ids", not locked_step.get("mux_playback_id") and not locked_step.get("youtube_video_id"))
    check("intro attached to mobility routines", bool(routines["hip-mobility"]["intro_playback_id"]))
    check("duration includes intro", routines["hip-mobility"]["duration_s"] == 60 + 60 + 90 + 90 + 90)
    days = g["free_week"]["days"]
    check("free week has 7 days", [d["day"] for d in days] == list(range(1, 8)))
    check("7 different sessions", len({tuple(orders(d)) for d in days}) == 7)
    check("all free-week days unlocked and free", all(d["unlocked"] and not d["premium"] for d in days))
    check("weekly schedule has 7 entries", len(g["weekly_schedule"]) == 7)
    check("daily_pacing reported", isinstance(g["daily_pacing"], bool))

    # Paths/today unchanged for older builds.
    r4 = client.get("/paths", headers={"X-Device-Id": "smoke-device-1", "X-MWP-Api": "4"})
    check("/paths api 4 still 200", r4.status_code == 200)
    r5 = client.get("/paths", headers=free)
    check("/paths api 5 same list as api 4", [p["slug"] for p in r5.json()["paths"]] == [p["slug"] for p in r4.json()["paths"]])
    check("/today still 200", client.get("/today", headers=free).status_code == 200)

# Coach safety
check("pain detected (en)", coach_safety.mentions_pain("My knee hurts when I do lunges"))
check("pain detected (es, accents)", coach_safety.mentions_pain("Tengo una lesión en la cadera"))
check("dolor detected", coach_safety.mentions_pain("me da dolor en la espalda"))
check("no false positive", not coach_safety.mentions_pain("How can I improve hip mobility?"))
out = coach_safety.ensure_safety_note("Try slower breathing.", "es")
check("note appended in Spanish", "fisioterapeuta" in out)
same = coach_safety.ensure_safety_note("Please see a physical therapist first.", "en")
check("no duplicate note", same == "Please see a physical therapist first.")
check("rules in system prompt source", "COACH_SAFETY_RULES" in open(main.__file__).read())

print(f"\n{len(failures)} failure(s)")
sys.exit(1 if failures else 0)
