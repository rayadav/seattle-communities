# Seattle Communities - Development & Event Maintenance Guidelines

## Core Mission
Seattle Communities is a local, high-performance community calendar and organization directory for the Puget Sound region.
The goal is to maintain rich, comprehensive, and up-to-date listings of real community gatherings, with an emphasis on authentic community-run, grassroots, and non-commercial events.

---

## High-Priority Interest Pillars
Whenever reviewing, searching, or updating events, ALWAYS conduct an in-depth review across these four priority pillars:

1. **Fungi, Mycology, Foraging & Lichenology**:
   - *Key Organizations:* Puget Sound Mycological Society (PSMS), Snohomish County Mycological Society (SCMS), Kitsap Peninsula Mycological Society (KPMS), South Sound Mushroom Club (SSMC), Northwest Mushroomers Association (NWMA), Tilth Alliance Foraging, Olympic Peninsula Fungi Festival.
   - *Seasonal Highlights:* Annual wild mushroom shows (October–November), spring morel and autumn fall forays, cultivation and microscopy workshops, ID clinics.

2. **Watershed Ecology, Salmon Runs, Botany & Birding**:
   - *Salmon & Watersheds:* Cedar River Salmon Journey (Seattle Aquarium naturalists), Carkeek Park Piper's Creek Salmon Stewards, Green Seattle Partnership, Duwamish Alive.
   - *Birding & Wildlife:* Birds Connect Seattle (formerly Seattle Audubon), Seward Park Audubon, Eastside Audubon, Tahoma Bird Alliance, Rainier/Skagit/Pilchuck Audubon, Wilderness Awareness School Wildlife Tracking Club.
   - *Botany & Native Flora:* Washington Native Plant Society (Central Puget Sound), PlantAmnesty (pinetum walks, pruning, soil workshops), UW Botanic Gardens / Washington Park Arboretum, Kubota Garden Foundation.

3. **Maker Culture, Community Woodshops, Tool Libraries & Creative Reuse**:
   - *Makerspaces & Woodshops:* Seattle Makers, Pratt Fine Arts Center, Bike Works Community Open Shop, Northwest Blacksmith Association.
   - *Tool Libraries & Reuse:* Capitol Hill Tool Library, West Seattle Tool Library, Northeast Seattle Tool Library, Ballard Tool Library, South King Tool Library (repair cafés, fix-it nights, clothing swaps, tool classes).

4. **Community Science, Discourse, Astronomy & Natural History**:
   - *Citizen Science, DIY Bio & Astronomy:* SoundBio Lab (DIY community biology, biomaterials, microscopes, biosensors at https://www.sound.bio/workshops), Seattle Astronomical Society (star parties, lectures), COASST (Coastal Observation and Seabird Survey Team), Pacific Northwest Microscopy Society, Seattle Robotics Society.
   - *Public Lectures & Gatherings:* Science on Tap Seattle, Pacific Science Center Science Communication Guild, UW Herbarium lectures.

---

## Thorough Review Standards (Never Miss Events)
When reviewing events for any given day, weekend, or month:
1. **Never perform a shallow or cursory scan**:
   - Do not stop after checking only 2–3 groups or glancing at existing listings.
   - Actively query time-bounded windows:
     - *Today / Tonight*: Check morning walks, afternoon workshops, and evening lectures/gatherings.
     - *This Weekend (Sat/Sun)*: Check recurring Saturday morning runs/walks, midday work parties, afternoon festivals.
     - *Upcoming 14–30 Days*: Check seasonal flagship dates (mushroom shows, salmon migration weekends, maker swaps).
2. **Seasonal Phenomenon Awareness**:
   - In **Autumn (Sep–Nov)**: Peak fall mushroom fruiting, chum/chinook/coho salmon returns to local streams, fall bird migration, arbor week restoration.
   - In **Winter (Dec–Feb)**: Winter bird counts, indoor tool library repair cafés, botany winter dormancy walks, microscopy meetings.
   - In **Spring (Mar–May)**: Spring flora blooms, morel foraging, spring bird arrival, community garden opening work parties.
   - In **Summer (Jun–Aug)**: Star parties, low-tide beach naturalist walks, outdoor foraging, kayak roll sessions.
3. **Event Schema, URL Verification & Deduplication Integrity**:
   - Every event must strictly adhere to the schema in `events.json`:
     `id`, `title`, `organization`, `activityType`, `venue`, `area`, `start`, `end`, `timeString`, `dateString` (MUST be `YYYY-MM-DD` matching `start[:10]`), `description`, `url`, `cost`, `recurrence`.
   - Verify that every event's `url` resolves to a live, non-404 webpage (`HTTP 200`). Prefer the specific event detail page or the organization's verified calendar URL in `groups_with_urls.csv`; never guess unverified `/events/` or `/calendar/` paths.
   - Prevent duplicates by matching against `id`, `(title.lower(), start)`, and `(url, dateString)`.
   - Maintain chronological sorting by `start`, then `title`.
4. **Cache & Minification Protocol**:
   - Whenever `events.json` is modified:
     - Generate minified `events.min.json` without whitespace.
     - Bump `CACHE_NAME` in `sw.js` (e.g. `seattle-communities-v12` -> `seattle-communities-v13`).
     - Commit all three files (`events.json`, `events.min.json`, `sw.js`).
