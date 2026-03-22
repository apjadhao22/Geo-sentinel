# PCMC Illegal Construction Detection System — Design Spec

## Overview

A satellite imagery-based system that detects illegal construction activity within the Pimpri Chinchwad Municipal Corporation (PCMC) area. The system fetches satellite images daily, compares them across multiple time intervals to detect changes indicative of construction, flags detected activity on a dashboard for PCMC officers to review, and tracks the lifecycle of each flagged spot.

## Goals

- Detect new construction activity (land clearing, excavation, foundation work, new structures, extensions to existing buildings) within the PCMC boundary (~181 sq km)
- Compare imagery across 1-day, 7-day, 15-day, and 30-day intervals to catch both rapid and gradual changes
- Provide an internal dashboard for PCMC officers to review flagged spots and mark them as legal or illegal
- Legal constructions enter a 12-month grace period, after which an officer is prompted to re-review
- Illegal constructions are continuously flagged until marked resolved
- Full audit trail of all officer actions, supervised by a super admin

## Tech Stack

- **Backend:** Python (FastAPI), Celery + Celery Beat for scheduling, Redis as message broker
- **Frontend:** React with Leaflet/Mapbox GL JS for map display
- **Database:** PostgreSQL + PostGIS for geospatial data
- **Object Storage:** MinIO (self-hosted, S3-compatible) for satellite imagery
- **ML:** PyTorch, Siamese U-Net for change detection
- **Satellite Imagery:** Planet Labs API (PlanetScope for daily 3-5m resolution)
- **Auth:** JWT-based authentication
- **Coordinate System:** EPSG:4326 (WGS84) for storage, EPSG:32643 (UTM Zone 43N) for area calculations

## System Architecture

Five core components:

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│  Image Ingestion │────▶│  Change Detection │────▶│  Flagging & State   │
│    Service       │     │    ML Pipeline    │     │     Management      │
└─────────────────┘     └──────────────────┘     └──────────┬──────────┘
                                                            │
                                                            ▼
┌─────────────────┐                              ┌─────────────────────┐
│   Auth & User   │◀────────────────────────────▶│    Dashboard API    │
│   Management    │                              │    + React Frontend │
└─────────────────┘                              └─────────────────────┘
```

---

## Component 1: Image Ingestion Service

### Behavior

- A daily cron job (Celery Beat) triggers at a fixed time (e.g., 6:00 AM IST)
- Calls the Planet Labs API with the PCMC boundary polygon as the area of interest
- Downloads the latest available image (may arrive as multiple tiles, stitched into a composite)
- Stores raw imagery in MinIO with metadata
- If cloud cover exceeds 30% over a tile, that tile is marked unusable; the system falls back to the last clear image for comparison
- After successful ingestion, publishes an event (Celery task) to trigger the ML pipeline

### API Quota Management

- PlanetScope subscriptions have monthly download quotas (measured in sq km). At ~181 sq km/day, expected monthly consumption is ~5,430 sq km.
- The ingestion service tracks cumulative monthly quota usage and surfaces it on the admin dashboard.
- When quota usage reaches 80%, admins are alerted. At 95%, the system switches to every-other-day ingestion to conserve quota.

### Failure Handling

- Planet API down or no image available: retry 3 times with exponential backoff, then alert admins via dashboard
- No usable image for 3+ consecutive days (e.g., monsoon): surface warning on dashboard

### Data Model

```
SatelliteImage
├── id (UUID)
├── captured_at (timestamp)
├── ingested_at (timestamp)
├── storage_path (string)
├── cloud_cover_pct (float)
├── resolution_meters (float)
├── bounds (PostGIS geometry - polygon)
├── is_usable (boolean)
└── source (string - "planet_planetscope")
```

---

## Component 2: Change Detection ML Pipeline

### Model Architecture

Siamese U-Net — two identical encoder branches (shared weights) each take one image (before and after). Feature maps are concatenated and passed through a decoder that outputs a pixel-level change mask.

```
Image T-1 ──▶ [Encoder] ──┐
                           ├──▶ [Decoder] ──▶ Change Mask
Image T   ──▶ [Encoder] ──┘
```

### Multi-Interval Comparison Strategy

For each day's image, comparisons run against multiple baselines:

| Interval | Purpose | Sensitivity |
|----------|---------|-------------|
| 1-day | Rapid changes (demolition, large equipment, sudden land clearing) | High threshold — only obvious changes |
| 7-day | Incremental construction progress (foundations, walls) | Medium threshold |
| 15-day | Slow-moving work missed by daily diffs | Lower threshold |
| 30-day | Very gradual changes (excavation, land grading) | Lowest threshold |

- Each interval has its own confidence threshold tuned to expected magnitude of change
- A detection from any interval creates a flag; the triggering interval is recorded for officer context
- Detections from multiple intervals for the same spot are merged, reinforcing confidence
- All comparisons run daily; each compares today's image against the best usable image from N days ago

### Baseline Image Selection

- For each interval, pick the best usable image closest to the target date (e.g., for 7-day, if day-7 had heavy cloud cover, use day-6 or day-8)
- A rolling window of the last 60 days of usable images is maintained (extended beyond 30 days to handle monsoon season gaps)

### Pipeline Steps

1. **Preprocessing** — Geo-registration alignment, pixel value normalization, split into 256x256 patches with overlap
2. **Inference** — Run each patch pair through the model, producing a probability mask (0-1) per pixel
3. **Post-processing** — Threshold probability mask using per-interval thresholds (1-day: 0.85, 7-day: 0.7, 15-day: 0.6, 30-day: 0.5), morphological operations (noise removal, gap filling), merge patches back into full map
4. **Region extraction** — Connected component analysis to identify distinct change regions. Regions below the minimum area threshold (configurable, default: 50 sq meters) are discarded. Each remaining region becomes a detection polygon with centroid, bounding box, area in sq meters, and confidence score
5. **Classification** — Lightweight classification head categorizes each detection as: `excavation`, `foundation`, `new_structure`, `extension`, `land_clearing`. Initially bootstrapped with rule-based heuristics (e.g., area size, shape regularity, proximity to existing structures) until sufficient officer-labeled data accumulates for ML-based classification

### Model Training

- **Bootstrap:** Pre-train on public datasets — LEVIR-CD (637 image pairs) and WHU Building Dataset
- **Fine-tune:** As officers label detections over time, their legal/illegal decisions become training signal
- **Retraining:** Automated monthly, or when 500+ new labeled samples accumulate
- **Versioning:** New models A/B tested against current model on held-out validation set before promotion; rollback if performance degrades

### Compute

- Inference: single mid-range GPU (e.g., NVIDIA T4) sufficient for daily PCMC coverage
- Retraining: same GPU during off-hours or cloud instance

---

## Component 3: Flagging & State Management

### Detection-to-Flag Flow

```
Detection polygon arrives
        │
        ▼
  Overlaps existing spot (>50% IoU)? ──yes──▶ Update existing spot
        │                                      (add detection, bump confidence)
        no
        │
        ▼
  In grace period zone? ──yes──▶ Ignore (legal, <12 months)
        │
        no
        │
        ▼
  Create new flagged spot
```

### Spot State Machine

```
┌──────────┐    officer marks    ┌───────────┐    12 months    ┌────────────────┐
│  FLAGGED  │───────legal───────▶│   LEGAL   │───────pass─────▶│ REVIEW_PENDING │
└──────────┘                     └───────────┘                 └────────────────┘
      │                                                               │
      │ officer marks                                    officer decides:
      │ illegal                                          ├─ re-approve ──▶ LEGAL (reset 12mo)
      ▼                                                  └─ re-flag ────▶ FLAGGED
┌──────────┐    officer marks
│ ILLEGAL  │──────resolved──────▶ RESOLVED
└──────────┘

RESOLVED spots re-enter monitoring: if the ML pipeline detects new change
at a RESOLVED location, a new ConstructionSpot is created (linked to the
old spot via `previous_spot_id` for history). This handles cases where
construction resumes after demolition or a new project starts at the same site.
```

### Spatial Merging

- New detection overlapping an existing spot by >50% (IoU) merges into that spot
- Spot geometry updated to union of all its detections
- Prevents duplicate flags for the same construction site

### Grace Period & Review Prompt

- When marked legal, `grace_period_until` set to `now + 12 months`
- Daily job checks for expired grace periods → transitions to `REVIEW_PENDING`, notifies assigned officer

### Data Models

```
ConstructionSpot
├── id (UUID)
├── geometry (PostGIS polygon — merged outline of all detections)
├── status (FLAGGED / LEGAL / ILLEGAL / RESOLVED / REVIEW_PENDING)
├── first_detected_at (timestamp)
├── last_detected_at (timestamp)
├── grace_period_until (timestamp, nullable)
├── review_prompted_at (timestamp, nullable)
├── confidence_score (float — aggregated from detections)
├── change_type (excavation / foundation / new_structure / extension / land_clearing)
├── reviewed_by (FK to User, nullable)
├── reviewed_at (timestamp, nullable)
├── notes (text, nullable)
├── assigned_to (FK to User, nullable — the reviewer responsible for this spot)
├── previous_spot_id (FK to ConstructionSpot, nullable — links to prior RESOLVED spot at same location)
├── version (integer — incremented on each status change, used for optimistic locking)
└── detections[] (one-to-many)

Detection
├── id (UUID)
├── spot_id (FK to ConstructionSpot)
├── detected_at (timestamp)
├── comparison_interval (1d / 7d / 15d / 30d)
├── confidence (float)
├── image_before_id (FK to SatelliteImage)
├── image_after_id (FK to SatelliteImage)
├── change_mask_path (string — MinIO path)
└── area_sq_meters (float)
```

---

## Component 4: Dashboard API (FastAPI)

### Endpoints

```
Auth
├── POST /auth/login
├── POST /auth/logout
└── GET  /auth/me

Spots
├── GET    /spots                — list with filters (status, date range, change_type, area)
├── GET    /spots/{id}           — detail with all detections, images, history
├── PATCH  /spots/{id}/review    — officer action: mark legal/illegal/resolved
├── GET    /spots/stats          — summary counts by status, trend over time
└── GET    /spots/review-pending — spots needing 12-month re-review

Images
├── GET    /images/{id}/tile     — serve satellite image tiles for map display
└── GET    /images/compare       — before/after pair for a specific spot

Admin
├── GET    /users                — list officers
├── POST   /users                — create officer account
├── PATCH  /users/{id}           — update role/status
├── PATCH  /spots/{id}/assign    — reassign spot to a different reviewer
├── GET    /system/health        — pipeline status, last ingestion, model version, quota usage
└── GET    /zones                — list zones with assigned reviewers

Super Admin
├── GET    /audit/logs           — all officer actions, filterable by officer/action/date
├── GET    /audit/officer-summary — review stats per officer (spots reviewed, legal vs illegal breakdown)
```

### Spot Assignment

- The PCMC area is divided into zones. Each zone is mapped to a reviewer via a `zone` field on the `User` model. When new spots are created, they are auto-assigned to the reviewer whose zone contains the spot's centroid. Admins can reassign spots manually.
- Zone boundaries are stored as PostGIS polygons in a `Zone` table (`id`, `name`, `geometry`, `assigned_reviewer_id`).
- `PATCH /spots/{id}/assign` — admin endpoint to reassign a spot to a different reviewer (listed under Admin endpoints below)

### Review Rules

- When marking a spot as **LEGAL** or **RE_APPROVED**, the `notes` field is **mandatory** (non-empty). The officer must provide justification (e.g., permit number, meeting reference).
- All other actions (mark illegal, mark resolved) accept optional notes.
- **Optimistic locking:** The `PATCH /spots/{id}/review` endpoint requires a `version` field. If the spot's current version doesn't match, the request is rejected (HTTP 409 Conflict), preventing stale writes from concurrent officer actions.

---

## Component 5: React Frontend

### Main View — Interactive Map

- Full PCMC boundary with satellite imagery base layer
- Flagged spots as colored markers/polygons:
  - Red = ILLEGAL
  - Orange = FLAGGED (pending review)
  - Yellow = REVIEW_PENDING (12-month re-review due)
  - Green = LEGAL (faint, toggleable)
  - Grey = RESOLVED (hidden by default, toggleable)
- Click a spot to open detail panel

### Spot Detail Panel

- Before/after satellite image slider (swipe to compare)
- Detection timeline — when first detected, which intervals flagged it
- Change type badge (excavation, foundation, etc.)
- Confidence score
- Action buttons: Mark Legal / Mark Illegal / Mark Resolved
- Mandatory notes field when marking legal
- History log of all actions on this spot

### Dashboard/Stats View

- Total spots by status (pie/bar chart)
- New detections over time (line chart)
- Spots pending review (prominent count)
- 12-month re-reviews due (prominent count)
- Last successful image ingestion timestamp
- Pipeline health indicators

### Super Admin — Officer Activity View

- Officer activity log table: officer name, spot ID, action, notes, timestamp
- Filterable by officer, action type, date range
- Drill into any spot for full review history
- Officer summary dashboard: spots reviewed per officer, legal vs illegal ratio per officer

---

## Auth & Roles

| Role | Capabilities |
|------|-------------|
| Reviewer | View spots, mark legal/illegal/resolved, add notes |
| Admin | All reviewer capabilities + manage reviewer accounts, view system health, configure thresholds |
| Super Admin | All admin capabilities + view all officer activity logs, audit trail with notes, manage admin accounts |

---

## Audit Trail

Every officer action is logged immutably — cannot be edited or deleted.

```
AuditLog
├── id (UUID)
├── officer_id (FK to User)
├── spot_id (FK to ConstructionSpot)
├── action (MARKED_LEGAL / MARKED_ILLEGAL / MARKED_RESOLVED / RE_APPROVED / RE_FLAGGED)
├── notes (text — required for MARKED_LEGAL and RE_APPROVED)
└── created_at (timestamp)
```

---

## Notifications

- In-app notification bell for:
  - New detections assigned to reviewer
  - 12-month reviews due
  - Pipeline failures (admin and super admin only)
- Optional email alerts for the same events

---

## Data Retention

- **Raw satellite images:** Retained for 24 months in MinIO, then archived to cold storage (or deleted if cold storage is not configured)
- **Change masks:** Retained indefinitely (small relative to raw imagery)
- **Database records:** Retained indefinitely (spots, detections, audit logs)
- Expected storage growth: ~50-100 MB/day for raw imagery (~18-36 GB/year), change masks ~5-10 MB/day
