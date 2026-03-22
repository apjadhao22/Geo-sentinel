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
