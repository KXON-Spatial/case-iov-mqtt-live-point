import json
import os
import paho.mqtt.client as mqtt
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime
from typing import Any, Dict

from dotenv import load_dotenv

load_dotenv()

# Load sensitive configuration from environment with sensible defaults
BROKER_HOST = os.getenv("BROKER_HOST", "localhost")
BROKER_PORT = int(os.getenv("BROKER_PORT", "1883"))

# You can provide a full DSN via PG_DSN or individual PG_* vars (optional)
PG_DSN = os.getenv("PG_DSN") or os.getenv("DATABASE_URL")

# If a full DSN isn't provided, try constructing one from individual vars.
if not PG_DSN:
    pg_db = os.getenv("PG_DB", "realtime_demo")
    pg_user = os.getenv("PG_USER")
    pg_password = os.getenv("PG_PASSWORD")
    pg_host = os.getenv("PG_HOST", "localhost")
    pg_port = os.getenv("PG_PORT", "5432")

    if pg_user:
        # Build a DSN without embedding a default password; password must come
        # from PG_PASSWORD if required. This avoids hard-coded credentials.
        PG_DSN = f"dbname={pg_db} user={pg_user} host={pg_host} port={pg_port}"
        if pg_password:
            PG_DSN += f" password={pg_password}"
    else:
        PG_DSN = None


def upsert_location(conn, msg_dict: Dict[str, Any]):
    """Write the received JSON into bus_locations_latest.

    If bus_id already exists, update the row.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO bus_locations_latest (bus_id, lat, lon, speed_kmh, ts_utc)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (bus_id) DO UPDATE
            SET lat = EXCLUDED.lat,
                lon = EXCLUDED.lon,
                speed_kmh = EXCLUDED.speed_kmh,
                ts_utc = EXCLUDED.ts_utc,
                updated_at = now();
            """,
            (
                msg_dict["bus_id"],
                msg_dict["lat"],
                msg_dict["lon"],
                msg_dict["speed_kmh"],
                # ISO8601 string — psycopg2 will auto-convert to TIMESTAMPTZ
                msg_dict["timestamp"],
            ),
        )
    # Do not commit here; commit together in on_message


def insert_history(conn, msg_dict: Dict[str, Any]):
    """Insert each location into bus_locations_history."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO bus_locations_history (bus_id, lat, lon, speed_kmh, ts_utc)
            VALUES (%s, %s, %s, %s, %s);
            """,
            (
                msg_dict["bus_id"],
                msg_dict["lat"],
                msg_dict["lon"],
                msg_dict["speed_kmh"],
                # ISO8601 string — psycopg2 will auto-convert to TIMESTAMPTZ
                msg_dict["timestamp"],
            ),
        )
    # Do not commit here; commit together in on_message


def on_message(client, userdata, msg):
    conn = userdata["pg_conn"]
    # Handle incoming MQTT messages. For each message, write to
    # bus_locations_history and insert/update bus_locations_latest.
    try:
        payload_str = msg.payload.decode("utf-8")
        data = json.loads(payload_str)
        print(f"[MQTT] {msg.topic}: {data}")
        insert_history(conn, data)  # insert into history
        upsert_location(conn, data)  # update latest location
        conn.commit()  # commit together
    except Exception as e:
        conn.rollback()
        print(f"Error handling message: {e}")


def main():
    # Connect to PostgreSQL (keep a persistent connection)
    if not PG_DSN:
        raise RuntimeError(
            "Postgres DSN not configured. Set PG_DSN or PG_USER in .env")
    conn = psycopg2.connect(PG_DSN)

    client = mqtt.Client(client_id="bus_location_consumer",
                         userdata={"pg_conn": conn})
    client.on_message = on_message

    client.connect(BROKER_HOST, BROKER_PORT, keepalive=60)

    # Subscribe to locations for all buses
    client.subscribe("buses/+/location")

    print("Starting consumer... (Ctrl+C to stop)")
    client.loop_forever()


if __name__ == "__main__":
    main()
