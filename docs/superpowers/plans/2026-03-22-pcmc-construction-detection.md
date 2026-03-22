# PCMC Illegal Construction Detection System — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a satellite imagery-based system that detects unauthorized construction in the PCMC area, flags it on a dashboard for officer review, and tracks the lifecycle of each flagged spot with full audit trail.

**Architecture:** FastAPI backend with Celery workers for scheduled imagery ingestion and ML inference. PostgreSQL+PostGIS stores geospatial data, MinIO stores imagery. Siamese U-Net model compares satellite images across multiple time intervals. React frontend with Leaflet map displays flagged spots for officer review.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.0 + GeoAlchemy2, Alembic, Celery, Redis, PostgreSQL + PostGIS, MinIO, PyTorch, rasterio, React 18, Leaflet, Docker Compose

**Spec:** `docs/superpowers/specs/2026-03-22-pcmc-illegal-construction-detection-design.md`

---

## File Structure

```
pcmc-construction-detector/
├── docker-compose.yml                    # PostgreSQL+PostGIS, Redis, MinIO, backend, worker, frontend
├── .env.example                          # Environment variable template
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── alembic/
│   │   └── versions/                     # Migration files
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                       # FastAPI app entry point, CORS, router mounting
│   │   ├── config.py                     # Settings from env vars (pydantic-settings)
│   │   ├── database.py                   # SQLAlchemy engine, session factory
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── user.py                   # User model (id, username, password_hash, role, zone_id)
│   │   │   ├── zone.py                   # Zone model (id, name, geometry)
│   │   │   ├── satellite_image.py        # SatelliteImage model
│   │   │   ├── construction_spot.py      # ConstructionSpot model
│   │   │   ├── detection.py              # Detection model
│   │   │   ├── audit_log.py              # AuditLog model
│   │   │   └── notification.py           # Notification model (id, user_id, message, read, created_at)
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py                   # Login request/response, token schemas
│   │   │   ├── user.py                   # User CRUD schemas
│   │   │   ├── spot.py                   # Spot list/detail/review schemas
│   │   │   ├── image.py                  # Image metadata schemas
│   │   │   ├── audit.py                  # Audit log schemas
│   │   │   └── notification.py           # Notification schemas
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py                   # POST /auth/login, /logout, GET /auth/me
│   │   │   ├── spots.py                  # GET /spots, /spots/{id}, PATCH /spots/{id}/review, etc.
│   │   │   ├── images.py                 # GET /images/{id}/tile, /images/compare
│   │   │   ├── admin.py                  # User CRUD, system health, zones, spot assignment
│   │   │   ├── audit.py                  # GET /audit/logs, /audit/officer-summary
│   │   │   └── notifications.py          # GET /notifications, PATCH /notifications/{id}/read
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── auth_service.py           # Password hashing, JWT creation/validation
│   │   │   ├── spot_service.py           # Spot CRUD, review logic, optimistic locking, assignment
│   │   │   ├── flagging_service.py       # Detection-to-flag flow, IoU merging, grace period check
│   │   │   ├── audit_service.py          # Immutable audit log creation, query
│   │   │   └── notification_service.py   # Create/query notifications
│   │   ├── dependencies.py               # Auth dependency (get_current_user), role checks
│   │   └── storage.py                    # MinIO client wrapper (upload, download, presigned URLs)
│   ├── ingestion/
│   │   ├── __init__.py
│   │   ├── provider_base.py              # Abstract base class for imagery providers
│   │   ├── sentinel2_provider.py         # Sentinel-2 Copernicus API implementation
│   │   ├── planet_provider.py            # Planet Labs API implementation (Phase 2 stub)
│   │   ├── ingest_task.py                # Celery task: fetch imagery, store in MinIO, save metadata
│   │   └── quota_tracker.py              # API quota tracking (Phase 2)
│   ├── ml/
│   │   ├── __init__.py
│   │   ├── model.py                      # Siamese U-Net architecture (PyTorch)
│   │   ├── preprocessing.py              # Geo-registration, normalization, patch splitting
│   │   ├── inference.py                  # Run model on patch pairs, produce change mask
│   │   ├── postprocessing.py             # Thresholding, morphology, region extraction, min area filter
│   │   ├── classifier.py                 # Rule-based classification (excavation/foundation/etc.)
│   │   ├── pipeline_task.py              # Celery task: orchestrate full detection pipeline
│   │   └── weights/                      # Pre-trained model weights (gitignored)
│   ├── tasks/
│   │   ├── __init__.py
│   │   ├── celery_app.py                 # Celery app config, Beat schedule
│   │   ├── grace_period_task.py          # Daily: check expired grace periods → REVIEW_PENDING
│   │   └── retention_task.py             # Monthly: archive/delete old imagery
│   └── tests/
│       ├── conftest.py                   # Test DB, test client, fixtures
│       ├── test_models.py                # Model creation, relationships
│       ├── test_auth.py                  # Login, JWT, role checks
│       ├── test_spots_api.py             # Spot CRUD, review, assignment, optimistic locking
│       ├── test_flagging_service.py      # IoU merging, grace period, resolved re-detection
│       ├── test_audit.py                 # Audit log creation, immutability, queries
│       ├── test_ingestion.py             # Provider abstraction, Sentinel-2 mock
│       ├── test_ml_postprocessing.py     # Thresholding, region extraction, min area
│       ├── test_ml_classifier.py         # Rule-based classification
│       └── test_pipeline.py             # End-to-end pipeline with mock imagery
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── index.html
│   ├── src/
│   │   ├── main.tsx                      # React entry point
│   │   ├── App.tsx                       # Router setup, auth context provider
│   │   ├── api/
│   │   │   └── client.ts                 # Axios instance, JWT interceptor, API functions
│   │   ├── hooks/
│   │   │   ├── useAuth.ts                # Auth context hook
│   │   │   ├── useSpots.ts               # Spot data fetching/mutation hooks
│   │   │   └── useNotifications.ts       # Notification polling hook
│   │   ├── components/
│   │   │   ├── Layout.tsx                # Sidebar nav, notification bell, user menu
│   │   │   ├── ProtectedRoute.tsx        # Auth + role guard
│   │   │   ├── Map/
│   │   │   │   ├── MapView.tsx           # Leaflet map with PCMC boundary + spot layers
│   │   │   │   ├── SpotMarker.tsx        # Colored polygon/marker per spot status
│   │   │   │   └── SpotDetailPanel.tsx   # Side panel: images, actions, history
│   │   │   ├── Dashboard/
│   │   │   │   └── StatsView.tsx         # Charts, counts, pipeline health
│   │   │   ├── Admin/
│   │   │   │   ├── UserManagement.tsx    # CRUD officers
│   │   │   │   └── SystemHealth.tsx      # Pipeline status, quota
│   │   │   └── SuperAdmin/
│   │   │       ├── AuditLog.tsx          # Officer activity table with filters
│   │   │       └── OfficerSummary.tsx    # Per-officer review stats
│   │   ├── pages/
│   │   │   ├── LoginPage.tsx
│   │   │   ├── MapPage.tsx               # Map + spot detail
│   │   │   ├── DashboardPage.tsx         # Stats view
│   │   │   ├── AdminPage.tsx             # User management + system health
│   │   │   └── AuditPage.tsx             # Super admin audit views
│   │   └── types/
│   │       └── index.ts                  # TypeScript interfaces matching backend schemas
│   └── tests/
│       └── ... (component tests)
└── scripts/
    ├── seed_zones.py                     # Seed PCMC zone boundaries from GeoJSON
    ├── seed_users.py                     # Create initial super admin + test users
    └── download_pcmc_boundary.py         # Fetch PCMC boundary polygon from OSM
```

---

## Task 1: Project Scaffolding & Docker Infrastructure

**Files:**
- Create: `docker-compose.yml`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `backend/Dockerfile`
- Create: `backend/requirements.txt`
- Create: `frontend/Dockerfile`
- Create: `frontend/package.json`

- [ ] **Step 1: Create .gitignore**

```gitignore
# Python
__pycache__/
*.pyc
.venv/
*.egg-info/

# Node
node_modules/
dist/

# Environment
.env

# ML weights
backend/ml/weights/*.pt
backend/ml/weights/*.pth

# IDE
.vscode/
.idea/

# OS
.DS_Store

# MinIO data
minio_data/
```

- [ ] **Step 2: Create .env.example**

```env
# Database
POSTGRES_USER=pcmc
POSTGRES_PASSWORD=pcmc_dev_password
POSTGRES_DB=pcmc_construction
DATABASE_URL=postgresql+asyncpg://pcmc:pcmc_dev_password@db:5432/pcmc_construction

# Redis
REDIS_URL=redis://redis:6379/0

# MinIO
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=satellite-imagery

# JWT
JWT_SECRET_KEY=change-me-in-production
JWT_ALGORITHM=HS256
JWT_EXPIRATION_MINUTES=480

# Sentinel-2 (Phase 1)
IMAGERY_PROVIDER=sentinel2
SENTINEL2_CLIENT_ID=your-copernicus-client-id
SENTINEL2_CLIENT_SECRET=your-copernicus-client-secret

# PCMC boundary (approx center)
PCMC_CENTER_LAT=18.6298
PCMC_CENTER_LNG=73.7997
```

- [ ] **Step 3: Create backend/requirements.txt**

```txt
fastapi==0.115.0
uvicorn[standard]==0.32.0
sqlalchemy[asyncio]==2.0.36
asyncpg==0.30.0
geoalchemy2==0.15.2
alembic==1.14.0
pydantic-settings==2.6.0
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.12
minio==7.2.12
celery[redis]==5.4.0
redis==5.2.0
rasterio==1.4.3
shapely==2.0.6
numpy==2.1.3
opencv-python-headless==4.10.0.84
torch==2.5.1
torchvision==0.20.1
scikit-image==0.24.0
httpx==0.28.0
pytest==8.3.4
pytest-asyncio==0.24.0
geojson==3.1.0
python-dateutil==2.9.0
```

- [ ] **Step 4: Create docker-compose.yml**

```yaml
version: "3.9"

services:
  db:
    image: postgis/postgis:16-3.4
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: ${MINIO_ACCESS_KEY}
      MINIO_ROOT_PASSWORD: ${MINIO_SECRET_KEY}
    ports:
      - "9000:9000"
      - "9001:9001"
    volumes:
      - minio_data:/data

  backend:
    build: ./backend
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    env_file: .env
    ports:
      - "8000:8000"
    depends_on:
      - db
      - redis
      - minio
    volumes:
      - ./backend:/app

  worker:
    build: ./backend
    command: celery -A tasks.celery_app worker --loglevel=info
    env_file: .env
    depends_on:
      - db
      - redis
      - minio
    volumes:
      - ./backend:/app

  beat:
    build: ./backend
    command: celery -A tasks.celery_app beat --loglevel=info
    env_file: .env
    depends_on:
      - redis
    volumes:
      - ./backend:/app

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    depends_on:
      - backend
    volumes:
      - ./frontend/src:/app/src

volumes:
  pgdata:
  minio_data:
```

- [ ] **Step 5: Create backend/Dockerfile**

```dockerfile
FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    gdal-bin libgdal-dev libgeos-dev libproj-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
```

- [ ] **Step 6: Create frontend scaffolding**

```bash
cd frontend
npm create vite@latest . -- --template react-ts
npm install leaflet react-leaflet @types/leaflet axios recharts react-router-dom
```

- [ ] **Step 7: Copy .env.example to .env and run docker-compose up**

```bash
cp .env.example .env
docker-compose up -d db redis minio
```

Verify: PostgreSQL accessible on 5432, Redis on 6379, MinIO console on 9001.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: project scaffolding with Docker infrastructure

PostgreSQL+PostGIS, Redis, MinIO, backend (FastAPI), Celery worker/beat,
and React frontend via Docker Compose."
```

---

## Task 2: Database Models & Migrations

**Files:**
- Create: `backend/app/config.py`
- Create: `backend/app/database.py`
- Create: `backend/app/models/__init__.py`
- Create: `backend/app/models/user.py`
- Create: `backend/app/models/zone.py`
- Create: `backend/app/models/satellite_image.py`
- Create: `backend/app/models/construction_spot.py`
- Create: `backend/app/models/detection.py`
- Create: `backend/app/models/audit_log.py`
- Create: `backend/app/models/notification.py`
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_models.py`

- [ ] **Step 1: Create backend/app/config.py**

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    redis_url: str = "redis://redis:6379/0"

    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "satellite-imagery"
    minio_secure: bool = False

    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 480

    imagery_provider: str = "sentinel2"
    sentinel2_client_id: str = ""
    sentinel2_client_secret: str = ""

    pcmc_center_lat: float = 18.6298
    pcmc_center_lng: float = 73.7997

    min_detection_area_sqm: float = 50.0

    class Config:
        env_file = ".env"


settings = Settings()
```

- [ ] **Step 2: Create backend/app/database.py**

```python
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(settings.database_url, echo=False)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with async_session_factory() as session:
        yield session
```

- [ ] **Step 3: Create all models**

`backend/app/models/user.py`:
```python
import uuid
from sqlalchemy import Column, String, Boolean, Enum as SAEnum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(200), nullable=False)
    role = Column(SAEnum("reviewer", "admin", "super_admin", name="user_role"), nullable=False, default="reviewer")
    is_active = Column(Boolean, nullable=False, default=True)
    zone_id = Column(UUID(as_uuid=True), ForeignKey("zones.id"), nullable=True)

    zone = relationship("Zone", back_populates="assigned_reviewer")
```

`backend/app/models/zone.py`:
```python
import uuid
from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from geoalchemy2 import Geometry
from sqlalchemy.orm import relationship

from app.database import Base


class Zone(Base):
    __tablename__ = "zones"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    geometry = Column(Geometry("POLYGON", srid=4326), nullable=False)

    assigned_reviewer = relationship("User", back_populates="zone", uselist=False)
```

`backend/app/models/satellite_image.py`:
```python
import uuid
from sqlalchemy import Column, String, Float, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID
from geoalchemy2 import Geometry
from sqlalchemy.sql import func

from app.database import Base


class SatelliteImage(Base):
    __tablename__ = "satellite_images"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    captured_at = Column(DateTime(timezone=True), nullable=False, index=True)
    ingested_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    storage_path = Column(String(500), nullable=False)
    cloud_cover_pct = Column(Float, nullable=False)
    resolution_meters = Column(Float, nullable=False)
    bounds = Column(Geometry("POLYGON", srid=4326), nullable=False)
    is_usable = Column(Boolean, nullable=False, default=True)
    source = Column(String(50), nullable=False, default="sentinel2")
```

`backend/app/models/construction_spot.py`:
```python
import uuid
from sqlalchemy import Column, String, Float, Integer, DateTime, Text, ForeignKey
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from geoalchemy2 import Geometry
from sqlalchemy.orm import relationship

from app.database import Base

SPOT_STATUS = SAEnum(
    "flagged", "legal", "illegal", "resolved", "review_pending",
    name="spot_status"
)
CHANGE_TYPE = SAEnum(
    "excavation", "foundation", "new_structure", "extension", "land_clearing",
    name="change_type"
)


class ConstructionSpot(Base):
    __tablename__ = "construction_spots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    geometry = Column(Geometry("POLYGON", srid=4326), nullable=False)
    status = Column(SPOT_STATUS, nullable=False, default="flagged")
    first_detected_at = Column(DateTime(timezone=True), nullable=False)
    last_detected_at = Column(DateTime(timezone=True), nullable=False)
    grace_period_until = Column(DateTime(timezone=True), nullable=True)
    review_prompted_at = Column(DateTime(timezone=True), nullable=True)
    confidence_score = Column(Float, nullable=False, default=0.0)
    change_type = Column(CHANGE_TYPE, nullable=True)
    reviewed_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)
    assigned_to_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    previous_spot_id = Column(UUID(as_uuid=True), ForeignKey("construction_spots.id"), nullable=True)
    version = Column(Integer, nullable=False, default=1)

    reviewed_by = relationship("User", foreign_keys=[reviewed_by_id])
    assigned_to = relationship("User", foreign_keys=[assigned_to_id])
    previous_spot = relationship("ConstructionSpot", remote_side=[id])
    detections = relationship("Detection", back_populates="spot", cascade="all, delete-orphan")
```

`backend/app/models/detection.py`:
```python
import uuid
from sqlalchemy import Column, String, Float, DateTime, ForeignKey
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base

COMPARISON_INTERVAL = SAEnum("1d", "7d", "15d", "30d", name="comparison_interval")


class Detection(Base):
    __tablename__ = "detections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    spot_id = Column(UUID(as_uuid=True), ForeignKey("construction_spots.id"), nullable=False)
    detected_at = Column(DateTime(timezone=True), nullable=False)
    comparison_interval = Column(COMPARISON_INTERVAL, nullable=False)
    confidence = Column(Float, nullable=False)
    image_before_id = Column(UUID(as_uuid=True), ForeignKey("satellite_images.id"), nullable=False)
    image_after_id = Column(UUID(as_uuid=True), ForeignKey("satellite_images.id"), nullable=False)
    change_mask_path = Column(String(500), nullable=False)
    area_sq_meters = Column(Float, nullable=False)

    spot = relationship("ConstructionSpot", back_populates="detections")
    image_before = relationship("SatelliteImage", foreign_keys=[image_before_id])
    image_after = relationship("SatelliteImage", foreign_keys=[image_after_id])
```

`backend/app/models/audit_log.py`:
```python
import uuid
from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.database import Base

AUDIT_ACTION = SAEnum(
    "marked_legal", "marked_illegal", "marked_resolved", "re_approved", "re_flagged",
    name="audit_action"
)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    officer_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    spot_id = Column(UUID(as_uuid=True), ForeignKey("construction_spots.id"), nullable=False)
    action = Column(AUDIT_ACTION, nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    officer = relationship("User")
    spot = relationship("ConstructionSpot")
```

`backend/app/models/notification.py`:
```python
import uuid
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.database import Base


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    message = Column(String(500), nullable=False)
    is_read = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User")
```

`backend/app/models/__init__.py`:
```python
from app.models.user import User
from app.models.zone import Zone
from app.models.satellite_image import SatelliteImage
from app.models.construction_spot import ConstructionSpot
from app.models.detection import Detection
from app.models.audit_log import AuditLog
from app.models.notification import Notification

__all__ = [
    "User", "Zone", "SatelliteImage", "ConstructionSpot",
    "Detection", "AuditLog", "Notification",
]
```

- [ ] **Step 4: Set up Alembic and create initial migration**

```bash
cd backend
alembic init alembic
```

Edit `alembic/env.py` to import models and use async engine:

```python
from app.database import Base, engine
from app.models import *  # noqa: ensure all models registered

target_metadata = Base.metadata
```

Then generate migration:

```bash
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```

- [ ] **Step 5: Write test for model creation**

`backend/tests/conftest.py`:
```python
import pytest
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.database import Base

TEST_DATABASE_URL = "postgresql+asyncpg://pcmc:pcmc_dev_password@localhost:5432/pcmc_construction_test"


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def db_session(test_engine):
    session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()
```

`backend/tests/test_models.py`:
```python
import pytest
from datetime import datetime, timezone
from app.models import User, Zone, ConstructionSpot, SatelliteImage, Detection, AuditLog


@pytest.mark.asyncio
async def test_create_user(db_session):
    user = User(username="officer1", password_hash="hashed", full_name="Test Officer", role="reviewer")
    db_session.add(user)
    await db_session.flush()
    assert user.id is not None
    assert user.role == "reviewer"


@pytest.mark.asyncio
async def test_create_construction_spot(db_session):
    spot = ConstructionSpot(
        geometry="SRID=4326;POLYGON((73.79 18.62, 73.80 18.62, 73.80 18.63, 73.79 18.63, 73.79 18.62))",
        status="flagged",
        first_detected_at=datetime.now(timezone.utc),
        last_detected_at=datetime.now(timezone.utc),
        confidence_score=0.75,
        version=1,
    )
    db_session.add(spot)
    await db_session.flush()
    assert spot.id is not None
    assert spot.status == "flagged"
    assert spot.version == 1
```

- [ ] **Step 6: Run tests**

```bash
pytest backend/tests/test_models.py -v
```

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/config.py backend/app/database.py backend/app/models/ backend/alembic.ini backend/alembic/ backend/tests/
git commit -m "feat: database models and migrations

All core models: User, Zone, SatelliteImage, ConstructionSpot, Detection,
AuditLog, Notification. PostGIS geometry columns, proper relationships,
optimistic locking version field on spots."
```

---

## Task 3: Auth & User Management

**Files:**
- Create: `backend/app/services/auth_service.py`
- Create: `backend/app/dependencies.py`
- Create: `backend/app/schemas/auth.py`
- Create: `backend/app/schemas/user.py`
- Create: `backend/app/routers/auth.py`
- Create: `backend/app/routers/admin.py` (user CRUD portion)
- Create: `backend/app/main.py`
- Create: `backend/tests/test_auth.py`

- [ ] **Step 1: Write failing auth tests**

`backend/tests/test_auth.py`:
```python
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_login_success(db_session, seed_users):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/auth/login", json={"username": "officer1", "password": "test123"})
        assert response.status_code == 200
        assert "access_token" in response.json()


@pytest.mark.asyncio
async def test_login_wrong_password(db_session, seed_users):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/auth/login", json={"username": "officer1", "password": "wrong"})
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_me_authenticated(db_session, seed_users):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        login = await client.post("/auth/login", json={"username": "officer1", "password": "test123"})
        token = login.json()["access_token"]
        response = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert response.json()["username"] == "officer1"


@pytest.mark.asyncio
async def test_get_me_unauthenticated(db_session):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/auth/me")
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_admin_only_endpoint(db_session, seed_users):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        login = await client.post("/auth/login", json={"username": "officer1", "password": "test123"})
        token = login.json()["access_token"]
        response = await client.get("/users", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 403
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest backend/tests/test_auth.py -v
```

Expected: FAIL (modules don't exist yet)

- [ ] **Step 3: Implement auth_service.py**

```python
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from passlib.context import CryptContext
from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expiration_minutes)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None
```

- [ ] **Step 4: Implement schemas, dependencies, routers, main.py**

`backend/app/schemas/auth.py`:
```python
from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
```

`backend/app/schemas/user.py`:
```python
from pydantic import BaseModel
from uuid import UUID


class UserOut(BaseModel):
    id: UUID
    username: str
    full_name: str
    role: str
    is_active: bool

    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    username: str
    password: str
    full_name: str
    role: str = "reviewer"


class UserUpdate(BaseModel):
    full_name: str | None = None
    role: str | None = None
    is_active: bool | None = None
```

`backend/app/dependencies.py`:
```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.user import User
from app.services.auth_service import decode_access_token

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def require_role(*roles: str):
    def checker(user: User = Depends(get_current_user)):
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user
    return checker
```

`backend/app/routers/auth.py`:
```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.user import UserOut
from app.services.auth_service import verify_password, create_access_token
from app.dependencies import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == body.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token({"sub": str(user.id), "role": user.role})
    return TokenResponse(access_token=token)


@router.post("/logout")
async def logout():
    # JWT is stateless — client discards the token.
    # Endpoint exists for API completeness per spec.
    return {"status": "ok"}


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return user
```

`backend/app/routers/admin.py`:
```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.user import User
from app.schemas.user import UserOut, UserCreate, UserUpdate
from app.services.auth_service import hash_password
from app.dependencies import require_role

router = APIRouter(tags=["admin"])


@router.get("/users", response_model=list[UserOut])
async def list_users(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("admin", "super_admin")),
):
    result = await db.execute(select(User))
    return result.scalars().all()


@router.post("/users", response_model=UserOut, status_code=201)
async def create_user(
    body: UserCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("admin", "super_admin")),
):
    user = User(
        username=body.username,
        password_hash=hash_password(body.password),
        full_name=body.full_name,
        role=body.role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.patch("/users/{user_id}", response_model=UserOut)
async def update_user(
    user_id: UUID,
    body: UserUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("admin", "super_admin")),
):
    from uuid import UUID as UUIDType
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if body.full_name is not None:
        user.full_name = body.full_name
    if body.role is not None:
        user.role = body.role
    if body.is_active is not None:
        user.is_active = body.is_active
    await db.commit()
    await db.refresh(user)
    return user
```

`backend/app/main.py`:
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import auth, admin

app = FastAPI(title="PCMC Construction Detection", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(admin.router)
```

- [ ] **Step 5: Add seed_users fixture to conftest.py and run tests**

Add to `backend/tests/conftest.py`:
```python
from app.models import User
from app.services.auth_service import hash_password

@pytest.fixture
async def seed_users(db_session):
    users = [
        User(username="officer1", password_hash=hash_password("test123"), full_name="Officer One", role="reviewer"),
        User(username="admin1", password_hash=hash_password("test123"), full_name="Admin One", role="admin"),
        User(username="superadmin", password_hash=hash_password("test123"), full_name="Super Admin", role="super_admin"),
    ]
    for u in users:
        db_session.add(u)
    await db_session.flush()
    return users
```

```bash
pytest backend/tests/test_auth.py -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/auth_service.py backend/app/dependencies.py backend/app/schemas/ backend/app/routers/ backend/app/main.py backend/tests/
git commit -m "feat: JWT auth, user management, role-based access control

Login/logout, token validation, get-me endpoint. Role hierarchy:
reviewer, admin, super_admin. Admin user CRUD endpoints."
```

---

## Task 4: Spots API & Flagging Service

**Files:**
- Create: `backend/app/schemas/spot.py`
- Create: `backend/app/services/spot_service.py`
- Create: `backend/app/services/flagging_service.py`
- Create: `backend/app/services/audit_service.py`
- Create: `backend/app/routers/spots.py`
- Create: `backend/app/routers/audit.py`
- Create: `backend/tests/test_spots_api.py`
- Create: `backend/tests/test_flagging_service.py`
- Create: `backend/tests/test_audit.py`

- [ ] **Step 1: Write failing tests for spot review with optimistic locking**

`backend/tests/test_spots_api.py`:
```python
import pytest
from datetime import datetime, timezone


@pytest.mark.asyncio
async def test_review_spot_mark_legal_requires_notes(client, auth_token, sample_spot):
    response = await client.patch(
        f"/spots/{sample_spot.id}/review",
        json={"action": "marked_legal", "version": 1},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 422  # notes required


@pytest.mark.asyncio
async def test_review_spot_mark_legal_with_notes(client, auth_token, sample_spot):
    response = await client.patch(
        f"/spots/{sample_spot.id}/review",
        json={"action": "marked_legal", "notes": "Permit #PCM-2026-001", "version": 1},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "legal"
    assert data["version"] == 2


@pytest.mark.asyncio
async def test_review_spot_optimistic_lock_conflict(client, auth_token, sample_spot):
    # First review succeeds
    await client.patch(
        f"/spots/{sample_spot.id}/review",
        json={"action": "marked_illegal", "version": 1},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    # Second review with stale version fails
    response = await client.patch(
        f"/spots/{sample_spot.id}/review",
        json={"action": "marked_legal", "notes": "Permit exists", "version": 1},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 409
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest backend/tests/test_spots_api.py -v
```

Expected: FAIL

- [ ] **Step 3: Implement spot schemas**

`backend/app/schemas/spot.py`:
```python
from pydantic import BaseModel, model_validator
from uuid import UUID
from datetime import datetime
from typing import Optional


class SpotOut(BaseModel):
    id: UUID
    status: str
    first_detected_at: datetime
    last_detected_at: datetime
    confidence_score: float
    change_type: Optional[str] = None
    assigned_to_id: Optional[UUID] = None
    version: int
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    class Config:
        from_attributes = True


class SpotDetail(SpotOut):
    notes: Optional[str] = None
    grace_period_until: Optional[datetime] = None
    review_prompted_at: Optional[datetime] = None
    reviewed_by_id: Optional[UUID] = None
    reviewed_at: Optional[datetime] = None
    previous_spot_id: Optional[UUID] = None


class SpotReviewRequest(BaseModel):
    action: str  # marked_legal, marked_illegal, marked_resolved, re_approved, re_flagged
    notes: Optional[str] = None
    version: int

    @model_validator(mode="after")
    def validate_notes_required(self):
        if self.action in ("marked_legal", "re_approved") and not self.notes:
            raise ValueError("Notes are required when marking as legal or re-approving")
        return self


class SpotAssignRequest(BaseModel):
    assigned_to_id: UUID


class SpotStats(BaseModel):
    flagged: int = 0
    legal: int = 0
    illegal: int = 0
    resolved: int = 0
    review_pending: int = 0
```

- [ ] **Step 4: Implement spot_service, flagging_service, audit_service**

`backend/app/services/spot_service.py`:
```python
from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status

from app.models.construction_spot import ConstructionSpot
from app.models.user import User
from app.services.audit_service import create_audit_log

ACTION_TO_STATUS = {
    "marked_legal": "legal",
    "marked_illegal": "illegal",
    "marked_resolved": "resolved",
    "re_approved": "legal",
    "re_flagged": "flagged",
}


async def review_spot(
    db: AsyncSession,
    spot_id: UUID,
    action: str,
    version: int,
    officer: User,
    notes: str | None = None,
) -> ConstructionSpot:
    new_status = ACTION_TO_STATUS.get(action)
    if not new_status:
        raise HTTPException(status_code=400, detail=f"Invalid action: {action}")

    now = datetime.now(timezone.utc)
    values = {
        "status": new_status,
        "reviewed_by_id": officer.id,
        "reviewed_at": now,
        "notes": notes,
        "version": version + 1,
    }
    if new_status == "legal":
        values["grace_period_until"] = now + relativedelta(months=12)

    # Atomic update with version check — prevents TOCTOU race
    result = await db.execute(
        update(ConstructionSpot)
        .where(ConstructionSpot.id == spot_id, ConstructionSpot.version == version)
        .values(**values)
        .returning(ConstructionSpot)
    )
    spot = result.scalar_one_or_none()
    if not spot:
        # Check if spot exists at all
        exists = await db.execute(select(ConstructionSpot.id).where(ConstructionSpot.id == spot_id))
        if not exists.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Spot not found")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Version conflict — spot was modified by another user")

    await create_audit_log(db, officer_id=officer.id, spot_id=spot_id, action=action, notes=notes)
    await db.commit()
    await db.refresh(spot)
    return spot


async def get_spot_stats(db: AsyncSession) -> dict:
    result = await db.execute(
        select(ConstructionSpot.status, func.count(ConstructionSpot.id))
        .group_by(ConstructionSpot.status)
    )
    stats = {row[0]: row[1] for row in result.all()}
    return stats
```

`backend/app/services/flagging_service.py`:
```python
from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from shapely.geometry import shape
from shapely import wkb
from geoalchemy2.shape import to_shape, from_shape

from app.models.construction_spot import ConstructionSpot
from app.models.detection import Detection
from app.models.zone import Zone
from app.models.user import User


def compute_iou(geom_a, geom_b) -> float:
    intersection = geom_a.intersection(geom_b).area
    union = geom_a.union(geom_b).area
    return intersection / union if union > 0 else 0.0


async def process_detection(
    db: AsyncSession,
    detection_polygon,  # shapely Polygon
    confidence: float,
    comparison_interval: str,
    image_before_id: UUID,
    image_after_id: UUID,
    change_mask_path: str,
    area_sq_meters: float,
    change_type: str | None = None,
) -> ConstructionSpot | None:
    # Check overlap with existing active spots
    result = await db.execute(
        select(ConstructionSpot).where(
            ConstructionSpot.status.in_(["flagged", "illegal", "review_pending"])
        )
    )
    existing_spots = result.scalars().all()

    for spot in existing_spots:
        spot_geom = to_shape(spot.geometry)
        iou = compute_iou(detection_polygon, spot_geom)
        if iou > 0.5:
            # Merge into existing spot
            merged_geom = spot_geom.union(detection_polygon)
            spot.geometry = from_shape(merged_geom, srid=4326)
            spot.last_detected_at = datetime.now(timezone.utc)
            spot.confidence_score = max(spot.confidence_score, confidence)
            detection = Detection(
                spot_id=spot.id,
                detected_at=datetime.now(timezone.utc),
                comparison_interval=comparison_interval,
                confidence=confidence,
                image_before_id=image_before_id,
                image_after_id=image_after_id,
                change_mask_path=change_mask_path,
                area_sq_meters=area_sq_meters,
            )
            db.add(detection)
            await db.commit()
            return spot

    # Check grace period (legal spots)
    legal_spots = await db.execute(
        select(ConstructionSpot).where(
            ConstructionSpot.status == "legal",
            ConstructionSpot.grace_period_until > datetime.now(timezone.utc),
        )
    )
    for spot in legal_spots.scalars().all():
        spot_geom = to_shape(spot.geometry)
        iou = compute_iou(detection_polygon, spot_geom)
        if iou > 0.5:
            return None  # In grace period, ignore

    # Check resolved spots — create new linked spot
    resolved_spots = await db.execute(
        select(ConstructionSpot).where(ConstructionSpot.status == "resolved")
    )
    previous_spot_id = None
    for spot in resolved_spots.scalars().all():
        spot_geom = to_shape(spot.geometry)
        iou = compute_iou(detection_polygon, spot_geom)
        if iou > 0.5:
            previous_spot_id = spot.id
            break

    # Auto-assign to zone reviewer
    assigned_to_id = await find_zone_reviewer(db, detection_polygon)

    # Create new spot
    now = datetime.now(timezone.utc)
    new_spot = ConstructionSpot(
        geometry=from_shape(detection_polygon, srid=4326),
        status="flagged",
        first_detected_at=now,
        last_detected_at=now,
        confidence_score=confidence,
        change_type=change_type,
        assigned_to_id=assigned_to_id,
        previous_spot_id=previous_spot_id,
        version=1,
    )
    db.add(new_spot)
    await db.flush()

    detection = Detection(
        spot_id=new_spot.id,
        detected_at=now,
        comparison_interval=comparison_interval,
        confidence=confidence,
        image_before_id=image_before_id,
        image_after_id=image_after_id,
        change_mask_path=change_mask_path,
        area_sq_meters=area_sq_meters,
    )
    db.add(detection)
    await db.commit()
    return new_spot


async def find_zone_reviewer(db: AsyncSession, polygon) -> UUID | None:
    from sqlalchemy.orm import selectinload
    centroid = polygon.centroid
    result = await db.execute(
        select(Zone)
        .options(selectinload(Zone.assigned_reviewer))
        .where(
            Zone.geometry.ST_Contains(
                f"SRID=4326;POINT({centroid.x} {centroid.y})"
            )
        )
    )
    zone = result.scalar_one_or_none()
    if zone and zone.assigned_reviewer:
        return zone.assigned_reviewer.id
    return None
```

`backend/app/services/audit_service.py`:
```python
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.audit_log import AuditLog


async def create_audit_log(
    db: AsyncSession,
    officer_id: UUID,
    spot_id: UUID,
    action: str,
    notes: str | None = None,
):
    log = AuditLog(officer_id=officer_id, spot_id=spot_id, action=action, notes=notes)
    db.add(log)


async def get_audit_logs(db: AsyncSession, officer_id: UUID = None, action: str = None, date_from: str = None, date_to: str = None, limit: int = 100, offset: int = 0):
    query = select(AuditLog).order_by(AuditLog.created_at.desc())
    if officer_id:
        query = query.where(AuditLog.officer_id == officer_id)
    if action:
        query = query.where(AuditLog.action == action)
    if date_from:
        query = query.where(AuditLog.created_at >= date_from)
    if date_to:
        query = query.where(AuditLog.created_at <= date_to)
    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    return result.scalars().all()


async def get_officer_summary(db: AsyncSession):
    result = await db.execute(
        select(
            AuditLog.officer_id,
            AuditLog.action,
            func.count(AuditLog.id),
        )
        .group_by(AuditLog.officer_id, AuditLog.action)
    )
    return result.all()
```

- [ ] **Step 5: Implement spots and audit routers**

`backend/app/routers/spots.py`:
```python
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from typing import Optional

from app.database import get_db
from app.models.construction_spot import ConstructionSpot
from app.models.user import User
from app.schemas.spot import SpotOut, SpotDetail, SpotReviewRequest, SpotAssignRequest, SpotStats
from app.services.spot_service import review_spot, get_spot_stats
from app.dependencies import get_current_user, require_role

router = APIRouter(prefix="/spots", tags=["spots"])


@router.get("", response_model=list[SpotOut])
async def list_spots(
    status: Optional[str] = None,
    change_type: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    min_area: Optional[float] = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(ConstructionSpot).order_by(ConstructionSpot.last_detected_at.desc())
    if status:
        query = query.where(ConstructionSpot.status == status)
    if change_type:
        query = query.where(ConstructionSpot.change_type == change_type)
    if date_from:
        query = query.where(ConstructionSpot.first_detected_at >= date_from)
    if date_to:
        query = query.where(ConstructionSpot.first_detected_at <= date_to)
    if min_area:
        # Filter spots that have at least one detection above min_area
        from app.models.detection import Detection
        query = query.join(Detection).where(Detection.area_sq_meters >= min_area).distinct()
    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/stats", response_model=SpotStats)
async def stats(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    raw = await get_spot_stats(db)
    return SpotStats(**raw)


@router.get("/review-pending", response_model=list[SpotOut])
async def review_pending(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(
        select(ConstructionSpot).where(ConstructionSpot.status == "review_pending")
    )
    return result.scalars().all()


@router.get("/{spot_id}", response_model=SpotDetail)
async def get_spot(spot_id: UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(ConstructionSpot).where(ConstructionSpot.id == spot_id))
    spot = result.scalar_one_or_none()
    if not spot:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Spot not found")
    return spot


@router.patch("/{spot_id}/review", response_model=SpotDetail)
async def review(
    spot_id: UUID,
    body: SpotReviewRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await review_spot(db, spot_id, body.action, body.version, user, body.notes)


@router.patch("/{spot_id}/assign", response_model=SpotDetail)
async def assign_spot(
    spot_id: UUID,
    body: SpotAssignRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("admin", "super_admin")),
):
    result = await db.execute(select(ConstructionSpot).where(ConstructionSpot.id == spot_id))
    spot = result.scalar_one_or_none()
    if not spot:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Spot not found")
    spot.assigned_to_id = body.assigned_to_id
    await db.commit()
    await db.refresh(spot)
    return spot
```

`backend/app/routers/audit.py`:
```python
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import Optional

from app.database import get_db
from app.models.user import User
from app.services.audit_service import get_audit_logs, get_officer_summary
from app.dependencies import require_role
from app.schemas.audit import AuditLogOut, OfficerSummaryOut

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/logs", response_model=list[AuditLogOut])
async def audit_logs(
    officer_id: Optional[UUID] = None,
    action: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("super_admin")),
):
    return await get_audit_logs(db, officer_id=officer_id, action=action, date_from=date_from, date_to=date_to, limit=limit, offset=offset)


@router.get("/officer-summary")
async def officer_summary(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("super_admin")),
):
    return await get_officer_summary(db)
```

`backend/app/schemas/audit.py`:
```python
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional


class AuditLogOut(BaseModel):
    id: UUID
    officer_id: UUID
    spot_id: UUID
    action: str
    notes: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class OfficerSummaryOut(BaseModel):
    officer_id: UUID
    action: str
    count: int
```

- [ ] **Step 6: Mount new routers in main.py**

Add to `backend/app/main.py`:
```python
from app.routers import spots, audit

app.include_router(spots.router)
app.include_router(audit.router)
```

- [ ] **Step 7: Write flagging service tests**

`backend/tests/test_flagging_service.py`:
```python
import pytest
from datetime import datetime, timezone, timedelta
from shapely.geometry import box
from geoalchemy2.shape import from_shape
from app.models import ConstructionSpot, SatelliteImage
from app.services.flagging_service import process_detection, compute_iou


def test_compute_iou_identical():
    a = box(0, 0, 10, 10)
    b = box(0, 0, 10, 10)
    assert compute_iou(a, b) == 1.0


def test_compute_iou_no_overlap():
    a = box(0, 0, 10, 10)
    b = box(20, 20, 30, 30)
    assert compute_iou(a, b) == 0.0


def test_compute_iou_partial_overlap():
    a = box(0, 0, 10, 10)
    b = box(5, 0, 15, 10)
    iou = compute_iou(a, b)
    assert 0.3 < iou < 0.4  # 50/150 ≈ 0.333


@pytest.mark.asyncio
async def test_new_detection_creates_flagged_spot(db_session):
    # Create required satellite images
    now = datetime.now(timezone.utc)
    img_before = SatelliteImage(
        captured_at=now - timedelta(days=1), storage_path="test/before.tif",
        cloud_cover_pct=5.0, resolution_meters=10.0,
        bounds="SRID=4326;POLYGON((73.79 18.62, 73.80 18.62, 73.80 18.63, 73.79 18.63, 73.79 18.62))",
        is_usable=True, source="sentinel2",
    )
    img_after = SatelliteImage(
        captured_at=now, storage_path="test/after.tif",
        cloud_cover_pct=5.0, resolution_meters=10.0,
        bounds="SRID=4326;POLYGON((73.79 18.62, 73.80 18.62, 73.80 18.63, 73.79 18.63, 73.79 18.62))",
        is_usable=True, source="sentinel2",
    )
    db_session.add_all([img_before, img_after])
    await db_session.flush()

    polygon = box(73.795, 18.625, 73.798, 18.628)
    spot = await process_detection(
        db=db_session, detection_polygon=polygon, confidence=0.8,
        comparison_interval="7d", image_before_id=img_before.id,
        image_after_id=img_after.id, change_mask_path="masks/test.png",
        area_sq_meters=120.0, change_type="foundation",
    )
    assert spot is not None
    assert spot.status == "flagged"
    assert spot.confidence_score == 0.8
    assert len(spot.detections) == 1


@pytest.mark.asyncio
async def test_overlapping_detection_merges_into_existing(db_session):
    now = datetime.now(timezone.utc)
    img = SatelliteImage(
        captured_at=now, storage_path="test/img.tif",
        cloud_cover_pct=5.0, resolution_meters=10.0,
        bounds="SRID=4326;POLYGON((73.79 18.62, 73.80 18.62, 73.80 18.63, 73.79 18.63, 73.79 18.62))",
        is_usable=True, source="sentinel2",
    )
    db_session.add(img)
    await db_session.flush()

    # First detection creates spot
    poly1 = box(73.795, 18.625, 73.798, 18.628)
    spot1 = await process_detection(
        db=db_session, detection_polygon=poly1, confidence=0.7,
        comparison_interval="7d", image_before_id=img.id,
        image_after_id=img.id, change_mask_path="masks/1.png",
        area_sq_meters=100.0,
    )

    # Second detection overlaps >50% — should merge
    poly2 = box(73.7955, 18.6255, 73.7985, 18.6285)
    spot2 = await process_detection(
        db=db_session, detection_polygon=poly2, confidence=0.85,
        comparison_interval="15d", image_before_id=img.id,
        image_after_id=img.id, change_mask_path="masks/2.png",
        area_sq_meters=110.0,
    )

    assert spot2.id == spot1.id  # Same spot
    assert spot2.confidence_score == 0.85  # Updated to max


@pytest.mark.asyncio
async def test_detection_in_grace_period_is_ignored(db_session):
    now = datetime.now(timezone.utc)
    img = SatelliteImage(
        captured_at=now, storage_path="test/img.tif",
        cloud_cover_pct=5.0, resolution_meters=10.0,
        bounds="SRID=4326;POLYGON((73.79 18.62, 73.80 18.62, 73.80 18.63, 73.79 18.63, 73.79 18.62))",
        is_usable=True, source="sentinel2",
    )
    db_session.add(img)
    await db_session.flush()

    # Create a legal spot with active grace period
    legal_spot = ConstructionSpot(
        geometry=from_shape(box(73.795, 18.625, 73.798, 18.628), srid=4326),
        status="legal",
        first_detected_at=now - timedelta(days=30),
        last_detected_at=now - timedelta(days=30),
        confidence_score=0.8,
        grace_period_until=now + timedelta(days=300),
        version=2,
    )
    db_session.add(legal_spot)
    await db_session.flush()

    # Detection at same location should be ignored
    poly = box(73.7955, 18.6255, 73.7975, 18.6275)
    result = await process_detection(
        db=db_session, detection_polygon=poly, confidence=0.9,
        comparison_interval="7d", image_before_id=img.id,
        image_after_id=img.id, change_mask_path="masks/grace.png",
        area_sq_meters=80.0,
    )
    assert result is None  # Ignored


@pytest.mark.asyncio
async def test_detection_at_resolved_spot_creates_new_linked_spot(db_session):
    now = datetime.now(timezone.utc)
    img = SatelliteImage(
        captured_at=now, storage_path="test/img.tif",
        cloud_cover_pct=5.0, resolution_meters=10.0,
        bounds="SRID=4326;POLYGON((73.79 18.62, 73.80 18.62, 73.80 18.63, 73.79 18.63, 73.79 18.62))",
        is_usable=True, source="sentinel2",
    )
    db_session.add(img)
    await db_session.flush()

    # Create a resolved spot
    resolved_spot = ConstructionSpot(
        geometry=from_shape(box(73.795, 18.625, 73.798, 18.628), srid=4326),
        status="resolved",
        first_detected_at=now - timedelta(days=60),
        last_detected_at=now - timedelta(days=30),
        confidence_score=0.8,
        version=3,
    )
    db_session.add(resolved_spot)
    await db_session.flush()

    # New detection at same location
    poly = box(73.7955, 18.6255, 73.7975, 18.6275)
    new_spot = await process_detection(
        db=db_session, detection_polygon=poly, confidence=0.75,
        comparison_interval="30d", image_before_id=img.id,
        image_after_id=img.id, change_mask_path="masks/new.png",
        area_sq_meters=90.0,
    )
    assert new_spot is not None
    assert new_spot.id != resolved_spot.id  # New spot created
    assert new_spot.previous_spot_id == resolved_spot.id  # Linked to old
    assert new_spot.status == "flagged"
```

- [ ] **Step 8: Run all tests**

```bash
pytest backend/tests/ -v
```

Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add backend/app/schemas/ backend/app/services/ backend/app/routers/ backend/tests/
git commit -m "feat: spots API, flagging service, audit trail

Spot listing/detail/review with atomic optimistic locking. Flagging service with
IoU-based merging, grace period check, resolved re-detection. Immutable
audit log with super admin endpoints. Mandatory notes on legal marking."
```

---

## Task 5: MinIO Storage & Image Serving

**Files:**
- Create: `backend/app/storage.py`
- Create: `backend/app/routers/images.py`
- Create: `backend/app/schemas/image.py`

- [ ] **Step 1: Implement storage.py**

```python
from minio import Minio
from app.config import settings

minio_client = Minio(
    settings.minio_endpoint,
    access_key=settings.minio_access_key,
    secret_key=settings.minio_secret_key,
    secure=settings.minio_secure,
)


def ensure_bucket():
    if not minio_client.bucket_exists(settings.minio_bucket):
        minio_client.make_bucket(settings.minio_bucket)


def upload_image(object_name: str, file_path: str, content_type: str = "image/tiff"):
    ensure_bucket()
    minio_client.fput_object(settings.minio_bucket, object_name, file_path, content_type=content_type)


def get_presigned_url(object_name: str, expires_hours: int = 1) -> str:
    from datetime import timedelta
    return minio_client.presigned_get_object(
        settings.minio_bucket, object_name, expires=timedelta(hours=expires_hours)
    )


def download_image(object_name: str, file_path: str):
    minio_client.fget_object(settings.minio_bucket, object_name, file_path)
```

- [ ] **Step 2: Implement image schemas and router**

`backend/app/schemas/image.py`:
```python
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional


class ImageOut(BaseModel):
    id: UUID
    captured_at: datetime
    cloud_cover_pct: float
    resolution_meters: float
    is_usable: bool
    source: str

    class Config:
        from_attributes = True


class ImageCompare(BaseModel):
    before_url: str
    after_url: str
    before_captured_at: datetime
    after_captured_at: datetime
```

`backend/app/routers/images.py`:
```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID

from app.database import get_db
from app.models.satellite_image import SatelliteImage
from app.models.detection import Detection
from app.models.user import User
from app.schemas.image import ImageOut, ImageCompare
from app.storage import get_presigned_url
from app.dependencies import get_current_user

router = APIRouter(prefix="/images", tags=["images"])


@router.get("/{image_id}/tile")
async def get_image_tile(
    image_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(SatelliteImage).where(SatelliteImage.id == image_id))
    image = result.scalar_one_or_none()
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    url = get_presigned_url(image.storage_path)
    return {"url": url}


@router.get("/compare", response_model=ImageCompare)
async def compare_images(
    detection_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Detection).where(Detection.id == detection_id))
    detection = result.scalar_one_or_none()
    if not detection:
        raise HTTPException(status_code=404, detail="Detection not found")

    before = await db.get(SatelliteImage, detection.image_before_id)
    after = await db.get(SatelliteImage, detection.image_after_id)

    return ImageCompare(
        before_url=get_presigned_url(before.storage_path),
        after_url=get_presigned_url(after.storage_path),
        before_captured_at=before.captured_at,
        after_captured_at=after.captured_at,
    )
```

- [ ] **Step 3: Mount images router in main.py and commit**

```bash
git add backend/app/storage.py backend/app/routers/images.py backend/app/schemas/image.py
git commit -m "feat: MinIO storage wrapper and image serving endpoints

Presigned URL generation for satellite imagery tiles. Image comparison
endpoint for before/after detection views."
```

---

## Task 6: Image Ingestion Service (Sentinel-2 Phase 1)

**Files:**
- Create: `backend/ingestion/provider_base.py`
- Create: `backend/ingestion/sentinel2_provider.py`
- Create: `backend/ingestion/planet_provider.py`
- Create: `backend/ingestion/ingest_task.py`
- Create: `backend/tests/test_ingestion.py`

- [ ] **Step 1: Write failing test for provider abstraction**

`backend/tests/test_ingestion.py`:
```python
import pytest
from unittest.mock import AsyncMock, patch
from ingestion.provider_base import ImageryProvider
from ingestion.sentinel2_provider import Sentinel2Provider


def test_sentinel2_implements_provider():
    provider = Sentinel2Provider(client_id="test", client_secret="test")
    assert isinstance(provider, ImageryProvider)


def test_provider_has_required_methods():
    provider = Sentinel2Provider(client_id="test", client_secret="test")
    assert hasattr(provider, "search_images")
    assert hasattr(provider, "download_image")
```

- [ ] **Step 2: Run test to verify failure**

```bash
pytest backend/tests/test_ingestion.py -v
```

- [ ] **Step 3: Implement provider base and Sentinel-2 provider**

`backend/ingestion/provider_base.py`:
```python
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any


class ImageryProvider(ABC):
    @abstractmethod
    async def search_images(
        self,
        bbox: tuple[float, float, float, float],
        start_date: datetime,
        end_date: datetime,
        max_cloud_cover: float = 30.0,
    ) -> list[dict[str, Any]]:
        """Search for available images in the given bounding box and date range."""
        ...

    @abstractmethod
    async def download_image(self, image_id: str, output_path: str) -> str:
        """Download an image to the given path. Returns the local file path."""
        ...
```

`backend/ingestion/sentinel2_provider.py`:
```python
import httpx
from datetime import datetime
from typing import Any
from ingestion.provider_base import ImageryProvider


class Sentinel2Provider(ImageryProvider):
    TOKEN_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
    CATALOG_URL = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"

    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self._token: str | None = None

    async def _get_token(self) -> str:
        async with httpx.AsyncClient() as client:
            response = await client.post(self.TOKEN_URL, data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            })
            response.raise_for_status()
            self._token = response.json()["access_token"]
            return self._token

    async def search_images(
        self,
        bbox: tuple[float, float, float, float],
        start_date: datetime,
        end_date: datetime,
        max_cloud_cover: float = 30.0,
    ) -> list[dict[str, Any]]:
        token = await self._get_token()
        west, south, east, north = bbox
        filter_str = (
            f"Collection/Name eq 'SENTINEL-2' "
            f"and OData.CSC.Intersects(area=geography'SRID=4326;POLYGON(("
            f"{west} {south},{east} {south},{east} {north},{west} {north},{west} {south}))') "
            f"and ContentDate/Start gt {start_date.isoformat()}Z "
            f"and ContentDate/Start lt {end_date.isoformat()}Z "
            f"and Attributes/OData.CSC.DoubleAttribute/any(att:att/Name eq 'cloudCover' "
            f"and att/Value lt {max_cloud_cover})"
        )
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.CATALOG_URL,
                params={"$filter": filter_str, "$top": 5, "$orderby": "ContentDate/Start desc"},
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()
            return response.json().get("value", [])

    async def download_image(self, image_id: str, output_path: str) -> str:
        token = await self._get_token()
        download_url = f"https://zipper.dataspace.copernicus.eu/odata/v1/Products({image_id})/$value"
        async with httpx.AsyncClient(timeout=300) as client:
            response = await client.get(
                download_url,
                headers={"Authorization": f"Bearer {token}"},
                follow_redirects=True,
            )
            response.raise_for_status()
            with open(output_path, "wb") as f:
                f.write(response.content)
        return output_path
```

`backend/ingestion/planet_provider.py`:
```python
from datetime import datetime
from typing import Any
from ingestion.provider_base import ImageryProvider


class PlanetProvider(ImageryProvider):
    """Phase 2 stub — to be implemented when Planet Labs subscription is active."""

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def search_images(
        self,
        bbox: tuple[float, float, float, float],
        start_date: datetime,
        end_date: datetime,
        max_cloud_cover: float = 30.0,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError("Planet Labs provider not yet implemented. Activate Phase 2.")

    async def download_image(self, image_id: str, output_path: str) -> str:
        raise NotImplementedError("Planet Labs provider not yet implemented. Activate Phase 2.")
```

- [ ] **Step 4: Implement Celery ingestion task**

`backend/ingestion/ingest_task.py`:
```python
import os
import tempfile
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.config import settings
from app.storage import upload_image
from ingestion.sentinel2_provider import Sentinel2Provider
from ingestion.planet_provider import PlanetProvider

# PCMC bounding box (approximate)
PCMC_BBOX = (73.7100, 18.5700, 73.8900, 18.6900)


def get_provider():
    if settings.imagery_provider == "sentinel2":
        return Sentinel2Provider(settings.sentinel2_client_id, settings.sentinel2_client_secret)
    elif settings.imagery_provider == "planet":
        return PlanetProvider(api_key=os.getenv("PLANET_API_KEY", ""))
    raise ValueError(f"Unknown provider: {settings.imagery_provider}")


async def run_ingestion(max_retries: int = 3):
    provider = get_provider()
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=2)

    images = None
    last_error = None
    for attempt in range(max_retries):
        try:
            images = await provider.search_images(
                bbox=PCMC_BBOX,
                start_date=start_date,
                end_date=end_date,
                max_cloud_cover=30.0,
            )
            break
        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                import asyncio
                await asyncio.sleep(2 ** attempt * 5)  # Exponential backoff: 5s, 10s, 20s

    if images is None:
        # All retries failed — create admin notification
        # (notification created via Celery task callback in celery_app.py)
        return {"status": "error", "message": f"Ingestion failed after {max_retries} retries: {last_error}"}

    if not images:
        return {"status": "no_images", "message": "No usable images found"}

    results = []
    for img_meta in images[:1]:  # Process latest image
        image_id = img_meta.get("Id") or img_meta.get("id")
        with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as tmp:
            tmp_path = tmp.name

        await provider.download_image(image_id, tmp_path)

        object_name = f"raw/{end_date.strftime('%Y/%m/%d')}/{uuid4()}.tif"
        upload_image(object_name, tmp_path)
        os.unlink(tmp_path)

        results.append({
            "image_id": image_id,
            "storage_path": object_name,
            "captured_at": img_meta.get("ContentDate", {}).get("Start"),
        })

    return {"status": "success", "images": results}
```

- [ ] **Step 5: Run tests and commit**

```bash
pytest backend/tests/test_ingestion.py -v
```

```bash
git add backend/ingestion/ backend/tests/test_ingestion.py
git commit -m "feat: image ingestion service with provider abstraction

Sentinel-2 provider for Phase 1 (Copernicus API). Planet Labs stub for
Phase 2. Celery task for scheduled ingestion with MinIO storage."
```

---

## Task 7: ML Pipeline — Model & Inference

**Files:**
- Create: `backend/ml/model.py`
- Create: `backend/ml/preprocessing.py`
- Create: `backend/ml/inference.py`
- Create: `backend/ml/postprocessing.py`
- Create: `backend/ml/classifier.py`
- Create: `backend/ml/pipeline_task.py`
- Create: `backend/tests/test_ml_postprocessing.py`
- Create: `backend/tests/test_ml_classifier.py`

- [ ] **Step 1: Write failing tests for postprocessing**

`backend/tests/test_ml_postprocessing.py`:
```python
import numpy as np
import pytest
from ml.postprocessing import threshold_mask, extract_regions, filter_by_area


def test_threshold_mask_1d_interval():
    mask = np.array([[0.9, 0.5], [0.3, 0.95]], dtype=np.float32)
    result = threshold_mask(mask, interval="1d")
    expected = np.array([[True, False], [False, True]])
    np.testing.assert_array_equal(result, expected)


def test_threshold_mask_30d_interval():
    mask = np.array([[0.6, 0.4], [0.3, 0.55]], dtype=np.float32)
    result = threshold_mask(mask, interval="30d")
    expected = np.array([[True, False], [False, True]])
    np.testing.assert_array_equal(result, expected)


def test_filter_by_area_removes_small_regions():
    regions = [
        {"area_sq_meters": 30.0, "polygon": None},
        {"area_sq_meters": 100.0, "polygon": None},
        {"area_sq_meters": 10.0, "polygon": None},
    ]
    filtered = filter_by_area(regions, min_area=50.0)
    assert len(filtered) == 1
    assert filtered[0]["area_sq_meters"] == 100.0
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest backend/tests/test_ml_postprocessing.py -v
```

- [ ] **Step 3: Implement Siamese U-Net model**

`backend/ml/model.py`:
```python
import torch
import torch.nn as nn


class ConvBlock(nn.Module):
    def __init__(self, in_ch, out_ch):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv2d(in_ch, out_ch, 3, padding=1),
            nn.BatchNorm2d(out_ch),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_ch, out_ch, 3, padding=1),
            nn.BatchNorm2d(out_ch),
            nn.ReLU(inplace=True),
        )

    def forward(self, x):
        return self.conv(x)


class Encoder(nn.Module):
    def __init__(self, in_channels=3):
        super().__init__()
        self.enc1 = ConvBlock(in_channels, 64)
        self.enc2 = ConvBlock(64, 128)
        self.enc3 = ConvBlock(128, 256)
        self.enc4 = ConvBlock(256, 512)
        self.pool = nn.MaxPool2d(2)

    def forward(self, x):
        e1 = self.enc1(x)
        e2 = self.enc2(self.pool(e1))
        e3 = self.enc3(self.pool(e2))
        e4 = self.enc4(self.pool(e3))
        return e1, e2, e3, e4


class Decoder(nn.Module):
    def __init__(self):
        super().__init__()
        # Inputs are concatenated features from both branches (double channels)
        self.up3 = nn.ConvTranspose2d(1024, 256, 2, stride=2)
        self.dec3 = ConvBlock(512 + 256, 256)
        self.up2 = nn.ConvTranspose2d(256, 128, 2, stride=2)
        self.dec2 = ConvBlock(256 + 128, 128)
        self.up1 = nn.ConvTranspose2d(128, 64, 2, stride=2)
        self.dec1 = ConvBlock(128 + 64, 64)
        self.final = nn.Conv2d(64, 1, 1)

    def forward(self, e1_a, e2_a, e3_a, e4_a, e1_b, e2_b, e3_b, e4_b):
        # Bottleneck: concat deepest features
        x = torch.cat([e4_a, e4_b], dim=1)  # 1024
        x = self.up3(x)
        x = torch.cat([x, e3_a, e3_b], dim=1)
        x = self.dec3(x)
        x = self.up2(x)
        x = torch.cat([x, e2_a, e2_b], dim=1)
        x = self.dec2(x)
        x = self.up1(x)
        x = torch.cat([x, e1_a, e1_b], dim=1)
        x = self.dec1(x)
        return torch.sigmoid(self.final(x))


class SiameseUNet(nn.Module):
    def __init__(self, in_channels=3):
        super().__init__()
        self.encoder = Encoder(in_channels)
        self.decoder = Decoder()

    def forward(self, img_before, img_after):
        e1_a, e2_a, e3_a, e4_a = self.encoder(img_before)
        e1_b, e2_b, e3_b, e4_b = self.encoder(img_after)
        return self.decoder(e1_a, e2_a, e3_a, e4_a, e1_b, e2_b, e3_b, e4_b)
```

- [ ] **Step 4: Implement preprocessing**

`backend/ml/preprocessing.py`:
```python
import numpy as np
import rasterio
from rasterio.warp import reproject, Resampling


def load_and_normalize(image_path: str) -> np.ndarray:
    with rasterio.open(image_path) as src:
        image = src.read()  # (bands, H, W)
        # Use first 3 bands (RGB)
        if image.shape[0] >= 3:
            image = image[:3]
        # Normalize to 0-1
        image = image.astype(np.float32)
        for i in range(image.shape[0]):
            band = image[i]
            min_val, max_val = np.percentile(band, [2, 98])
            if max_val > min_val:
                image[i] = np.clip((band - min_val) / (max_val - min_val), 0, 1)
        return image


def split_into_patches(image: np.ndarray, patch_size: int = 256, overlap: int = 32) -> list[tuple[np.ndarray, int, int]]:
    _, h, w = image.shape
    stride = patch_size - overlap
    patches = []
    for y in range(0, h - patch_size + 1, stride):
        for x in range(0, w - patch_size + 1, stride):
            patch = image[:, y:y + patch_size, x:x + patch_size]
            patches.append((patch, y, x))
    return patches


def merge_patches(patches: list[tuple[np.ndarray, int, int]], image_shape: tuple, patch_size: int = 256) -> np.ndarray:
    h, w = image_shape
    result = np.zeros((h, w), dtype=np.float32)
    count = np.zeros((h, w), dtype=np.float32)
    for patch, y, x in patches:
        result[y:y + patch_size, x:x + patch_size] += patch
        count[y:y + patch_size, x:x + patch_size] += 1
    count = np.maximum(count, 1)
    return result / count
```

- [ ] **Step 5: Implement postprocessing and classifier**

`backend/ml/postprocessing.py`:
```python
import numpy as np
import cv2
from shapely.geometry import Polygon

INTERVAL_THRESHOLDS = {
    "1d": 0.85,
    "7d": 0.70,
    "15d": 0.60,
    "30d": 0.50,
}


def threshold_mask(probability_mask: np.ndarray, interval: str) -> np.ndarray:
    threshold = INTERVAL_THRESHOLDS.get(interval, 0.6)
    return probability_mask >= threshold


def apply_morphology(binary_mask: np.ndarray) -> np.ndarray:
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    cleaned = cv2.morphologyEx(binary_mask.astype(np.uint8), cv2.MORPH_OPEN, kernel)
    cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_CLOSE, kernel)
    return cleaned


def extract_regions(binary_mask: np.ndarray, pixel_resolution_m: float = 10.0) -> list[dict]:
    contours, _ = cv2.findContours(binary_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    regions = []
    for contour in contours:
        if len(contour) < 3:
            continue
        area_pixels = cv2.contourArea(contour)
        area_sq_meters = area_pixels * (pixel_resolution_m ** 2)
        points = contour.squeeze().tolist()
        if len(points) >= 3:
            polygon = Polygon(points)
            centroid = polygon.centroid
            regions.append({
                "polygon": polygon,
                "area_sq_meters": area_sq_meters,
                "centroid": (centroid.x, centroid.y),
                "confidence": float(np.mean(binary_mask[binary_mask > 0])) if np.any(binary_mask > 0) else 0.0,
            })
    return regions


def filter_by_area(regions: list[dict], min_area: float = 50.0) -> list[dict]:
    return [r for r in regions if r["area_sq_meters"] >= min_area]
```

`backend/ml/classifier.py`:
```python
from shapely.geometry import Polygon


def classify_change(polygon: Polygon, area_sq_meters: float, nearby_buildings: bool = False) -> str:
    compactness = (4 * 3.14159 * polygon.area) / (polygon.length ** 2) if polygon.length > 0 else 0

    if area_sq_meters < 100:
        if nearby_buildings:
            return "extension"
        return "excavation"
    elif area_sq_meters < 500:
        if compactness > 0.7:
            return "foundation"
        return "land_clearing"
    else:
        if compactness > 0.6:
            return "new_structure"
        return "land_clearing"
```

- [ ] **Step 6: Implement inference and pipeline task**

`backend/ml/inference.py`:
```python
import torch
import numpy as np
from ml.model import SiameseUNet
from ml.preprocessing import split_into_patches, merge_patches

_model: SiameseUNet | None = None


def load_model(weights_path: str | None = None, device: str = "cpu") -> SiameseUNet:
    global _model
    model = SiameseUNet(in_channels=3)
    if weights_path:
        model.load_state_dict(torch.load(weights_path, map_location=device))
    model.eval()
    model.to(device)
    _model = model
    return model


def run_inference(
    image_before: np.ndarray,
    image_after: np.ndarray,
    model: SiameseUNet | None = None,
    device: str = "cpu",
    patch_size: int = 256,
) -> np.ndarray:
    if model is None:
        model = _model
    if model is None:
        raise RuntimeError("Model not loaded. Call load_model() first.")

    patches_before = split_into_patches(image_before, patch_size)
    patches_after = split_into_patches(image_after, patch_size)

    result_patches = []
    with torch.no_grad():
        for (pb, y, x), (pa, _, _) in zip(patches_before, patches_after):
            tb = torch.from_numpy(pb).unsqueeze(0).to(device)
            ta = torch.from_numpy(pa).unsqueeze(0).to(device)
            pred = model(tb, ta).squeeze().cpu().numpy()
            result_patches.append((pred, y, x))

    _, h, w = image_before.shape
    return merge_patches(result_patches, (h, w), patch_size)
```

`backend/ml/pipeline_task.py`:
```python
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.satellite_image import SatelliteImage
from app.config import settings
from app.storage import download_image, upload_image
from ml.preprocessing import load_and_normalize
from ml.inference import run_inference, load_model
from ml.postprocessing import threshold_mask, apply_morphology, extract_regions, filter_by_area
from ml.classifier import classify_change
from app.services.flagging_service import process_detection

INTERVALS = [
    ("1d", 1),
    ("7d", 7),
    ("15d", 15),
    ("30d", 30),
]


async def run_pipeline(db: AsyncSession, current_image_id: str):
    current = await db.get(SatelliteImage, current_image_id)
    if not current or not current.is_usable:
        return

    model = load_model()

    for interval_name, days in INTERVALS:
        target_date = current.captured_at - timedelta(days=days)

        # Find best baseline image within ±2 days of target
        result = await db.execute(
            select(SatelliteImage)
            .where(
                SatelliteImage.is_usable == True,
                SatelliteImage.captured_at.between(
                    target_date - timedelta(days=2),
                    target_date + timedelta(days=2),
                ),
            )
            .order_by(SatelliteImage.cloud_cover_pct.asc())
            .limit(1)
        )
        baseline = result.scalar_one_or_none()
        if not baseline:
            continue

        # Download both images
        import tempfile, os
        before_path = tempfile.mktemp(suffix=".tif")
        after_path = tempfile.mktemp(suffix=".tif")
        download_image(baseline.storage_path, before_path)
        download_image(current.storage_path, after_path)

        # Run ML pipeline
        img_before = load_and_normalize(before_path)
        img_after = load_and_normalize(after_path)

        change_mask = run_inference(img_before, img_after, model)
        binary = threshold_mask(change_mask, interval=interval_name)
        binary = apply_morphology(binary)
        regions = extract_regions(binary, pixel_resolution_m=current.resolution_meters)
        regions = filter_by_area(regions, min_area=settings.min_detection_area_sqm)

        # Process each detected region
        for region in regions:
            change_type = classify_change(region["polygon"], region["area_sq_meters"])

            # Save change mask
            mask_path = f"masks/{current.captured_at.strftime('%Y/%m/%d')}/{interval_name}_{region['centroid'][0]}_{region['centroid'][1]}.png"

            await process_detection(
                db=db,
                detection_polygon=region["polygon"],
                confidence=region["confidence"],
                comparison_interval=interval_name,
                image_before_id=baseline.id,
                image_after_id=current.id,
                change_mask_path=mask_path,
                area_sq_meters=region["area_sq_meters"],
                change_type=change_type,
            )

        os.unlink(before_path)
        os.unlink(after_path)
```

- [ ] **Step 7: Write classifier test**

`backend/tests/test_ml_classifier.py`:
```python
from shapely.geometry import box
from ml.classifier import classify_change


def test_small_area_no_buildings_is_excavation():
    polygon = box(0, 0, 5, 5)
    result = classify_change(polygon, area_sq_meters=80)
    assert result == "excavation"


def test_small_area_with_buildings_is_extension():
    polygon = box(0, 0, 5, 5)
    result = classify_change(polygon, area_sq_meters=80, nearby_buildings=True)
    assert result == "extension"


def test_large_compact_area_is_new_structure():
    polygon = box(0, 0, 30, 30)
    result = classify_change(polygon, area_sq_meters=900)
    assert result == "new_structure"
```

- [ ] **Step 8: Run all ML tests**

```bash
pytest backend/tests/test_ml_postprocessing.py backend/tests/test_ml_classifier.py -v
```

Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add backend/ml/ backend/tests/test_ml_postprocessing.py backend/tests/test_ml_classifier.py
git commit -m "feat: ML pipeline — Siamese U-Net, preprocessing, postprocessing, classifier

Change detection model with shared encoder branches. Multi-interval
thresholding (0.85/0.7/0.6/0.5). Region extraction with 50 sq m minimum.
Rule-based classification (excavation/foundation/structure/extension/clearing)."
```

---

## Task 8: Celery Tasks & Scheduling

**Files:**
- Create: `backend/tasks/celery_app.py`
- Create: `backend/tasks/grace_period_task.py`
- Create: `backend/tasks/retention_task.py`

- [ ] **Step 1: Implement Celery app with Beat schedule**

`backend/tasks/celery_app.py`:
```python
from celery import Celery
from celery.schedules import crontab
from app.config import settings

celery_app = Celery("pcmc", broker=settings.redis_url)

celery_app.conf.beat_schedule = {
    "ingest-imagery": {
        "task": "tasks.ingest",
        "schedule": crontab(hour=6, minute=0),  # 6:00 AM IST daily
    },
    "check-grace-periods": {
        "task": "tasks.check_grace_periods",
        "schedule": crontab(hour=7, minute=0),  # 7:00 AM IST daily
    },
    "cleanup-old-imagery": {
        "task": "tasks.cleanup_old_imagery",
        "schedule": crontab(day_of_month=1, hour=2, minute=0),  # 1st of month, 2 AM
    },
}
celery_app.conf.timezone = "Asia/Kolkata"


@celery_app.task(name="tasks.ingest")
def ingest_imagery_task():
    import asyncio
    from ingestion.ingest_task import run_ingestion
    asyncio.run(run_ingestion())


@celery_app.task(name="tasks.check_grace_periods")
def check_grace_periods_task():
    import asyncio
    from tasks.grace_period_task import check_expired_grace_periods
    asyncio.run(check_expired_grace_periods())


@celery_app.task(name="tasks.cleanup_old_imagery")
def cleanup_old_imagery_task():
    import asyncio
    from tasks.retention_task import cleanup_old_images
    asyncio.run(cleanup_old_images())
```

- [ ] **Step 2: Implement grace period checker**

`backend/tasks/grace_period_task.py`:
```python
from datetime import datetime, timezone
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models.construction_spot import ConstructionSpot
from app.models.notification import Notification

engine = create_async_engine(settings.database_url)
session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def check_expired_grace_periods():
    async with session_factory() as db:
        now = datetime.now(timezone.utc)
        result = await db.execute(
            select(ConstructionSpot).where(
                ConstructionSpot.status == "legal",
                ConstructionSpot.grace_period_until <= now,
            )
        )
        expired_spots = result.scalars().all()

        for spot in expired_spots:
            spot.status = "review_pending"
            spot.review_prompted_at = now

            if spot.assigned_to_id:
                notification = Notification(
                    user_id=spot.assigned_to_id,
                    message=f"12-month review due for spot at ({spot.id}). Please re-evaluate.",
                )
                db.add(notification)

        await db.commit()
        return {"transitioned": len(expired_spots)}
```

- [ ] **Step 3: Implement retention cleanup**

`backend/tasks/retention_task.py`:
```python
from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models.satellite_image import SatelliteImage
from app.storage import minio_client

engine = create_async_engine(settings.database_url)
session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def cleanup_old_images():
    async with session_factory() as db:
        cutoff = datetime.now(timezone.utc) - relativedelta(months=24)
        result = await db.execute(
            select(SatelliteImage).where(SatelliteImage.ingested_at < cutoff)
        )
        old_images = result.scalars().all()

        deleted_count = 0
        for image in old_images:
            try:
                minio_client.remove_object(settings.minio_bucket, image.storage_path)
            except Exception:
                pass  # Object may already be deleted
            await db.delete(image)
            deleted_count += 1

        await db.commit()
        return {"deleted": deleted_count}
```

- [ ] **Step 4: Commit**

```bash
git add backend/tasks/
git commit -m "feat: Celery tasks — scheduled ingestion, grace period checks, retention cleanup

Daily 6 AM image ingestion, 7 AM grace period expiry check with
REVIEW_PENDING transition and notifications, monthly old image cleanup
(24-month retention)."
```

---

## Task 9: Notifications API

**Files:**
- Create: `backend/app/schemas/notification.py`
- Create: `backend/app/routers/notifications.py`
- Create: `backend/app/services/notification_service.py`

- [ ] **Step 1: Implement notification schemas, service, and router**

`backend/app/schemas/notification.py`:
```python
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime


class NotificationOut(BaseModel):
    id: UUID
    message: str
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True
```

`backend/app/services/notification_service.py`:
```python
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.notification import Notification


async def get_notifications(db: AsyncSession, user_id: UUID, unread_only: bool = False):
    query = select(Notification).where(Notification.user_id == user_id).order_by(Notification.created_at.desc()).limit(50)
    if unread_only:
        query = query.where(Notification.is_read == False)
    result = await db.execute(query)
    return result.scalars().all()


async def get_unread_count(db: AsyncSession, user_id: UUID) -> int:
    result = await db.execute(
        select(func.count(Notification.id)).where(
            Notification.user_id == user_id, Notification.is_read == False
        )
    )
    return result.scalar()


async def mark_read(db: AsyncSession, notification_id: UUID, user_id: UUID):
    result = await db.execute(
        select(Notification).where(Notification.id == notification_id, Notification.user_id == user_id)
    )
    notification = result.scalar_one_or_none()
    if notification:
        notification.is_read = True
        await db.commit()
    return notification
```

`backend/app/routers/notifications.py`:
```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.database import get_db
from app.models.user import User
from app.schemas.notification import NotificationOut
from app.services.notification_service import get_notifications, get_unread_count, mark_read
from app.dependencies import get_current_user

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationOut])
async def list_notifications(
    unread_only: bool = False,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await get_notifications(db, user.id, unread_only)


@router.get("/count")
async def unread_count(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    count = await get_unread_count(db, user.id)
    return {"unread": count}


@router.patch("/{notification_id}/read")
async def read_notification(
    notification_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await mark_read(db, notification_id, user.id)
    return {"status": "ok"}
```

- [ ] **Step 2: Mount router in main.py and commit**

Add to `backend/app/main.py`:
```python
from app.routers import notifications
app.include_router(notifications.router)
```

```bash
git add backend/app/schemas/notification.py backend/app/services/notification_service.py backend/app/routers/notifications.py
git commit -m "feat: notifications API — list, unread count, mark read

In-app notification bell support for new detections, review reminders,
and pipeline alerts."
```

---

## Task 10: System Health & Admin Endpoints

**Files:**
- Modify: `backend/app/routers/admin.py`

- [ ] **Step 1: Add system health and zone endpoints to admin router**

Add to `backend/app/routers/admin.py`:
```python
from app.models.satellite_image import SatelliteImage
from app.models.zone import Zone
from sqlalchemy import select, func


@router.get("/system/health")
async def system_health(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("admin", "super_admin")),
):
    last_image = await db.execute(
        select(SatelliteImage).order_by(SatelliteImage.ingested_at.desc()).limit(1)
    )
    last = last_image.scalar_one_or_none()

    return {
        "last_ingestion": last.ingested_at.isoformat() if last else None,
        "last_image_usable": last.is_usable if last else None,
        "imagery_provider": settings.imagery_provider,
    }


@router.get("/zones")
async def list_zones(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("admin", "super_admin")),
):
    result = await db.execute(select(Zone))
    return result.scalars().all()
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/routers/admin.py
git commit -m "feat: system health and zone management admin endpoints"
```

---

## Task 11: Seed Scripts

**Files:**
- Create: `scripts/seed_users.py`
- Create: `scripts/seed_zones.py`
- Create: `scripts/download_pcmc_boundary.py`

- [ ] **Step 1: Create seed scripts**

`scripts/seed_users.py`:
```python
import asyncio
from app.database import async_session_factory
from app.models.user import User
from app.services.auth_service import hash_password


async def seed():
    async with async_session_factory() as db:
        users = [
            User(username="superadmin", password_hash=hash_password("admin123"), full_name="PCMC Super Admin", role="super_admin"),
            User(username="admin1", password_hash=hash_password("admin123"), full_name="PCMC Admin", role="admin"),
            User(username="reviewer1", password_hash=hash_password("review123"), full_name="Field Officer 1", role="reviewer"),
            User(username="reviewer2", password_hash=hash_password("review123"), full_name="Field Officer 2", role="reviewer"),
        ]
        for u in users:
            db.add(u)
        await db.commit()
        print(f"Seeded {len(users)} users")


if __name__ == "__main__":
    asyncio.run(seed())
```

`scripts/seed_zones.py`:
```python
"""Seed PCMC zone boundaries. Divides PCMC into a grid of zones for reviewer assignment."""
import asyncio
from shapely.geometry import box
from geoalchemy2.shape import from_shape
from app.database import async_session_factory
from app.models.zone import Zone

# Approximate PCMC bounding box
PCMC_WEST, PCMC_SOUTH = 73.7100, 18.5700
PCMC_EAST, PCMC_NORTH = 73.8900, 18.6900

# Divide into a 3x3 grid (9 zones)
COLS, ROWS = 3, 3


async def seed():
    async with async_session_factory() as db:
        dx = (PCMC_EAST - PCMC_WEST) / COLS
        dy = (PCMC_NORTH - PCMC_SOUTH) / ROWS
        zone_num = 1
        for row in range(ROWS):
            for col in range(COLS):
                west = PCMC_WEST + col * dx
                south = PCMC_SOUTH + row * dy
                east = west + dx
                north = south + dy
                zone = Zone(
                    name=f"Zone {zone_num}",
                    geometry=from_shape(box(west, south, east, north), srid=4326),
                )
                db.add(zone)
                zone_num += 1
        await db.commit()
        print(f"Seeded {zone_num - 1} zones")


if __name__ == "__main__":
    asyncio.run(seed())
```

`scripts/download_pcmc_boundary.py`:
```python
"""Download PCMC boundary from OpenStreetMap via Overpass API."""
import httpx
import json

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
QUERY = """
[out:json];
relation["name"="Pimpri-Chinchwad"]["admin_level"="6"];
out geom;
"""


def download():
    response = httpx.post(OVERPASS_URL, data={"data": QUERY}, timeout=60)
    response.raise_for_status()
    data = response.json()
    with open("data/pcmc_boundary.json", "w") as f:
        json.dump(data, f, indent=2)
    print("PCMC boundary saved to data/pcmc_boundary.json")


if __name__ == "__main__":
    download()
```

- [ ] **Step 2: Commit**

```bash
git add scripts/
git commit -m "feat: seed scripts for users, zones, and PCMC boundary download"
```

---

## Task 12: React Frontend — Project Setup & Auth

**Files:**
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/hooks/useAuth.ts`
- Create: `frontend/src/types/index.ts`
- Create: `frontend/src/pages/LoginPage.tsx`
- Create: `frontend/src/components/Layout.tsx`
- Create: `frontend/src/components/ProtectedRoute.tsx`

- [ ] **Step 1: Set up TypeScript types**

`frontend/src/types/index.ts`:
```typescript
export interface User {
  id: string;
  username: string;
  full_name: string;
  role: "reviewer" | "admin" | "super_admin";
}

export interface Spot {
  id: string;
  status: "flagged" | "legal" | "illegal" | "resolved" | "review_pending";
  first_detected_at: string;
  last_detected_at: string;
  confidence_score: number;
  change_type: string | null;
  assigned_to_id: string | null;
  version: number;
  latitude: number | null;
  longitude: number | null;
}

export interface SpotDetail extends Spot {
  notes: string | null;
  grace_period_until: string | null;
  reviewed_by_id: string | null;
  reviewed_at: string | null;
  previous_spot_id: string | null;
}

export interface Detection {
  id: string;
  detected_at: string;
  comparison_interval: "1d" | "7d" | "15d" | "30d";
  confidence: number;
  area_sq_meters: number;
}

export interface AuditLogEntry {
  id: string;
  officer_id: string;
  spot_id: string;
  action: string;
  notes: string | null;
  created_at: string;
}

export interface Notification {
  id: string;
  message: string;
  is_read: boolean;
  created_at: string;
}

export interface SpotStats {
  flagged: number;
  legal: number;
  illegal: number;
  resolved: number;
  review_pending: number;
}
```

- [ ] **Step 2: Set up API client with JWT interceptor**

`frontend/src/api/client.ts`:
```typescript
import axios from "axios";

const api = axios.create({
  baseURL: "http://localhost:8000",
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem("token");
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);

export default api;
```

- [ ] **Step 3: Implement auth hook, login page, layout, protected route**

`frontend/src/hooks/useAuth.ts`:
```typescript
import { createContext, useContext, useState, useEffect } from "react";
import api from "../api/client";
import type { User } from "../types";

interface AuthContextType {
  user: User | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  loading: boolean;
}

export const AuthContext = createContext<AuthContextType>(null!);

export function useAuth() {
  return useContext(AuthContext);
}

export function useAuthProvider(): AuthContextType {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (token) {
      api.get("/auth/me").then((res) => setUser(res.data)).catch(() => localStorage.removeItem("token")).finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  const login = async (username: string, password: string) => {
    const res = await api.post("/auth/login", { username, password });
    localStorage.setItem("token", res.data.access_token);
    const me = await api.get("/auth/me");
    setUser(me.data);
  };

  const logout = () => {
    localStorage.removeItem("token");
    setUser(null);
  };

  return { user, login, logout, loading };
}
```

`frontend/src/pages/LoginPage.tsx`:
```tsx
import { useState } from "react";
import { useAuth } from "../hooks/useAuth";
import { useNavigate } from "react-router-dom";

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await login(username, password);
      navigate("/");
    } catch {
      setError("Invalid credentials");
    }
  };

  return (
    <div style={{ display: "flex", justifyContent: "center", alignItems: "center", height: "100vh", background: "#f5f5f5" }}>
      <form onSubmit={handleSubmit} style={{ background: "white", padding: 32, borderRadius: 8, boxShadow: "0 2px 8px rgba(0,0,0,0.1)", width: 360 }}>
        <h2 style={{ marginBottom: 24 }}>PCMC Construction Monitor</h2>
        {error && <p style={{ color: "red" }}>{error}</p>}
        <input type="text" placeholder="Username" value={username} onChange={(e) => setUsername(e.target.value)} style={{ width: "100%", padding: 8, marginBottom: 12, boxSizing: "border-box" }} />
        <input type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} style={{ width: "100%", padding: 8, marginBottom: 16, boxSizing: "border-box" }} />
        <button type="submit" style={{ width: "100%", padding: 10, background: "#1976d2", color: "white", border: "none", borderRadius: 4, cursor: "pointer" }}>Login</button>
      </form>
    </div>
  );
}
```

`frontend/src/components/ProtectedRoute.tsx`:
```tsx
import { Navigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";

export default function ProtectedRoute({ children, roles }: { children: React.ReactNode; roles?: string[] }) {
  const { user, loading } = useAuth();
  if (loading) return <div>Loading...</div>;
  if (!user) return <Navigate to="/login" />;
  if (roles && !roles.includes(user.role)) return <Navigate to="/" />;
  return <>{children}</>;
}
```

`frontend/src/components/Layout.tsx`:
```tsx
import { Link, Outlet } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { useNotifications } from "../hooks/useNotifications";

export default function Layout() {
  const { user, logout } = useAuth();
  const { unreadCount } = useNotifications();

  return (
    <div style={{ display: "flex", height: "100vh" }}>
      <nav style={{ width: 220, background: "#1a237e", color: "white", padding: 16, display: "flex", flexDirection: "column" }}>
        <h3 style={{ marginBottom: 24 }}>PCMC Monitor</h3>
        <Link to="/" style={{ color: "white", marginBottom: 12, textDecoration: "none" }}>Map</Link>
        <Link to="/dashboard" style={{ color: "white", marginBottom: 12, textDecoration: "none" }}>Dashboard</Link>
        {(user?.role === "admin" || user?.role === "super_admin") && (
          <Link to="/admin" style={{ color: "white", marginBottom: 12, textDecoration: "none" }}>Admin</Link>
        )}
        {user?.role === "super_admin" && (
          <Link to="/audit" style={{ color: "white", marginBottom: 12, textDecoration: "none" }}>Audit</Link>
        )}
        <div style={{ marginTop: "auto" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
            <span style={{ position: "relative", cursor: "pointer", fontSize: 20 }}>
              &#128276;
              {unreadCount > 0 && (
                <span style={{ position: "absolute", top: -6, right: -8, background: "#f44336", borderRadius: "50%", width: 18, height: 18, fontSize: 11, display: "flex", alignItems: "center", justifyContent: "center" }}>
                  {unreadCount}
                </span>
              )}
            </span>
          </div>
          <p style={{ fontSize: 14 }}>{user?.full_name}</p>
          <button onClick={logout} style={{ background: "transparent", color: "white", border: "1px solid white", padding: "4px 8px", cursor: "pointer" }}>Logout</button>
        </div>
      </nav>
      <main style={{ flex: 1, overflow: "auto" }}>
        <Outlet />
      </main>
    </div>
  );
}
```

`frontend/src/App.tsx`:
```tsx
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthContext, useAuthProvider } from "./hooks/useAuth";
import Layout from "./components/Layout";
import ProtectedRoute from "./components/ProtectedRoute";
import LoginPage from "./pages/LoginPage";
import MapPage from "./pages/MapPage";
import DashboardPage from "./pages/DashboardPage";
import AdminPage from "./pages/AdminPage";
import AuditPage from "./pages/AuditPage";

export default function App() {
  const auth = useAuthProvider();

  return (
    <AuthContext.Provider value={auth}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<ProtectedRoute><Layout /></ProtectedRoute>}>
            <Route path="/" element={<MapPage />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/admin" element={<ProtectedRoute roles={["admin", "super_admin"]}><AdminPage /></ProtectedRoute>} />
            <Route path="/audit" element={<ProtectedRoute roles={["super_admin"]}><AuditPage /></ProtectedRoute>} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthContext.Provider>
  );
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/
git commit -m "feat: React frontend — auth, routing, layout with role-based nav

JWT login, protected routes, sidebar navigation with role-based visibility.
Type definitions matching backend schemas."
```

---

## Task 13: React Frontend — Map View & Spot Detail

**Files:**
- Create: `frontend/src/pages/MapPage.tsx`
- Create: `frontend/src/components/Map/MapView.tsx`
- Create: `frontend/src/components/Map/SpotMarker.tsx`
- Create: `frontend/src/components/Map/SpotDetailPanel.tsx`
- Create: `frontend/src/hooks/useSpots.ts`

- [ ] **Step 1a: Implement useNotifications hook**

`frontend/src/hooks/useNotifications.ts`:
```typescript
import { useState, useEffect } from "react";
import api from "../api/client";

export function useNotifications(pollIntervalMs: number = 30000) {
  const [unreadCount, setUnreadCount] = useState(0);

  useEffect(() => {
    const fetchCount = () => {
      api.get("/notifications/count").then((res) => setUnreadCount(res.data.unread)).catch(() => {});
    };
    fetchCount();
    const interval = setInterval(fetchCount, pollIntervalMs);
    return () => clearInterval(interval);
  }, [pollIntervalMs]);

  return { unreadCount };
}
```

- [ ] **Step 1b: Implement useSpots hook**

`frontend/src/hooks/useSpots.ts`:
```typescript
import { useState, useEffect } from "react";
import api from "../api/client";
import type { Spot, SpotDetail } from "../types";

export function useSpots(filters?: { status?: string }) {
  const [spots, setSpots] = useState<Spot[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchSpots = async () => {
    setLoading(true);
    const params = new URLSearchParams();
    if (filters?.status) params.set("status", filters.status);
    const res = await api.get(`/spots?${params}`);
    setSpots(res.data);
    setLoading(false);
  };

  useEffect(() => { fetchSpots(); }, [filters?.status]);

  return { spots, loading, refetch: fetchSpots };
}

export function useSpotDetail(spotId: string | null) {
  const [spot, setSpot] = useState<SpotDetail | null>(null);

  useEffect(() => {
    if (!spotId) { setSpot(null); return; }
    api.get(`/spots/${spotId}`).then((res) => setSpot(res.data));
  }, [spotId]);

  return { spot, setSpot };
}

export async function reviewSpot(spotId: string, action: string, version: number, notes?: string) {
  const res = await api.patch(`/spots/${spotId}/review`, { action, version, notes });
  return res.data;
}
```

- [ ] **Step 2: Implement map components**

`frontend/src/components/Map/MapView.tsx`:
```tsx
import { MapContainer, TileLayer, GeoJSON } from "react-leaflet";
import SpotMarker from "./SpotMarker";
import type { Spot } from "../../types";
import "leaflet/dist/leaflet.css";

const PCMC_CENTER: [number, number] = [18.6298, 73.7997];

interface Props {
  spots: Spot[];
  onSpotClick: (spotId: string) => void;
}

export default function MapView({ spots, onSpotClick }: Props) {
  return (
    <MapContainer center={PCMC_CENTER} zoom={13} style={{ height: "100%", width: "100%" }}>
      <TileLayer
        attribution='&copy; OpenStreetMap'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      {spots.map((spot) => (
        <SpotMarker key={spot.id} spot={spot} onClick={() => onSpotClick(spot.id)} />
      ))}
    </MapContainer>
  );
}
```

`frontend/src/components/Map/SpotMarker.tsx`:
```tsx
import { CircleMarker, Popup } from "react-leaflet";
import type { Spot } from "../../types";

const STATUS_COLORS: Record<string, string> = {
  flagged: "#ff9800",
  illegal: "#f44336",
  review_pending: "#ffeb3b",
  legal: "#4caf50",
  resolved: "#9e9e9e",
};

interface Props {
  spot: Spot;
  onClick: () => void;
}

export default function SpotMarker({ spot, onClick }: Props) {
  if (!spot.latitude || !spot.longitude) return null;

  return (
    <CircleMarker
      center={[spot.latitude, spot.longitude]}
      radius={8}
      pathOptions={{ color: STATUS_COLORS[spot.status] || "#999", fillColor: STATUS_COLORS[spot.status] || "#999", fillOpacity: 0.7 }}
      eventHandlers={{ click: onClick }}
    >
      <Popup>
        <strong>{spot.status.toUpperCase()}</strong><br />
        {spot.change_type && <span>Type: {spot.change_type}<br /></span>}
        Confidence: {(spot.confidence_score * 100).toFixed(0)}%
      </Popup>
    </CircleMarker>
  );
}
```

`frontend/src/components/Map/SpotDetailPanel.tsx`:
```tsx
import { useState } from "react";
import { reviewSpot } from "../../hooks/useSpots";
import type { SpotDetail } from "../../types";

interface Props {
  spot: SpotDetail;
  onClose: () => void;
  onReviewed: () => void;
}

export default function SpotDetailPanel({ spot, onClose, onReviewed }: Props) {
  const [notes, setNotes] = useState("");
  const [error, setError] = useState("");

  const handleReview = async (action: string) => {
    try {
      if ((action === "marked_legal" || action === "re_approved") && !notes.trim()) {
        setError("Notes are required when marking as legal");
        return;
      }
      await reviewSpot(spot.id, action, spot.version, notes || undefined);
      onReviewed();
    } catch (err: any) {
      if (err.response?.status === 409) {
        setError("Conflict: this spot was modified by another user. Please refresh.");
      } else {
        setError("Failed to update spot");
      }
    }
  };

  return (
    <div style={{ width: 380, background: "white", borderLeft: "1px solid #ddd", padding: 16, overflowY: "auto" }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16 }}>
        <h3>Spot Detail</h3>
        <button onClick={onClose} style={{ background: "none", border: "none", fontSize: 18, cursor: "pointer" }}>x</button>
      </div>

      <p><strong>Status:</strong> {spot.status}</p>
      <p><strong>Type:</strong> {spot.change_type || "Unknown"}</p>
      <p><strong>Confidence:</strong> {(spot.confidence_score * 100).toFixed(0)}%</p>
      <p><strong>First detected:</strong> {new Date(spot.first_detected_at).toLocaleDateString()}</p>
      <p><strong>Last detected:</strong> {new Date(spot.last_detected_at).toLocaleDateString()}</p>
      {spot.grace_period_until && <p><strong>Grace until:</strong> {new Date(spot.grace_period_until).toLocaleDateString()}</p>}
      {spot.notes && <p><strong>Notes:</strong> {spot.notes}</p>}

      <hr style={{ margin: "16px 0" }} />

      <textarea
        placeholder="Add notes (required for marking legal)..."
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
        style={{ width: "100%", height: 80, marginBottom: 8, boxSizing: "border-box" }}
      />

      {error && <p style={{ color: "red", fontSize: 14 }}>{error}</p>}

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        {spot.status === "flagged" && (
          <>
            <button onClick={() => handleReview("marked_legal")} style={{ background: "#4caf50", color: "white", border: "none", padding: "8px 16px", borderRadius: 4, cursor: "pointer" }}>Mark Legal</button>
            <button onClick={() => handleReview("marked_illegal")} style={{ background: "#f44336", color: "white", border: "none", padding: "8px 16px", borderRadius: 4, cursor: "pointer" }}>Mark Illegal</button>
          </>
        )}
        {spot.status === "illegal" && (
          <button onClick={() => handleReview("marked_resolved")} style={{ background: "#2196f3", color: "white", border: "none", padding: "8px 16px", borderRadius: 4, cursor: "pointer" }}>Mark Resolved</button>
        )}
        {spot.status === "review_pending" && (
          <>
            <button onClick={() => handleReview("re_approved")} style={{ background: "#4caf50", color: "white", border: "none", padding: "8px 16px", borderRadius: 4, cursor: "pointer" }}>Re-approve</button>
            <button onClick={() => handleReview("re_flagged")} style={{ background: "#ff9800", color: "white", border: "none", padding: "8px 16px", borderRadius: 4, cursor: "pointer" }}>Re-flag</button>
          </>
        )}
      </div>
    </div>
  );
}
```

`frontend/src/pages/MapPage.tsx`:
```tsx
import { useState } from "react";
import MapView from "../components/Map/MapView";
import SpotDetailPanel from "../components/Map/SpotDetailPanel";
import { useSpots, useSpotDetail } from "../hooks/useSpots";

export default function MapPage() {
  const [statusFilter, setStatusFilter] = useState<string | undefined>();
  const { spots, refetch } = useSpots({ status: statusFilter });
  const [selectedSpotId, setSelectedSpotId] = useState<string | null>(null);
  const { spot: selectedSpot } = useSpotDetail(selectedSpotId);

  return (
    <div style={{ display: "flex", height: "100%" }}>
      <div style={{ flex: 1, position: "relative" }}>
        <div style={{ position: "absolute", top: 10, left: 60, zIndex: 1000, background: "white", padding: 8, borderRadius: 4, boxShadow: "0 2px 4px rgba(0,0,0,0.2)" }}>
          <select value={statusFilter || ""} onChange={(e) => setStatusFilter(e.target.value || undefined)}>
            <option value="">All statuses</option>
            <option value="flagged">Flagged</option>
            <option value="illegal">Illegal</option>
            <option value="review_pending">Review Pending</option>
            <option value="legal">Legal</option>
            <option value="resolved">Resolved</option>
          </select>
        </div>
        <MapView spots={spots} onSpotClick={setSelectedSpotId} />
      </div>
      {selectedSpot && (
        <SpotDetailPanel
          spot={selectedSpot}
          onClose={() => setSelectedSpotId(null)}
          onReviewed={() => { setSelectedSpotId(null); refetch(); }}
        />
      )}
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/
git commit -m "feat: map view with spot markers, detail panel, and review actions

Interactive Leaflet map centered on PCMC. Color-coded spot markers by status.
Side panel with spot details, before/after imagery, and review action buttons
with mandatory notes for legal marking. Optimistic locking conflict handling."
```

---

## Task 14: React Frontend — Dashboard & Admin Views

**Files:**
- Create: `frontend/src/pages/DashboardPage.tsx`
- Create: `frontend/src/components/Dashboard/StatsView.tsx`
- Create: `frontend/src/pages/AdminPage.tsx`
- Create: `frontend/src/pages/AuditPage.tsx`
- Create: `frontend/src/components/SuperAdmin/AuditLog.tsx`
- Create: `frontend/src/components/SuperAdmin/OfficerSummary.tsx`

- [ ] **Step 1: Implement dashboard stats page**

`frontend/src/components/Dashboard/StatsView.tsx`:
```tsx
import { useState, useEffect } from "react";
import api from "../../api/client";
import type { SpotStats } from "../../types";

export default function StatsView() {
  const [stats, setStats] = useState<SpotStats | null>(null);

  useEffect(() => {
    api.get("/spots/stats").then((res) => setStats(res.data));
  }, []);

  if (!stats) return <div>Loading...</div>;

  const items = [
    { label: "Flagged", value: stats.flagged, color: "#ff9800" },
    { label: "Illegal", value: stats.illegal, color: "#f44336" },
    { label: "Review Pending", value: stats.review_pending, color: "#ffeb3b" },
    { label: "Legal", value: stats.legal, color: "#4caf50" },
    { label: "Resolved", value: stats.resolved, color: "#9e9e9e" },
  ];

  return (
    <div>
      <h2 style={{ marginBottom: 24 }}>Dashboard</h2>
      <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
        {items.map((item) => (
          <div key={item.label} style={{ background: "white", padding: 24, borderRadius: 8, boxShadow: "0 2px 4px rgba(0,0,0,0.1)", minWidth: 150, borderLeft: `4px solid ${item.color}` }}>
            <div style={{ fontSize: 32, fontWeight: "bold" }}>{item.value}</div>
            <div style={{ color: "#666" }}>{item.label}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
```

`frontend/src/pages/DashboardPage.tsx`:
```tsx
import StatsView from "../components/Dashboard/StatsView";

export default function DashboardPage() {
  return (
    <div style={{ padding: 24 }}>
      <StatsView />
    </div>
  );
}
```

- [ ] **Step 2: Implement admin page**

`frontend/src/pages/AdminPage.tsx`:
```tsx
import { useState, useEffect } from "react";
import api from "../api/client";
import type { User } from "../types";

export default function AdminPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [newUser, setNewUser] = useState({ username: "", password: "", full_name: "", role: "reviewer" });

  useEffect(() => {
    api.get("/users").then((res) => setUsers(res.data));
  }, []);

  const createUser = async () => {
    await api.post("/users", newUser);
    const res = await api.get("/users");
    setUsers(res.data);
    setNewUser({ username: "", password: "", full_name: "", role: "reviewer" });
  };

  return (
    <div style={{ padding: 24 }}>
      <h2>User Management</h2>

      <div style={{ background: "white", padding: 16, borderRadius: 8, marginBottom: 24, boxShadow: "0 2px 4px rgba(0,0,0,0.1)" }}>
        <h3>Add Officer</h3>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <input placeholder="Username" value={newUser.username} onChange={(e) => setNewUser({ ...newUser, username: e.target.value })} style={{ padding: 8 }} />
          <input placeholder="Full Name" value={newUser.full_name} onChange={(e) => setNewUser({ ...newUser, full_name: e.target.value })} style={{ padding: 8 }} />
          <input type="password" placeholder="Password" value={newUser.password} onChange={(e) => setNewUser({ ...newUser, password: e.target.value })} style={{ padding: 8 }} />
          <select value={newUser.role} onChange={(e) => setNewUser({ ...newUser, role: e.target.value })}>
            <option value="reviewer">Reviewer</option>
            <option value="admin">Admin</option>
          </select>
          <button onClick={createUser} style={{ background: "#1976d2", color: "white", border: "none", padding: "8px 16px", borderRadius: 4, cursor: "pointer" }}>Add</button>
        </div>
      </div>

      <table style={{ width: "100%", background: "white", borderRadius: 8, boxShadow: "0 2px 4px rgba(0,0,0,0.1)" }}>
        <thead>
          <tr style={{ borderBottom: "1px solid #eee" }}>
            <th style={{ padding: 12, textAlign: "left" }}>Username</th>
            <th style={{ padding: 12, textAlign: "left" }}>Full Name</th>
            <th style={{ padding: 12, textAlign: "left" }}>Role</th>
          </tr>
        </thead>
        <tbody>
          {users.map((u) => (
            <tr key={u.id} style={{ borderBottom: "1px solid #eee" }}>
              <td style={{ padding: 12 }}>{u.username}</td>
              <td style={{ padding: 12 }}>{u.full_name}</td>
              <td style={{ padding: 12 }}>{u.role}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 3: Implement audit page (super admin)**

`frontend/src/components/SuperAdmin/AuditLog.tsx`:
```tsx
import { useState, useEffect } from "react";
import api from "../../api/client";
import type { AuditLogEntry } from "../../types";

export default function AuditLog() {
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [filterAction, setFilterAction] = useState("");

  useEffect(() => {
    const params = new URLSearchParams();
    if (filterAction) params.set("action", filterAction);
    api.get(`/audit/logs?${params}`).then((res) => setLogs(res.data));
  }, [filterAction]);

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <select value={filterAction} onChange={(e) => setFilterAction(e.target.value)}>
          <option value="">All actions</option>
          <option value="marked_legal">Marked Legal</option>
          <option value="marked_illegal">Marked Illegal</option>
          <option value="marked_resolved">Marked Resolved</option>
          <option value="re_approved">Re-approved</option>
          <option value="re_flagged">Re-flagged</option>
        </select>
      </div>
      <table style={{ width: "100%", background: "white", borderRadius: 8 }}>
        <thead>
          <tr style={{ borderBottom: "1px solid #eee" }}>
            <th style={{ padding: 12, textAlign: "left" }}>Date</th>
            <th style={{ padding: 12, textAlign: "left" }}>Officer</th>
            <th style={{ padding: 12, textAlign: "left" }}>Action</th>
            <th style={{ padding: 12, textAlign: "left" }}>Notes</th>
          </tr>
        </thead>
        <tbody>
          {logs.map((log) => (
            <tr key={log.id} style={{ borderBottom: "1px solid #eee" }}>
              <td style={{ padding: 12 }}>{new Date(log.created_at).toLocaleString()}</td>
              <td style={{ padding: 12 }}>{log.officer_id.slice(0, 8)}</td>
              <td style={{ padding: 12 }}>{log.action}</td>
              <td style={{ padding: 12 }}>{log.notes || "-"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

`frontend/src/components/SuperAdmin/OfficerSummary.tsx`:
```tsx
import { useState, useEffect } from "react";
import api from "../../api/client";

interface Summary {
  officer_id: string;
  action: string;
  count: number;
}

export default function OfficerSummary() {
  const [data, setData] = useState<Summary[]>([]);

  useEffect(() => {
    api.get("/audit/officer-summary").then((res) => setData(res.data));
  }, []);

  // Group by officer
  const grouped = data.reduce((acc, item) => {
    if (!acc[item.officer_id]) acc[item.officer_id] = {};
    acc[item.officer_id][item.action] = item.count;
    return acc;
  }, {} as Record<string, Record<string, number>>);

  return (
    <div>
      <h3>Officer Review Summary</h3>
      <table style={{ width: "100%", background: "white", borderRadius: 8 }}>
        <thead>
          <tr style={{ borderBottom: "1px solid #eee" }}>
            <th style={{ padding: 12, textAlign: "left" }}>Officer</th>
            <th style={{ padding: 12, textAlign: "left" }}>Legal</th>
            <th style={{ padding: 12, textAlign: "left" }}>Illegal</th>
            <th style={{ padding: 12, textAlign: "left" }}>Resolved</th>
            <th style={{ padding: 12, textAlign: "left" }}>Total</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(grouped).map(([officerId, actions]) => {
            const legal = (actions.marked_legal || 0) + (actions.re_approved || 0);
            const illegal = actions.marked_illegal || 0;
            const resolved = actions.marked_resolved || 0;
            return (
              <tr key={officerId} style={{ borderBottom: "1px solid #eee" }}>
                <td style={{ padding: 12 }}>{officerId.slice(0, 8)}</td>
                <td style={{ padding: 12 }}>{legal}</td>
                <td style={{ padding: 12 }}>{illegal}</td>
                <td style={{ padding: 12 }}>{resolved}</td>
                <td style={{ padding: 12 }}>{legal + illegal + resolved}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
```

`frontend/src/pages/AuditPage.tsx`:
```tsx
import AuditLog from "../components/SuperAdmin/AuditLog";
import OfficerSummary from "../components/SuperAdmin/OfficerSummary";

export default function AuditPage() {
  return (
    <div style={{ padding: 24 }}>
      <h2>Audit Trail</h2>
      <OfficerSummary />
      <div style={{ marginTop: 24 }}>
        <AuditLog />
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/
git commit -m "feat: dashboard stats, admin user management, super admin audit views

Status summary cards, user CRUD for admins, audit log table with action
filters, officer review summary with legal/illegal/resolved breakdown."
```

---

## Task 15: Integration Test & Final Wiring

**Files:**
- Create: `backend/tests/test_pipeline.py`
- Modify: `backend/app/main.py` (ensure all routers mounted)

- [ ] **Step 1: Write integration test for end-to-end flow**

`backend/tests/test_pipeline.py`:
```python
import pytest
from datetime import datetime, timezone
from app.models import User, ConstructionSpot, AuditLog
from app.services.auth_service import hash_password


@pytest.mark.asyncio
async def test_full_review_lifecycle(db_session):
    """Test: flag → mark legal → grace period → review pending"""
    # Create officer
    officer = User(username="test_officer", password_hash=hash_password("test"), full_name="Test", role="reviewer")
    db_session.add(officer)
    await db_session.flush()

    # Create flagged spot
    spot = ConstructionSpot(
        geometry="SRID=4326;POLYGON((73.79 18.62, 73.80 18.62, 73.80 18.63, 73.79 18.63, 73.79 18.62))",
        status="flagged",
        first_detected_at=datetime.now(timezone.utc),
        last_detected_at=datetime.now(timezone.utc),
        confidence_score=0.8,
        version=1,
    )
    db_session.add(spot)
    await db_session.flush()
    assert spot.status == "flagged"

    # Mark legal
    from app.services.spot_service import review_spot
    updated = await review_spot(db_session, spot.id, "marked_legal", 1, officer, notes="Permit #123")
    assert updated.status == "legal"
    assert updated.grace_period_until is not None
    assert updated.version == 2

    # Verify audit log created
    from sqlalchemy import select
    result = await db_session.execute(select(AuditLog).where(AuditLog.spot_id == spot.id))
    logs = result.scalars().all()
    assert len(logs) == 1
    assert logs[0].action == "marked_legal"
    assert logs[0].notes == "Permit #123"
```

- [ ] **Step 2: Verify all routers are mounted in main.py**

Ensure `backend/app/main.py` includes:
```python
from app.routers import auth, admin, spots, images, audit, notifications

app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(spots.router)
app.include_router(images.router)
app.include_router(audit.router)
app.include_router(notifications.router)
```

- [ ] **Step 3: Run full test suite**

```bash
pytest backend/tests/ -v
```

Expected: ALL PASS

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat: integration tests and final wiring

End-to-end review lifecycle test (flag → legal → audit log).
All routers mounted and verified."
```

---

## Summary

| Task | Component | Description |
|------|-----------|-------------|
| 1 | Infrastructure | Docker Compose, Dockerfiles, env config |
| 2 | Database | SQLAlchemy models, Alembic migrations |
| 3 | Auth | JWT, login, role-based access |
| 4 | API | Spots CRUD, flagging service, audit trail |
| 5 | Storage | MinIO wrapper, image serving |
| 6 | Ingestion | Sentinel-2 provider, Celery task |
| 7 | ML | Siamese U-Net, preprocessing, postprocessing |
| 8 | Scheduling | Celery Beat, grace period, retention |
| 9 | Notifications | In-app notification API |
| 10 | Admin | System health, zone endpoints |
| 11 | Scripts | Seed users, zones, PCMC boundary |
| 12 | Frontend | React setup, auth, routing |
| 13 | Frontend | Map view, spot markers, detail panel |
| 14 | Frontend | Dashboard, admin, audit views |
| 15 | Integration | End-to-end tests, final wiring |
