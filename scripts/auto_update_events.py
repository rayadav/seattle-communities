#!/usr/bin/env python3
"""
Seattle Communities - Autonomous Event Updater & Deep Researcher
Designed to run unattended via scheduled jobs or locally.

1. Reads groups_with_urls.csv and events.json.
2. Identifies upcoming calendar coverage and gaps across core pillars:
   - Fungi, Mycology, Foraging & Lichenology
   - Watersheds, Salmon Runs, Botany & Birding
   - Maker Culture, Community Woodshops, Tool Libraries & Reuse
   - Community Science, Discourse & Natural History
3. Analyzes upcoming events (on or after today) per organization.
4. Uses Gemini API with Google Search grounding to discover 12-25 verified upcoming events.
5. Validates schema, deduplicates against existing events, appends, and sorts chronologically.
6. Automatically compiles events.min.json and increments the service worker cache version in sw.js.
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
MIN_EVENTS_PATH = REPO_DIR / "events.min.json"
SW_PATH = REPO_DIR / "sw.js"

REQUIRED_FIELDS = [
    "id", "title", "organization", "activityType",
    "venue", "area", "start", "end", "timeString",
    "dateString", "description", "url"
]

PRIORITY_KEYWORDS = [
    "myco", "mush", "fungi", "forag", "salmon", "watershed", "river",
    "bird", "audubon", "plant", "botan", "tree", "forest", "track",
    "wild", "maker", "tool", "woodshop", "craft", "astronom", "science",
    "soundbio", "bio", "diybio", "microscop", "repair", "salish", "marine"
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
    # Use Pacific Time (UTC-7 for PDT, UTC-8 for PST)
    utc_now = datetime.now(timezone.utc)
    pacific_now = utc_now - timedelta(hours=7)
    return pacific_now.strftime("%Y-%m-%d")

def get_seasonal_context(month):
    if month in (9, 10, 11):
        return (
            "Autumn Focus: Peak Pacific Northwest fall mushroom fruiting and mycological society exhibitions; "
            "spawning salmon returns in Puget Sound creeks (Chum, Chinook, Coho); fall bird migration and waterfowl arrivals; "
            "indoor tool library fix-it workshops and maker seasonal classes."
        )
    elif month in (12, 1, 2):
        return (
            "Winter Focus: Christmas bird counts and winter waterfowl surveys; indoor tool library fix-it nights and woodworking; "
            "winter tree ID and botany dormancy walks; microscopy and electronics meetups; cozy community talks."
        )
    elif month in (3, 4, 5):
        return (
            "Spring Focus: Spring native wildflower blooms and botanical garden tours; spring morel foraging and early fungi; "
            "spring songbird arrival and nesting; community garden work parties and tool checkout season."
        )
    else:
        return (
            "Summer Focus: Low-tide intertidal marine naturalist walks; outdoor foraging and botanical hikes; "
            "star parties and astronomy outings; outdoor community build days and repair cafes."
        )

def find_candidate_groups(groups, events, today_str, count=16):
    """
    Find priority community groups that have zero or few UPCOMING events (start >= today).
    Gives heavy weight to priority pillars (Fungi, Nature/Salmon, Birding, Botany, Tool Libraries, Makers).
    """
    # Count only upcoming events from today onwards
    upcoming_counts = {g["Group name"]: 0 for g in groups}
    for ev in events:
        ev_date = ev.get("dateString") or ev.get("start", "")[:10]
        if ev_date >= today_str:
            org = ev.get("organization")
            if org in upcoming_counts:
                upcoming_counts[org] += 1

    # Score groups: lower count = higher priority, priority keywords give extra boost
    def score_group(g):
        name = g["Group name"].lower()
        cat = g.get("Activity type", "").lower()
        is_priority = any(k in name or k in cat for k in PRIORITY_KEYWORDS)
        upcoming = upcoming_counts.get(g["Group name"], 0)
        
        # Priority groups with 0 upcoming events get top priority (score 0),
        # non-priority with 0 get score 10, priority with 1 get score 20, etc.
        priority_offset = 0 if is_priority else 10
        return (upcoming * 20) + priority_offset

    sorted_groups = sorted(groups, key=score_group)
    return sorted_groups[:count]

def query_gemini_for_events(api_key, candidates, today_str):
    """Use Gemini with Google Search grounding to find comprehensive, verified upcoming community events."""
    models_to_try = [
        os.environ.get("GEMINI_MODEL", "").strip(),
        "gemini-3.8-flash",
        "gemini-2.5-flash",
        "gemini-1.5-flash",
    ]
    seen = set()
    models = []
    for m in models_to_try:
        if m and m not in seen:
            seen.add(m)
            models.append(m)

    month = int(today_str.split("-")[1])
    seasonal_context = get_seasonal_context(month)

    group_list_text = "\n".join([
        f"- {g['Group name']} (Category: {g.get('Activity type', 'Community')}, Area: {g.get('Area', 'Seattle')})\n"
        f"  Website: {g.get('Website', '')}\n"
        f"  Events Page: {g.get('Events URL', '')}"
        for g in candidates
    ])

    prompt = f"""
You are an expert Seattle community event researcher and natural science historian. Today's date is {today_str}.
{seasonal_context}

Your mission is to perform a thorough, comprehensive search for active, verified, upcoming community events in the Seattle metropolitan area and Puget Sound.
Target these community organizations with priority:

{group_list_text}

Rules for Event Discovery:
1. All proposed events must be real and scheduled to occur on or after {today_str} (within the next 1 to 6 weeks).
2. DO NOT return past events or made-up events. Verify each against current real calendar listings.
3. Aim to find 12 to 25 high-quality, verified community events across these organizations and related Puget Sound community gatherings.
4. Special attention must be given to:
   - Annual wild mushroom exhibitions, forays, and mycology talks
   - Salmon return viewing tours and watershed steward gatherings
   - Guided birding walks and wildlife tracking outings
   - Native plant walks and botanical tours
   - Tool library repair cafés, fix-it nights, and hands-on maker workshops
   - Public natural science and astronomy lectures
5. Every event must include a valid source URL linking to the organization's official event page or calendar.
6. Output MUST be ONLY a valid raw JSON array of event objects with no additional markdown, no code blocks, and no extra commentary.

Each event object in the array must adhere strictly to this schema:
{{
  "id": "unique-kebab-cased-id-with-date-e.g-org-event-20261025",
  "title": "Clear Title of Event",
  "organization": "Exact Organization Name matching the candidate list or official group",
  "activityType": "Category matching the organization (e.g. Nature/Conservation, Birding, Tools, Maker & Crafts, Science, Art, Outdoors)",
  "venue": "Full venue name and address (e.g. 'Floral Hall, Forest Park (802 E Mukilteo Blvd, Everett, WA 98203)')",
  "area": "Neighborhood or region (e.g. 'Seattle (Washington Park)', 'Seattle (Carkeek Park)', 'Everett', 'Shoreline', 'Renton')",
  "start": "ISO 8601 start timestamp with timezone offset (e.g. '2026-10-25T10:00:00-07:00')",
  "end": "ISO 8601 end timestamp with timezone offset (e.g. '2026-10-25T15:00:00-07:00')",
  "timeString": "Human-friendly time range (e.g. '10:00 AM – 3:00 PM')",
  "dateString": "YYYY-MM-DD format",
  "description": "2-3 concise, informative sentences about the community event and who can attend.",
  "url": "https://official-source-url-for-this-event",
  "cost": "Free or ticket price",
  "recurrence": "e.g. 'Annual Wild Mushroom Show' or 'Weekly on Saturdays' or 'Special Event'"
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
            with urllib.request.urlopen(req, timeout=120) as resp:
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
        return [], True

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

def validate_and_filter_event(ev, today_str, existing_ids, existing_title_starts, existing_urls_dates):
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

    url_date_key = (ev["url"].strip().lower(), date_str.strip())
    if url_date_key in existing_urls_dates:
        print(f"Skipping duplicate url & date: {ev['url']} on {date_str}")
        return False

    return True

def bump_sw_cache_version():
    """Increment CACHE_NAME in sw.js to ensure progressive web app users get refreshed data."""
    if not SW_PATH.exists():
        return
    try:
        content = SW_PATH.read_text(encoding="utf-8")
        match = re.search(r"const CACHE_NAME = 'seattle-communities-v(\d+)';", content)
        if match:
            curr_ver = int(match.group(1))
            new_ver = curr_ver + 1
            new_content = content.replace(
                f"const CACHE_NAME = 'seattle-communities-v{curr_ver}';",
                f"const CACHE_NAME = 'seattle-communities-v{new_ver}';"
            )
            SW_PATH.write_text(new_content, encoding="utf-8")
            print(f"Bumped sw.js cache version from v{curr_ver} to v{new_ver}.")
        else:
            print("Notice: Could not match CACHE_NAME pattern in sw.js")
    except Exception as e:
        print(f"Warning: Failed to bump sw.js cache version: {e}", file=sys.stderr)

def main():
    if not CSV_PATH.exists() or not EVENTS_PATH.exists():
        print(f"Error: Missing CSV or events.json in {REPO_DIR}", file=sys.stderr)
        sys.exit(1)

    load_env_file()
    today_str = get_today_str()
    print(f"Seattle Communities Deep Event Researcher running for {today_str}...")

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

    candidate_groups = find_candidate_groups(groups, events, today_str, count=16)
    print(f"\nTargeting {len(candidate_groups)} priority & zero-coverage organizations...")
    for g in candidate_groups:
        print(f"  - {g['Group name']} ({g.get('Activity type', '')})")

    proposed_events, is_error = query_gemini_for_events(api_key, candidate_groups, today_str)
    if is_error:
        print("Failed to retrieve valid event proposals from Gemini API.", file=sys.stderr)
        sys.exit(1)

    print(f"\nReceived {len(proposed_events)} proposed events from Gemini research.")

    existing_ids = set(e.get("id") for e in events)
    existing_title_starts = set((e.get("title", "").strip().lower(), e.get("start", "").strip()) for e in events)
    existing_urls_dates = set((e.get("url", "").strip().lower(), (e.get("dateString") or e.get("start", "")[:10]).strip()) for e in events)

    valid_additions = []
    for ev in proposed_events:
        if validate_and_filter_event(ev, today_str, existing_ids, existing_title_starts, existing_urls_dates):
            valid_additions.append(ev)
            existing_ids.add(ev["id"])
            existing_title_starts.add((ev["title"].strip().lower(), ev["start"].strip()))
            existing_urls_dates.add((ev["url"].strip().lower(), ev["dateString"].strip()))

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

    with open(MIN_EVENTS_PATH, "w", encoding="utf-8") as f:
        json.dump(events, f, separators=(',', ':'), ensure_ascii=False)

    bump_sw_cache_version()

    print(f"\nSuccessfully updated events.json and events.min.json. Total events now: {len(events)}")

if __name__ == "__main__":
    main()
