#!/usr/bin/env python3
"""
Seattle Communities - Event Coverage & Gap Analyzer
Analyzes events.json against groups_with_urls.csv to identify upcoming date gaps,
organizations lacking upcoming events, and weekend coverage across core pillars.
"""

import json
import csv
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import defaultdict

REPO_DIR = Path(__file__).resolve().parent.parent
CSV_PATH = REPO_DIR / "groups_with_urls.csv"
EVENTS_PATH = REPO_DIR / "events.json"

PRIORITY_PILLARS = {
    "Fungi & Foraging": ["myco", "mush", "fungi", "forag"],
    "Salmon & Watersheds": ["salmon", "watershed", "river", "marine", "salish", "estuary"],
    "Botany & Birding": ["bird", "audubon", "plant", "botan", "tree", "forest", "track", "wild"],
    "Maker & Tool Libraries": ["maker", "tool", "woodshop", "craft", "repair", "metal", "blacksmith"],
    "Community Science & Discourse": ["astronom", "science", "soundbio", "bio", "microscop", "robotic"]
}

def get_today_str():
    utc_now = datetime.now(timezone.utc)
    pacific_now = utc_now - timedelta(hours=7)
    return pacific_now.strftime("%Y-%m-%d")

def main():
    if not EVENTS_PATH.exists() or not CSV_PATH.exists():
        print(f"Error: Missing required files in {REPO_DIR}", file=sys.stderr)
        sys.exit(1)

    today_str = get_today_str()

    with open(CSV_PATH, "r", encoding="utf-8") as f:
        groups = list(csv.DictReader(f))

    with open(EVENTS_PATH, "r", encoding="utf-8") as f:
        events = json.load(f)

    upcoming_events = [
        e for e in events
        if (e.get("dateString") or e.get("start", "")[:10]) >= today_str
    ]

    print(f"=== Seattle Communities Event Coverage Analysis ({today_str}) ===")
    print(f"Total Groups Cataloged: {len(groups)}")
    print(f"Total Scheduled Events: {len(events)}")
    print(f"Upcoming Active Events (>= {today_str}): {len(upcoming_events)}\n")

    # Upcoming coverage by date window (next 4 weekends)
    today_dt = datetime.fromisoformat(today_str).date()
    weekend_counts = defaultdict(int)
    for ev in upcoming_events:
        d_str = ev.get("dateString") or ev.get("start", "")[:10]
        try:
            d = datetime.fromisoformat(d_str).date()
            diff_days = (d - today_dt).days
            if 0 <= diff_days <= 28:
                # Group into calendar week or day
                if d.weekday() in (5, 6): # Sat / Sun
                    weekend_counts[d_str] += 1
        except Exception:
            pass

    print("Upcoming Weekend Density (next 4 weeks):")
    for d_str in sorted(weekend_counts.keys())[:8]:
        d = datetime.fromisoformat(d_str).date()
        day_name = d.strftime("%a %b %d")
        print(f"  - {day_name}: {weekend_counts[d_str]} events")

    # Count upcoming events per group
    upcoming_per_group = {g["Group name"]: 0 for g in groups}
    for ev in upcoming_events:
        org = ev.get("organization")
        if org in upcoming_per_group:
            upcoming_per_group[org] += 1

    zero_upcoming = [g for g in groups if upcoming_per_group[g["Group name"]] == 0]
    print(f"\nGroups with 0 upcoming events: {len(zero_upcoming)} / {len(groups)}")

    # Pillar Analysis
    print("\n--- Priority Pillar Upcoming Coverage ---")
    for pillar, kws in PRIORITY_PILLARS.items():
        matching_groups = [
            g for g in groups
            if any(k in g["Group name"].lower() or k in g.get("Activity type", "").lower() for k in kws)
        ]
        active_in_pillar = [
            g for g in matching_groups if upcoming_per_group[g["Group name"]] > 0
        ]
        zero_in_pillar = [
            g for g in matching_groups if upcoming_per_group[g["Group name"]] == 0
        ]
        print(f"\n{pillar}: {len(active_in_pillar)}/{len(matching_groups)} groups currently active")
        if zero_in_pillar:
            print("  Top groups needing upcoming event research:")
            for g in zero_in_pillar[:4]:
                print(f"    * {g['Group name']} ({g.get('Area', 'Seattle')}) -> {g.get('Events URL')}")

if __name__ == "__main__":
    main()
