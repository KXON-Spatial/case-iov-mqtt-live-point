# Realtime Bus Demo — README

A small demo that stitches together a simulated bus, MQTT broker, Postgres-backed consumer, and a FastAPI
WebSocket feed so you can visualize live vehicle positions in the browser. The repo demonstrates how to move
data from MQTT to a relational database and expose it via REST/WebSocket for a Mapbox GL frontend.

## Components at a glance
- **Bus simulator** (`sim_route_buses.py`): publishes location points along real routes in `routes/` to `buses/<id>/location` every second.
- **MQTT broker**: Mosquitto (Docker or local package) receives simulator messages and broadcasts them to subscribers.
- **Consumer** (`consumer.py`): listens on MQTT topics, writes snapshots to `bus_locations_latest`, and appends every point to `bus_locations_history`.
- **API server** (`api_server.py`): FastAPI exposes REST snapshots and history plus a `/ws/buses` WebSocket for live updates.
- **Frontend** (`index.html`): deck.gl + Mapbox GL that fetches the Mapbox token from `/api/config` and connects to the WebSocket stream for visualization.

## Prerequisites
- Python 3.10+ (asyncio support).
- PostgreSQL instance accessible locally.
- Mosquitto broker (Docker container or system install).
- Mapbox access token for the front-end (used via `/api/config`).
- Optional: Docker CLI for the Mosquitto container.

## Environment configuration
1. Copy `.env.example` to `.env`.
2. Fill in the values (`BROKER_HOST`, `BROKER_PORT`, `PG_DSN` or the PG_* pieces, `MAPBOX_TOKEN`).
3. The Python scripts use `python-dotenv` to load the values; missing keys raise descriptive errors so you know which variable to add.

## Database setup
1. Create the database (run as the `postgres` user or a privileged account):
   ```bash
   createdb -U postgres realtime_demo
   ```
2. Run the following SQL (for example with `psql -d realtime_demo -f setup.sql`):
   ```sql
   -- latest snapshot per bus
   CREATE TABLE IF NOT EXISTS bus_locations_latest (
     bus_id TEXT PRIMARY KEY,
     lat DOUBLE PRECISION NOT NULL,
     lon DOUBLE PRECISION NOT NULL,
     speed_kmh REAL,
     ts_utc TIMESTAMPTZ,
     updated_at TIMESTAMPTZ DEFAULT now()
   );

   -- history of locations
   CREATE TABLE IF NOT EXISTS bus_locations_history (
     id SERIAL PRIMARY KEY,
     bus_id TEXT NOT NULL,
     lat DOUBLE PRECISION NOT NULL,
     lon DOUBLE PRECISION NOT NULL,
     speed_kmh REAL,
     ts_utc TIMESTAMPTZ,
     ingested_at TIMESTAMPTZ DEFAULT now()
   );
   ```
3. `bus_locations_latest` keeps the current position per vehicle; `bus_locations_history` logs every ingested point.

## MQTT broker
**Option 1: Docker (recommended)**
```bash
docker run -it --name mosquitto \
  -p 1883:1883 -p 9001:9001 \
  eclipse-mosquitto
```

**Option 2: macOS package**
```bash
brew install mosquitto
```

Useful tools:
- `mosquitto_pub`: publish custom JSON payloads for manual testing.
- `mosquitto_sub`: subscribe to topics (e.g., `mosquitto_sub -h localhost -p 1883 -t "buses/#"`).

## Python dependencies
The minimal dependencies listed in `requirements.txt`:
```
paho-mqtt
psycopg2-binary
fastapi
uvicorn[standard]
python-dotenv
```
Install them with pip:
```bash
python -m pip install -r requirements.txt
```
`psycopg2-binary` is easier for local development; swap to the system `psycopg2` wheel for production deployments if desired.

## Execution order after cloning
1. **Create `.env`** from `.env.example` and verify the credentials (Postgres DSN, Mapbox token, MQTT broker host/port).
2. **Prepare the database** by starting Postgres and running the SQL above to create the two tables.
3. **Install Python dependencies**: `python -m pip install -r requirements.txt`.
4. **Start Mosquitto** (Docker or brew) so MQTT topics are available before the consumer connects.
5. **Start the API server**: `uvicorn api_server:app --reload --port 8000`. This exposes REST, WebSocket, and config endpoints.
6. **Start the consumer**: `python consumer.py`. It will connect to the MQTT broker and keep Postgres updated.
7. **Start the simulator**: `python sim_route_buses.py`. It begins publishing fake location data to MQTT.
8. **Optionally monitor MQTT**: run `mosquitto_sub -h localhost -p 1883 -t "buses/#"` in another terminal to watch raw messages.
9. **Open the frontend**: `index.html` can be served via `python -m http.server 8001` or opened directly. It fetches the Mapbox token from `/api/config` and subscribes to `/ws/buses`.

## API & WebSocket endpoints
- REST snapshot: `http://localhost:8000/api/buses`
- History: `http://localhost:8000/api/history?bus_id=bus_001&minutes=10`
- WebSocket feed: `ws://localhost:8000/ws/buses`
- Mapbox token: `http://localhost:8000/api/config`

Every component relies on the `.env` configuration and the MQTT broker running before they attempt to connect. Follow the numbered sequence above for the smoothest startup experience after cloning the repo.# Realtime Bus Demo — README


## Local MQTT Broker (Mosquitto)

### Option 1: Run Mosquitto in Docker (exposes MQTT on 1883 and WebSocket on 9001):
```
docker run -it --name mosquitto \
  -p 1883:1883 -p 9001:9001 \
  eclipse-mosquitto
```
- The Docker container runs the broker (like a radio station)

### Option 2: Install Mosquitto (macOS)：
```
brew install mosquitto
```

- mosquitto_pub (publisher): can be used for manual testing
- mosquitto_sub (subscriber): listens for messages on topics


---

## PostgreSQL — Database setup

Create database ans two tables：`bus_locations_latest` and
`bus_locations_history`。

1) Create database（using `postgres` user）：
```
createdb -U postgres realtime_demo
```

2) Connect to `realtime_demo` database and create tables：
```
-- latest snapshot per bus
CREATE TABLE IF NOT EXISTS bus_locations_latest (
  bus_id TEXT PRIMARY KEY,
  lat DOUBLE PRECISION NOT NULL,
  lon DOUBLE PRECISION NOT NULL,
  speed_kmh REAL,
  ````markdown
  # Realtime Bus Demo — README

  Initial version:
  - Vehicle simulator: a Python script simulates vehicle devices that publish location data to an MQTT broker.
    - Location points are generated along real bus routes; one point per second. Routes loop back automatically. See the `routes/` directory for three sample routes.
  - MQTT Broker: Mosquitto running locally (or in Docker).
  - Database: PostgreSQL. For this demo, a simple OLTP setup is sufficient to store both current positions and historical points.
  - API: FastAPI (ASGI-native) is used to serve current positions and historical trajectories from the database.
    - You could use Flask, but since it is WSGI-based you would need Flask-SocketIO to provide WebSocket support.
  - WebSocket: FastAPI (used in this example) provides first-class WebSocket support.


  ## Local MQTT Broker (Mosquitto)

  Run Mosquitto in Docker (exposes MQTT on 1883 and WebSocket on 9001):
  ```
  docker run -it --name mosquitto \
    -p 1883:1883 -p 9001:9001 \
    eclipse-mosquitto
  ```

  - mosquitto_pub (publisher): can be used for manual testing
  - mosquitto_sub (subscriber): listens for messages on topics

  Subscribe to all 'buses' topics in one terminal:
  ```
  mosquitto_sub -h localhost -p 1883 -t "buses/#"
  ```

  Run the simulator in another terminal to send messages:
  ```
  python sim_route_buses.py
  ```

  ---

  ## PostgreSQL — Database setup

  The SQL and commands below help create the database and two tables: `bus_locations_latest` and
  `bus_locations_history`.

  1) Create the database (run as the `postgres` user or a privileged account):
  ```
  createdb -U postgres realtime_demo
  ```

  2) Connect to the `realtime_demo` database and create the tables:
  ```
  -- latest snapshot per bus
  CREATE TABLE IF NOT EXISTS bus_locations_latest (
    bus_id TEXT PRIMARY KEY,
    lat DOUBLE PRECISION NOT NULL,
    lon DOUBLE PRECISION NOT NULL,
    speed_kmh REAL,
    ts_utc TIMESTAMPTZ,
    updated_at TIMESTAMPTZ DEFAULT now()
  );

  -- history of locations
  CREATE TABLE IF NOT EXISTS bus_locations_history (
    id SERIAL PRIMARY KEY,
    bus_id TEXT NOT NULL,
    lat DOUBLE PRECISION NOT NULL,
    lon DOUBLE PRECISION NOT NULL,
    speed_kmh REAL,
    ts_utc TIMESTAMPTZ,
    ingested_at TIMESTAMPTZ DEFAULT now()
  );
  ```

  Notes:
  - `bus_locations_latest` stores the most recent position per vehicle (primary key: `bus_id`).
  - `bus_locations_history` stores each received point so you can query or replay trajectories.

  ---

  ## Python — Package list

  Recommended minimal dependencies (put them in `requirements.txt`):
  ```
  paho-mqtt
  psycopg2-binary
  fastapi
  uvicorn[standard]
  python-dotenv
  ```

  Install:
  ```
  python -m pip install -r requirements.txt
  ```

  Note: `psycopg2-binary` is convenient for local development; for production you may prefer a system-installed `psycopg2`.

  ---

  ## Mapbox token

  The front-end `index.html` contains a Mapbox token placeholder. You can:

  1) Replace the `mapboxglAccessToken` string directly in `index.html` for a quick test, or
  2) Inject the token at runtime from your development server (requires additional setup).

  Quick method: open `index.html` and replace the following line with your token:
  ```js
  const mapboxglAccessToken = 'your_mapbox_token_here';
  ```

  Get a token from https://www.mapbox.com and keep it secret in production.

  ---

  ## Quick start

  1) Start Postgres and create the database and tables (see above).
  2) Start Mosquitto (Docker or brew).
  
  Subscribe all buses info in one topic：
  ```
  mosquitto_sub -h localhost -p 1883 -t "buses/#"
  ```

  3) Install Python packages:
  ```
  python -m pip install -r requirements.txt
  ```
  4) Start the API server (FastAPI):
  ```
  uvicorn api_server:app --reload --port 8000
  ```
  5) Start the consumer:
  ```
  python consumer.py
  ```
  6) Start the simulator:
  ```
  python sim_route_buses.py (Push the simulated bus message)
  ```
  7) Open `index.html` directly or serve it from a static server, and make sure the Mapbox token is configured.

  API / WebSocket:
  - REST: `http://localhost:8000/api/buses` (latest snapshot)
  - History: `http://localhost:8000/api/history?bus_id=bus_001&minutes=10`
  - WebSocket: `ws://localhost:8000/ws/buses`

  ---

  ## Consumer
  Subscribes to `buses/+/location` → receives JSON → writes to PostgreSQL tables `bus_locations_latest` and
  `bus_locations_history` (upsert/update as appropriate).
  ````
