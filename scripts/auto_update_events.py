#!/usr/bin/env python3
"""
Seattle Communities - Autonomous Nightly Event Updater
Designed to run unattended via GitHub Actions or locally.

1. Reads groups_with_urls.csv and events.json.
2. Identifies community organizations with low or zero event coverage.
3. Uses Gemini API with Google Search grounding to discover 3-5 verified upcoming events.
4. Validates, deduplicates, appends, and sorts new events into events.json.
"""

import os
import sys
import json
import csv
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
import urllib.request
import urllib.error

REPO_DIR = Path(__file__).resolve().parent.parent
CSV_PATH = REPO_DIR / "groups_with_urls.csv"
EVENTS_PATH = REPO_DIR / "events.json"

REQUIRED_FIELDS = [
    "id", "title", "organization", "activityType",
    "venue", "area", "start", "end", "timeString",
    "dateString", "description", "url"
]

def load_env_file():
    """Load simple KEY=VALUE pairs from .env in REPO_DIR into os.environ if not already set."""
    env_file = REPO_DIR / ".env"
    if env_file.exists():
        try:
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip("'\"")
                    if key and key not in os.environ:
                        os.environ[key] = val
        except Exception as e:
            print(f"Warning: could not read .env file: {e}", file=sys.stderr)

def get_today_str():
    # Use Pacific Time (UTC-7 or UTC-8)
    utc_now = datetime.now(timezone.utc)
    # Approximate Pacific Time (UTC-7 for PDT, UTC-8 for PST)
    pacific_now = utc_now - timedelta(hours=7)
    return pacific_now.strftime("%Y-%m-%d")

def find_candidate_groups(groups, events, count=8):
    """Find community groups from CSV that currently have the fewest events in events.json."""
    org_counts = {g["Group name"]: 0 for g in groups}
    for ev in events:
        org = ev.get("organization")
        if org in org_counts:
            org_counts[org] += 1

    # Sort groups by event count (ascending), preferring groups with 0 events
    sorted_groups = sorted(groups, key=lambda g: org_counts.get(g["Group name"], 0))
    return sorted_groups[:count]

def query_gemini_for_events(api_key, candidates, today_str):
    """Use Gemini with Google Search grounding to find verified upcoming community events."""
    models_to_try = [
        os.environ.get("GEMINI_MODEL", "").strip(),
        "gemini-3.8-flash",
        "gemini-2.5-flash",
        "gemini-1.5-flash",
    ]
    # Remove duplicates and empty strings while preserving order
    seen = set()
    models = []
    for m in models_to_try:
        if m and m not in seen:
            seen.add(m)
            models.append(m)

    group_list_text = "\n".join([
        f"- {g['Group name']} (Category: {g.get('Activity type', 'Community')}, Area: {g.get('Area', 'Seattle')})\n"
        f"  Website: {g.get('Website', '')}\n"
        f"  Events Page: {g.get('Events URL', '')}"
        for g in candidates
    ])

    prompt = f"""
You are an expert Seattle community event researcher. Today's date is {today_str}.
Your task is to search the web for active, verified, upcoming community events in the Seattle metropolitan area hosted by these organizations:

{group_list_text}

Rules:
1. All proposed events must be real and scheduled to occur on or after {today_str} (within the next 1 to 4 weeks). DO NOT return past events.
2. Select 3 to 5 high-quality, verified community events across different organizations.
3. Every event must include a valid source URL linking to the organization's official event page or calendar.
4. Output MUST be ONLY a valid raw JSON array of event objects with no additional markdown, no code blocks, and no extra commentary.

Each event object in the array must adhere strictly to this schema:
{{
  "id": "unique-kebab-cased-id-with-date-e.g-org-event-20261015",
  "title": "Clear Title of Event",
  "organization": "Exact Organization Name from the candidate list",
  "activityType": "Category matching the organization (e.g. Sports, Outdoors, Arts & Culture, Science & Technology, Maker & Crafts, Games & Hobbies)",
  "venue": "Full venue name and address (e.g. 'Phinney Center (6532 Phinney Ave N, Seattle, WA 98103)')",
  "area": "Neighborhood or region (e.g. 'Seattle (Phinney Ridge)', 'Seattle (Capitol Hill)', 'South King County (Renton)')",
  "start": "ISO 8601 start timestamp with timezone offset (e.g. '2026-10-15T18:30:00-07:00')",
  "end": "ISO 8601 end timestamp with timezone offset (e.g. '2026-10-15T20:30:00-07:00')",
  "timeString": "Human-friendly time range (e.g. '6:30 PM – 8:30 PM')",
  "dateString": "YYYY-MM-DD format",
  "description": "2-3 concise, informative sentences about the community event and who can attend.",
  "url": "https://official-source-url-for-this-event",
  "cost": "Free or ticket price",
  "recurrence": "e.g. 'Weekly on Thursdays' or 'Monthly (1st Saturdays)' or 'Special Event'"
}}
"""

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ],
        "tools": [
            {"google_search": {}}
        ],
        "generationConfig": {
            "temperature": 0.2
        }
    }

    req_data = json.dumps(payload).encode("utf-8")
    data = None
    last_error = None

    for model in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        req = urllib.request.Request(
            url,
            data=req_data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        try:
            print(f"Querying Gemini API with model: {model}...")
            with urllib.request.urlopen(req, timeout=90) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            last_error = None
            break
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8")
            print(f"Gemini API HTTP Error {e.code} with model '{model}': {err_body}", file=sys.stderr)
            last_error = f"HTTP {e.code}: {err_body}"
            continue
        except Exception as e:
            print(f"Error calling Gemini API with model '{model}': {e}", file=sys.stderr)
            last_error = str(e)
            continue

    if not data:
        print(f"All Gemini models failed. Last error: {last_error}", file=sys.stderr)
        return [], True  # Return empty list and is_error=True

    # Extract text content from candidate response
    try:
        candidates_resp = data.get("candidates", [])
        if not candidates_resp:
            print("No candidates returned from Gemini API.", file=sys.stderr)
            return [], True
        
        parts = candidates_resp[0].get("content", {}).get("parts", [])
        raw_text = "".join(p.get("text", "") for p in parts).strip()
    except Exception as e:
        print(f"Failed to parse Gemini response structure: {e}", file=sys.stderr)
        return [], True

    # Strip markdown code blocks if present (```json ... ```)
    cleaned_text = raw_text
    if "```" in cleaned_text:
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned_text)
        if match:
            cleaned_text = match.group(1).strip()

    try:
        new_events = json.loads(cleaned_text)
        if isinstance(new_events, dict) and "events" in new_events:
            new_events = new_events["events"]
        if not isinstance(new_events, list):
            print(f"Expected a JSON list of events, got: {type(new_events)}", file=sys.stderr)
            return [], True
        return new_events, False
    except Exception as e:
        print(f"Failed to decode JSON from Gemini output: {e}\nRaw output:\n{raw_text}", file=sys.stderr)
        return [], True

def validate_and_filter_event(ev, today_str, existing_ids, existing_title_starts):
    """Validate schema and ensure event is upcoming and not a duplicate."""
    for field in REQUIRED_FIELDS:
        if field not in ev or not str(ev[field]).strip():
            print(f"Skipping event missing field '{field}': {ev.get('title', 'Unknown')}")
            return False

    ev_id = str(ev["id"]).strip()
    if ev_id in existing_ids:
        print(f"Skipping duplicate event ID: {ev_id}")
        return False

    date_str = ev.get("dateString", "")
    if date_str < today_str:
        print(f"Skipping past event: {ev['title']} ({date_str} < {today_str})")
        return False

    title_start_key = (ev["title"].strip().lower(), ev["start"].strip())
    if title_start_key in existing_title_starts:
        print(f"Skipping duplicate title & start: {ev['title']} on {ev['start']}")
        return False

    return True

def main():
    if not CSV_PATH.exists() or not EVENTS_PATH.exists():
        print(f"Error: Missing CSV or events.json in {REPO_DIR}", file=sys.stderr)
        sys.exit(1)

    load_env_file()
    today_str = get_today_str()
    print(f"Seattle Communities Auto-Updater running for {today_str}...")

    with open(CSV_PATH, "r", encoding="utf-8") as f:
        groups = list(csv.DictReader(f))

    with open(EVENTS_PATH, "r", encoding="utf-8") as f:
        events = json.load(f)

    print(f"Loaded {len(groups)} community groups and {len(events)} current events.")

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        print("\nNotice: GEMINI_API_KEY is not set.")
        print("Set the GEMINI_API_KEY environment variable or create a .env file in the repository root:")
        print("  GEMINI_API_KEY=your_gemini_api_key_here")
        sys.exit(0)

    candidate_groups = find_candidate_groups(groups, events, count=8)
    print(f"\nResearching upcoming events for {len(candidate_groups)} priority groups...")
    for g in candidate_groups:
        print(f"  - {g['Group name']} ({g.get('Activity type', '')})")

    proposed_events, is_error = query_gemini_for_events(api_key, candidate_groups, today_str)
    if is_error:
        print("Failed to retrieve valid event proposals from Gemini API.", file=sys.stderr)
        sys.exit(1)

    print(f"\nReceived {len(proposed_events)} proposed events from Gemini research.")

    existing_ids = set(e.get("id") for e in events)
    existing_title_starts = set((e.get("title", "").strip().lower(), e.get("start", "").strip()) for e in events)

    valid_additions = []
    for ev in proposed_events:
        if validate_and_filter_event(ev, today_str, existing_ids, existing_title_starts):
            valid_additions.append(ev)
            existing_ids.add(ev["id"])
            existing_title_starts.add((ev["title"].strip().lower(), ev["start"].strip()))

    if not valid_additions:
        print("No new valid, non-duplicate events found today.")
        sys.exit(0)

    print(f"\nAdding {len(valid_additions)} new verified events to events.json:")
    for ev in valid_additions:
        print(f"  + [{ev['dateString']}] {ev['title']} ({ev['organization']})")
        events.append(ev)

    # Sort all events chronologically by start date, then title
    events.sort(key=lambda e: (e.get("start", ""), e.get("title", "")))

    with open(EVENTS_PATH, "w", encoding="utf-8") as f:
        json.dump(events, f, indent=2, ensure_ascii=False)

    min_path = REPO_DIR / "events.min.json"
    with open(min_path, "w", encoding="utf-8") as f:
        json.dump(events, f, separators=(',', ':'), ensure_ascii=False)

    print(f"\nSuccessfully updated events.json and events.min.json. Total events now: {len(events)}")

if __name__ == "__main__":
    main()
