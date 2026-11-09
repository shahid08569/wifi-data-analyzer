"""
WiFi & Hotspot Data Analyzer - Backend Application API
FastAPI server serving REST API, Huawei Router Gateway, and Web Dashboard.
"""

import os
import subprocess
from contextlib import asynccontextmanager
from fastapi import FastAPI, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from database import (
    init_db,
    get_devices_with_usage,
    get_summary_statistics,
    get_hotspot_sessions_list,
    log_traffic,
    upsert_device,
    start_or_update_hotspot_session,
    set_all_devices_inactive
)
from network_scanner import get_local_network_info, scan_devices
from hotspot_service import hotspot_service
from router_service import router_service
from traffic_monitor import monitor


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    monitor.start()
    yield
    monitor.stop()


app = FastAPI(
    title="WiFi & Hotspot Data Analyzer",
    description="Real-time and historical Wi-Fi and Mobile Hotspot bandwidth tracking per device",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))


@app.get("/api/health")
def health_check():
    return {"status": "ok", "app": "WiFi Data Analyzer"}


@app.get("/api/network-info")
def get_network_info():
    info = get_local_network_info()
    hs = hotspot_service.check_hotspot_status()
    router_status = router_service.get_status()
    return {
        "network": info,
        "hotspot": hs,
        "router": router_status
    }


@app.get("/api/speed")
def get_live_speed():
    return monitor.current_speed


@app.get("/api/devices")
def get_devices(
    filter_type: str = Query("30days", alias="filter", description="Filter: 1hour, today, 7days, 30days, all, custom"),
    start_date: str = Query(None, description="YYYY-MM-DD for custom filter"),
    end_date: str = Query(None, description="YYYY-MM-DD for custom filter")
):
    devices = get_devices_with_usage(filter_type, start_date, end_date)
    return {
        "filter": filter_type,
        "count": len(devices),
        "devices": devices
    }


@app.get("/api/summary")
def get_summary(
    filter_type: str = Query("30days", alias="filter", description="Filter: 1hour, today, 7days, 30days, all, custom"),
    start_date: str = Query(None, description="YYYY-MM-DD for custom filter"),
    end_date: str = Query(None, description="YYYY-MM-DD for custom filter")
):
    summary = get_summary_statistics(filter_type, start_date, end_date)
    return summary


@app.get("/api/hotspot")
def get_hotspot_details():
    current_status = hotspot_service.check_hotspot_status()
    sessions = get_hotspot_sessions_list(limit=50)
    return {
        "current": current_status,
        "sessions": sessions
    }


@app.get("/api/router")
def get_router_status():
    return router_service.get_status()


@app.post("/api/router/login")
def router_login(data: dict = Body(...)):
    username = data.get("username", "admin")
    password = data.get("password", "")
    return router_service.login(username, password)


@app.post("/api/scan")
def trigger_scan():
    """Performs real-time Layer-2 ARP sweep. Only active devices are marked online."""
    set_all_devices_inactive()
    discovered = scan_devices()
    for dev in discovered:
        upsert_device(
            mac=dev["mac"],
            ip=dev["ip"],
            hostname=dev["hostname"],
            vendor=dev["vendor"],
            device_type=dev["device_type"],
            is_hotspot_client=0,
            is_active=1
        )
    return {"status": "scan_complete", "devices_found": len(discovered), "devices": discovered}


@app.post("/api/hotspot/open-settings")
def open_windows_hotspot_settings():
    try:
        subprocess.run(["cmd", "/c", "start", "ms-settings:network-mobilehotspot"], shell=True)
        return {"status": "opened_settings"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    @app.get("/")
    def serve_index():
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 9000))
    uvicorn.run("app:app", host="127.0.0.1", port=port, reload=False)
