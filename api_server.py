import asyncio
import json
import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta, timezone
from fastapi.middleware.cors import CORSMiddleware


from dotenv import load_dotenv

load_dotenv()

# Postgres DSN (can be provided as PG_DSN or DATABASE_URL in .env)
PG_DSN = os.getenv("PG_DSN") or os.getenv("DATABASE_URL")

if not PG_DSN:
    pg_db = os.getenv("PG_DB", "realtime_demo")
    pg_user = os.getenv("PG_USER")
    pg_password = os.getenv("PG_PASSWORD")
    pg_host = os.getenv("PG_HOST", "localhost")
    pg_port = os.getenv("PG_PORT", "5432")

    if pg_user:
        PG_DSN = f"dbname={pg_db} user={pg_user} host={pg_host} port={pg_port}"
        if pg_password:
            PG_DSN += f" password={pg_password}"
    else:
        PG_DSN = None
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # allow all origins during demo
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_conn():
    if not PG_DSN:
        raise RuntimeError(
            "Postgres DSN not configured. Set PG_DSN or PG_USER in .env")
    return psycopg2.connect(PG_DSN)


@app.get("/api/config")
def get_config():
    """Return runtime configuration that may be needed by the front-end.

    Currently returns the Mapbox token (if set in MAPBOX_TOKEN).
    """
    return {"mapbox_token": os.getenv("MAPBOX_TOKEN", "")}


@app.get("/api/buses")
def get_latest_locations():
    """Get the latest locations for all buses (REST endpoint)."""
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT bus_id, lat, lon, speed_kmh, ts_utc, updated_at "
                "FROM bus_locations_latest ORDER BY bus_id;")
            results = cur.fetchall()
            return results
    finally:
        conn.close()


@app.websocket("/ws/buses")
async def ws_buses(websocket: WebSocket):
    await websocket.accept()

    try:
        conn = get_conn()
    except Exception as e:
        # If DB connection fails, send an error to the client instead of crashing
        await websocket.send_text(f"DB connection error: {e}")
        await websocket.close()
        return

    cur = conn.cursor(cursor_factory=RealDictCursor)

    try:
        while True:
            try:
                cur.execute(
                    "SELECT * FROM bus_locations_latest ORDER BY bus_id")
                rows = cur.fetchall()
                payload = json.dumps(rows, default=str)
                await websocket.send_text(payload)
            except Exception as inner_e:
                print("Error querying DB in WS loop:", inner_e)
                # Optionally decide whether to close the websocket based on the situation
                await websocket.send_text(f"DB query error: {inner_e}")
                await asyncio.sleep(2.0)

            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
        print("WebSocket client disconnected")
    finally:
        cur.close()
        conn.close()


@app.get("/api/history")
def get_history(
    bus_id: str,
    # default 10 minutes; range 1~1440 (one day)
    minutes: int = Query(10, ge=1, le=1440),
):
    """
    Return the specified bus's trajectory points within the last N minutes
    (ordered by time).
    """
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Current time (UTC)
            now_utc = datetime.now(timezone.utc)
            since = now_utc - timedelta(minutes=minutes)

            cur.execute(
                """
                SELECT bus_id, lat, lon, speed_kmh, ts_utc, ingested_at
                FROM bus_locations_history
                WHERE bus_id = %s
                  AND ts_utc >= %s
                ORDER BY ts_utc ASC
                """,
                (bus_id, since),
            )
            rows = cur.fetchall()
        return rows
    finally:
        conn.close()
