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
