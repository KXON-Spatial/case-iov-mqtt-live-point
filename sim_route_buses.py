import json
import time
import math
from datetime import datetime, timezone
from pathlib import Path

import paho.mqtt.client as mqtt

import os
from dotenv import load_dotenv

load_dotenv()

# MQTT broker config from environment
BROKER_HOST = os.getenv("BROKER_HOST", "localhost")
BROKER_PORT = int(os.getenv("BROKER_PORT", "1883"))

BUS_IDS = ["bus_001", "bus_002", "bus_003"]

# The three GeoJSON routes (LineString) generated earlier
# Note: place the files under the project's routes/ directory
ROUTE_FILES = {
    "bus_001": "routes/route_307.geojson",
    "bus_002": "routes/route_R12.geojson",
    "bus_003": "routes/route_MinquanMetro.geojson",
}


# Simulation speed (larger = faster bus)
BUS_SPEED_KMH = 30.0
BUS_SPEED_MPS = BUS_SPEED_KMH * 1000 / 3600  # m/s

# Distance per second (default derived from speed)
DIST_PER_SECOND_M = BUS_SPEED_MPS


# ---------------- geojson loader ----------------
def load_linestring_geojson(path: str):
    """
    Supports two formats:
    1) FeatureCollection -> LineString of the first feature
    2) Feature -> LineString

    Returns a list of (lat, lon) tuples: [(lat, lon), ...]
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))

    if data.get("type") == "FeatureCollection":
        geom = data["features"][0]["geometry"]
    elif data.get("type") == "Feature":
        geom = data["geometry"]
    else:
        raise ValueError(f"Unsupported GeoJSON type: {data.get('type')}")

    if geom["type"] != "LineString":
        raise ValueError(f"Only LineString supported, got {geom['type']}")

    coords = geom["coordinates"]  # [[lon, lat], ...]
    return [(lat, lon) for lon, lat in coords]


# ---------------- distance utils ----------------
def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * \
        math.cos(phi2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def interpolate(lat1, lon1, lat2, lon2, t):
    """t in [0,1]"""
    return lat1 + (lat2 - lat1) * t, lon1 + (lon2 - lon1) * t


# ---------------- bus state ----------------
class BusState:
    """
    Move along the polyline:
    - current_index points to the start point
    - segment_progress_m indicates meters traveled on the current segment
    - direction=1 means forward, -1 means backward (bounce at ends)
    """

    def __init__(self, bus_id: str, route_points):
        self.bus_id = bus_id
        self.route_points = route_points

        self.current_index = 0
        self.direction = 1   # 1 forward, -1 backward
        self.segment_progress_m = 0.0

        self.lat, self.lon = route_points[0]
        self.speed_kmh = BUS_SPEED_KMH

    def step(self, dist_m):
        pts = self.route_points

        while dist_m > 0:
            next_index = self.current_index + self.direction

            # Bounce / turnaround logic at polyline ends
            if next_index >= len(pts):
                self.direction = -1
                next_index = self.current_index + self.direction
            elif next_index < 0:
                self.direction = 1
                next_index = self.current_index + self.direction

            lat1, lon1 = pts[self.current_index]
            lat2, lon2 = pts[next_index]

            seg_len = haversine_m(lat1, lon1, lat2, lon2)

            remain_on_seg = seg_len - self.segment_progress_m

            if dist_m < remain_on_seg:
                # Still on the same segment: update progress and interpolate
                self.segment_progress_m += dist_m
                t = self.segment_progress_m / seg_len if seg_len > 0 else 1.0
                self.lat, self.lon = interpolate(lat1, lon1, lat2, lon2, t)
                dist_m = 0
            else:
                # Finished this segment: move to the next segment
                dist_m -= remain_on_seg
                self.current_index = next_index
                self.segment_progress_m = 0.0
                self.lat, self.lon = pts[self.current_index]


def main():
    # 1) load routes
    routes = {}
    for bus_id, fpath in ROUTE_FILES.items():
        route = load_linestring_geojson(fpath)
        if len(route) < 2:
            raise ValueError(f"Route for {bus_id} has too few points.")
        routes[bus_id] = route
        print(f"[route loaded] {bus_id}: {fpath}, pts={len(route)}")

    # 2) init states
    bus_states = {}
    for bus_id in BUS_IDS:
        bus_states[bus_id] = BusState(bus_id, routes[bus_id])

    # 3) mqtt
    client = mqtt.Client(client_id="sim_geojson_buses")
    client.connect(BROKER_HOST, BROKER_PORT, keepalive=60)

    print(f"Starting geojson-route simulator for: {', '.join(BUS_IDS)}")
    print("Press Ctrl+C to stop.")

    while True:
        now = datetime.now(timezone.utc).isoformat()

        for bus_id, state in bus_states.items():
            state.step(DIST_PER_SECOND_M)

            payload = {
                "bus_id": bus_id,
                "lat": state.lat,
                "lon": state.lon,
                "speed_kmh": state.speed_kmh,
                "timestamp": now,
            }

            topic = f"buses/{bus_id}/location"
            client.publish(topic, json.dumps(payload), qos=0)

        time.sleep(1)


if __name__ == "__main__":
    main()
