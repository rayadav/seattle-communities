#!/usr/bin/env python3
"""
Seattle Communities - Nightly Event Scanner & Gap Analyzer
Analyzes events.json against groups_with_urls.csv to identify upcoming date gaps,
organizations lacking recent events, and upcoming date windows.
"""

import json
import csv
import sys
from datetime import datetime, timedelta
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
CSV_PATH = REPO_DIR / "groups_with_urls.csv"
EVENTS_PATH = REPO_DIR / "events.json"

def main():
    if not EVENTS_PATH.exists() or not CSV_PATH.exists():
        print(f"Error: Missing required files in {REPO_DIR}", file=sys.stderr)
        sys.exit(1)

    with open(CSV_PATH, "r", encoding="utf-8") as f:
        groups = list(csv.DictReader(f))

    with open(EVENTS_PATH, "r", encoding="utf-8") as f:
        events = json.load(f)

    print(f"Loaded {len(groups)} community groups and {len(events)} scheduled events.\n")

    # Current event date range
    dates = sorted(set(e["dateString"] for e in events))
    print(f"Current event date window: {dates[0]} to {dates[-1]}")

    # Count events per organization
    org_counts = {}
    for g in groups:
        org_counts[g["Group name"]] = 0
    for e in events:
        org = e.get("organization")
        if org in org_counts:
            org_counts[org] += 1

    # Single-event organizations that could use additional dates
    single_event_orgs = [org for org, count in org_counts.items() if count <= 1]
    print(f"Organizations with 1 or fewer events: {len(single_event_orgs)}/{len(groups)}")

    print("\nTop 10 candidate organizations for new event additions:")
    for org in single_event_orgs[:10]:
        grp = next(g for g in groups if g["Group name"] == org)
        print(f"  - {org} ({grp['Activity type']} · {grp['Area']})")
        print(f"    URL: {grp['Events URL']}")

if __name__ == "__main__":
    main()
