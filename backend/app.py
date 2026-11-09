"""
WiFi & Hotspot Data Analyzer - Backend Application API
FastAPI server serving REST API and Web Dashboard.
"""

import os
import subprocess
from contextlib import asynccontextmanager
from fastapi import FastAPI, Query
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
    start_or_update_hotspot_session
)
from network_scanner import get_local_network_info, scan_devices
from hotspot_service import hotspot_service
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
    return {
        "network": info,
        "hotspot": hs
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


@app.post("/api/scan")
def trigger_scan():
    """Performs deep full-subnet Layer-2 ARP sweep across all 254 IPs."""
    discovered = scan_devices()
    for dev in discovered:
        upsert_device(
            mac=dev["mac"],
            ip=dev["ip"],
            hostname=dev["hostname"],
            vendor=dev["vendor"],
            device_type=dev["device_type"],
            is_hotspot_client=0,
            is_active=dev["is_active"]
        )
    return {"status": "scan_complete", "devices_found": len(discovered), "devices": discovered}


@app.post("/api/simulate")
def simulate_traffic_burst():
    devices = get_devices_with_usage("30days")
    if devices:
        import random
        for dev in devices:
            down_burst = random.randint(1500000, 8500000)
            up_burst = random.randint(500000, 2500000)
            log_traffic(dev["mac"], dev["ip"], down_burst, up_burst, is_hotspot=0)
    return {"status": "simulated_burst_logged", "devices_affected": len(devices)}


@app.post("/api/hotspot/open-settings")
def open_windows_hotspot_settings():
    """Opens Windows Mobile Hotspot settings page on the host machine."""
    try:
        subprocess.run(["cmd", "/c", "start", "ms-settings:network-mobilehotspot"], shell=True)
        return {"status": "opened_settings"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/api/hotspot/simulate-session")
def simulate_hotspot_session():
    """Generates an active or completed hotspot test session for immediate demonstration."""
    import random
    from datetime import datetime, timedelta
    start_or_update_hotspot_session(
        is_on=True, 
        current_clients=random.randint(2, 4), 
        down_delta=random.randint(45000000, 150000000), 
        up_delta=random.randint(12000000, 45000000)
    )
    return {"status": "hotspot_session_updated"}


if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    @app.get("/")
    def serve_index():
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 9000))
    uvicorn.run("app:app", host="127.0.0.1", port=port, reload=False)
