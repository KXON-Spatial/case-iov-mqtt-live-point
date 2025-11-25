# Realtime Bus Demo — README

第一版：
- 車機：透過python模擬車機，將資料打到 MQTT Broker
  - 資料的點位沿真實的公車路線產生，每秒一點，並自動折返，如 `routes/` 路徑下有三條公車路線
-  MQTT Broker：使用 Mosquitto 並在本機運作
-  Database: 使用 PostgreSQL，根據本示範需求，只要單純的OLTP已經能滿足同時儲存即時位置與歷史點位的要求
-  API: 選用 FastAPI (ASGI-native)，透過 API 提供資料庫中即時點位與歷史軌跡的資料
   -  也可以使用 Flask，但其為 WSGI-based，需要 Flask-SocketIO 才能提供 WebSocket
-  WebSocket: 範例中使用的 FastAPI 提供 first-class WebSocket


## Local MQTT Broker (Mosquitto)

Run Mosquitto in Docker (exposes MQTT on 1883 and WebSocket on 9001):
```
docker run -it --name mosquitto \
  -p 1883:1883 -p 9001:9001 \
  eclipse-mosquitto
```

- Docker 上跑的是 Broker（就像廣播電台）
- The Docker container runs the broker (like a radio station)

若想安裝客戶端工具 (macOS 範例)：
```
brew install mosquitto
```

- mosquitto_pub (publisher): can be used for manual testing
- mosquitto_sub (subscriber): listens for messages on topics

在一個終端中訂閱所有 buses topic：
```
mosquitto_sub -h localhost -p 1883 -t "buses/#"
```

在另一個終端中執行模擬器來發送訊息：
```
python sim_route_buses.py
```

---

## PostgreSQL — 建立資料庫與資料表 / Database setup

下列 SQL 與指令協助建立資料庫與兩張表：`bus_locations_latest` 與
`bus_locations_history`。

1) 建立資料庫（使用 postgres 使用者或有權限的帳號）：
```
createdb -U postgres realtime_demo
```

2) 連到 `realtime_demo` 資料庫並建立資料表：
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

說明 / Notes:
- `bus_locations_latest` 儲存每台車最新位置（以 `bus_id` 為主鍵）。
- `bus_locations_history` 儲存每次接收到的位置，以便查詢或回放。

---

## Python — 套件清單 / Python packages

建議最小依賴（放在 `requirements.txt`）：
```
paho-mqtt
psycopg2-binary
fastapi
uvicorn[standard]
python-dotenv
```

安裝：
```
python -m pip install -r requirements.txt
```

備註：`psycopg2-binary` 在本地開發較方便；在生產環境可考慮使用
系統安裝的 `psycopg2`。

---

## Mapbox token

前端 `index.html` 內含一個 Mapbox token 的 placeholder。你可以：

1) 直接在 `index.html` 中替換 `mapboxglAccessToken` 為你的 token（快速測試），
或
2) 使用本地開發伺服器將環境變數注入到前端（需要額外步驟）。

快速方法：開啟 `index.html` 並把下列一行替換成你的 token：
```js
const mapboxglAccessToken = 'your_mapbox_token_here';
```

到 https://www.mapbox.com 申請 token，並妥善保管（生產環境勿洩漏）。

---

## Quick start / 快速啟動

1) 啟動 Postgres 並建立資料庫與資料表（見上方）。
2) 啟動 Mosquitto（docker 或 brew）。
3) 安裝 Python 套件：
```
python -m pip install -r requirements.txt
```
4) 啟動 API server (FastAPI)：
```
uvicorn api_server:app --reload --port 8000
```
5) 啟動 consumer：
```
python consumer.py
```
6) 啟動模擬器：
```
python sim_route_buses.py
```
7) 開啟 `index.html` 或用靜態伺服器提供它，並確認 Mapbox token 已設定。

API / WebSocket:
- REST: `http://localhost:8000/api/buses` (latest snapshot)
- History: `http://localhost:8000/api/history?bus_id=bus_001&minutes=10`
- WebSocket: `ws://localhost:8000/ws/buses`

---

## Consumer
訂閱 buses/+/location → 收到 JSON → 寫進 PostgreSQL 的 `bus_locations_latest` 與
`bus_locations_history`（同時更新/插入）
