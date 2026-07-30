# youtube_ids.py
# Mapping of exercise names (matching seed.py) to YouTube Shorts IDs

YOUTUBE_IDS = {
    "Pelvic Tilts": "Gy9k15DHOYE",
    "Hip Circles": "k8mb7KgVVTo",
    "Back Extension to the Side": "nYv8yR2VQ7c",
    "Knee to Shoulder": "NwbwUBPA7Ok",
    "Lying Leg Raise (Battement)": "0bb8pV6BNmk",
    "Glute Kick": "oZaUIY-BWGo",
    "Glute Bridge": "YK-3XblqBU4",
    "Single Leg Raise (Seated)": "3t_yvFT5x5Q",
    "V-Raise (Seated)": "tEFHgm1V8as",
    "High Hip Flexion (Chair)": "3_rkMPS1JzI",
    "Standing Hamstring Stretch": "i1hv9Lauono",
    "Deep Lunge": "H9ueuk7ALi4",
    "Low Lunge": "aXdflKW7c6U",
    "Pancake Stretch": "pmUM7p8EQN8",
}

if __name__ == "__main__":
    print("✅ YouTube IDs mapped successfully.")
    for name, vid in YOUTUBE_IDS.items():
        print(f"  {name}: {vid}")
