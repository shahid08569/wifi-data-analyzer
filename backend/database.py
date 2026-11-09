"""
WiFi & Hotspot Data Analyzer - Database Layer
Stores persistent network history, device profiles, traffic metrics and hotspot sessions in SQLite.
"""

import sqlite3
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wifi_analyzer.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # Devices table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS devices (
        mac TEXT PRIMARY KEY,
        ip TEXT NOT NULL,
        hostname TEXT,
        vendor TEXT,
        device_type TEXT DEFAULT 'Unknown',
        is_hotspot_client INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1,
        first_seen TEXT,
        last_seen TEXT
    )
    """)

    # Traffic logs table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS traffic_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mac TEXT NOT NULL,
        ip TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        bytes_down INTEGER DEFAULT 0,
        bytes_up INTEGER DEFAULT 0,
        is_hotspot INTEGER DEFAULT 0
    )
    """)

    # Hotspot sessions table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS hotspot_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        started_at TEXT NOT NULL,
        ended_at TEXT,
        duration_seconds INTEGER DEFAULT 0,
        bytes_down INTEGER DEFAULT 0,
        bytes_up INTEGER DEFAULT 0,
        clients_count INTEGER DEFAULT 0,
        status TEXT DEFAULT 'active'
    )
    """)

    # Indices for high query performance
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_traffic_mac ON traffic_logs(mac)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_traffic_ts ON traffic_logs(timestamp)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_traffic_hotspot ON traffic_logs(is_hotspot)")

    # Seed baseline hotspot sessions for demonstration if empty
    cursor.execute("SELECT COUNT(*) FROM hotspot_sessions")
    if cursor.fetchone()[0] == 0:
        past_2h = (datetime.now() - timedelta(hours=2)).isoformat()
        past_1h = (datetime.now() - timedelta(hours=1)).isoformat()
        cursor.execute("""
            INSERT INTO hotspot_sessions (started_at, ended_at, duration_seconds, bytes_down, bytes_up, clients_count, status)
            VALUES (?, ?, 3600, 185000000, 45000000, 3, 'closed')
        """, (past_2h, past_1h))

    conn.commit()
    conn.close()


def upsert_device(mac: str, ip: str, hostname: str = None, vendor: str = None,
                  device_type: str = "Unknown", is_hotspot_client: int = 0, is_active: int = 1):
    clean_mac = mac.upper().replace("-", ":")
    now = datetime.now().isoformat()
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT first_seen, hostname, vendor FROM devices WHERE mac = ?", (clean_mac,))
    row = cursor.fetchone()

    generic_names = ["Realme Smartphone", "Windows PC", "Xiaomi / Redmi Phone", "Samsung Galaxy", "Apple iPhone", "Unknown"]

    if row:
        existing_host = row["hostname"] or ""
        # Keep authentic router names if incoming is generic
        if hostname and not any(hostname.startswith(g) for g in generic_names):
            final_hostname = hostname
        elif existing_host and not any(existing_host.startswith(g) for g in generic_names):
            final_hostname = existing_host
        else:
            final_hostname = hostname or existing_host or "Device"

        final_vendor = vendor if vendor and vendor != "Unknown" else row["vendor"]
        cursor.execute("""
            UPDATE devices 
            SET ip = ?, hostname = ?, vendor = ?, device_type = ?, 
                is_hotspot_client = MAX(is_hotspot_client, ?), 
                is_active = ?, last_seen = ?
            WHERE mac = ?
        """, (ip, final_hostname, final_vendor, device_type, is_hotspot_client, is_active, now, clean_mac))
    else:
        cursor.execute("""
            INSERT INTO devices (mac, ip, hostname, vendor, device_type, is_hotspot_client, is_active, first_seen, last_seen)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (clean_mac, ip, hostname or "Unknown", vendor or "Unknown", device_type, is_hotspot_client, is_active, now, now))

    conn.commit()
    conn.close()


def set_all_devices_inactive():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE devices SET is_active = 0")
    conn.commit()
    conn.close()


def log_traffic(mac: str, ip: str, bytes_down: int, bytes_up: int, is_hotspot: int = 0):
    clean_mac = mac.upper().replace("-", ":")
    now = datetime.now().isoformat()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO traffic_logs (mac, ip, timestamp, bytes_down, bytes_up, is_hotspot)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (clean_mac, ip, now, bytes_down, bytes_up, is_hotspot))
    conn.commit()
    conn.close()


def parse_date_filter(filter_type: str = "30days", start_date: str = None, end_date: str = None):
    now = datetime.now()
    if filter_type == "1hour" or filter_type == "hour":
        start = (now - timedelta(hours=1)).isoformat()
        end = now.isoformat()
    elif filter_type == "today" or filter_type == "1day":
        start = (now - timedelta(days=1)).isoformat()
        end = now.isoformat()
    elif filter_type == "7days":
        start = (now - timedelta(days=7)).isoformat()
        end = now.isoformat()
    elif filter_type == "30days" or filter_type == "month":
        start = (now - timedelta(days=30)).isoformat()
        end = now.isoformat()
    elif filter_type == "all":
        start = "2000-01-01T00:00:00"
        end = (now + timedelta(days=1)).isoformat()
    elif filter_type == "custom" and start_date and end_date:
        start = f"{start_date}T00:00:00"
        end = f"{end_date}T23:59:59"
    else:
        # Default to 30 days
        start = (now - timedelta(days=30)).isoformat()
        end = now.isoformat()
    return start, end


def get_devices_with_usage(filter_type: str = "30days", start_date: str = None, end_date: str = None) -> List[Dict[str, Any]]:
    start_ts, end_ts = parse_date_filter(filter_type, start_date, end_date)
    conn = get_connection()
    cursor = conn.cursor()

    query = """
    SELECT 
        d.mac,
        d.ip,
        d.hostname,
        d.vendor,
        d.device_type,
        d.is_hotspot_client,
        d.is_active,
        d.first_seen,
        d.last_seen,
        COALESCE(SUM(t.bytes_down), 0) AS total_down,
        COALESCE(SUM(t.bytes_up), 0) AS total_up,
        COALESCE(SUM(t.bytes_down + t.bytes_up), 0) AS total_bytes,
        COALESCE(SUM(CASE WHEN t.is_hotspot = 1 THEN (t.bytes_down + t.bytes_up) ELSE 0 END), 0) AS hotspot_bytes
    FROM devices d
    LEFT JOIN traffic_logs t ON d.mac = t.mac AND t.timestamp >= ? AND t.timestamp <= ?
    GROUP BY d.mac
    ORDER BY total_bytes DESC, d.is_active DESC
    """
    cursor.execute(query, (start_ts, end_ts))
    rows = cursor.fetchall()

    result = []
    for r in rows:
        result.append({
            "mac": r["mac"],
            "ip": r["ip"],
            "hostname": r["hostname"] or "Device",
            "vendor": r["vendor"] or "Unknown",
            "device_type": r["device_type"] or "Unknown",
            "is_hotspot_client": bool(r["is_hotspot_client"]),
            "is_active": bool(r["is_active"]),
            "first_seen": r["first_seen"],
            "last_seen": r["last_seen"],
            "bytes_down": int(r["total_down"]),
            "bytes_up": int(r["total_up"]),
            "total_bytes": int(r["total_bytes"]),
            "hotspot_bytes": int(r["hotspot_bytes"])
        })

    conn.close()
    return result


def get_summary_statistics(filter_type: str = "30days", start_date: str = None, end_date: str = None) -> Dict[str, Any]:
    start_ts, end_ts = parse_date_filter(filter_type, start_date, end_date)
    conn = get_connection()
    cursor = conn.cursor()

    # Total network traffic
    cursor.execute("""
        SELECT 
            COALESCE(SUM(bytes_down), 0) AS total_down,
            COALESCE(SUM(bytes_up), 0) AS total_up,
            COALESCE(SUM(CASE WHEN is_hotspot = 1 THEN (bytes_down + bytes_up) ELSE 0 END), 0) AS hotspot_traffic
        FROM traffic_logs
        WHERE timestamp >= ? AND timestamp <= ?
    """, (start_ts, end_ts))
    traffic = cursor.fetchone()

    # Device counts
    cursor.execute("SELECT COUNT(*) AS total_devices, SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) AS active_devices FROM devices")
    dev_counts = cursor.fetchone()

    # Hotspot duration in selected range
    cursor.execute("""
        SELECT 
            COALESCE(SUM(duration_seconds), 0) AS total_hotspot_seconds,
            COUNT(*) AS total_sessions
        FROM hotspot_sessions
        WHERE started_at >= ? AND started_at <= ?
    """, (start_ts, end_ts))
    hs = cursor.fetchone()

    conn.close()

    total_down = int(traffic["total_down"]) if traffic else 0
    total_up = int(traffic["total_up"]) if traffic else 0
    hotspot_traffic = int(traffic["hotspot_traffic"]) if traffic else 0
    total_bytes = total_down + total_up

    return {
        "filter": filter_type,
        "start_time": start_ts,
        "end_time": end_ts,
        "total_devices": int(dev_counts["total_devices"] or 0),
        "active_devices": int(dev_counts["active_devices"] or 0),
        "total_download_bytes": total_down,
        "total_upload_bytes": total_up,
        "total_bytes": total_bytes,
        "hotspot_traffic_bytes": hotspot_traffic,
        "hotspot_total_seconds": int(hs["total_hotspot_seconds"] or 0),
        "hotspot_sessions_count": int(hs["total_sessions"] or 0)
    }


def get_hotspot_sessions_list(limit: int = 50) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, started_at, ended_at, duration_seconds, bytes_down, bytes_up, clients_count, status
        FROM hotspot_sessions
        ORDER BY id DESC
        LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "id": r["id"],
            "started_at": r["started_at"],
            "ended_at": r["ended_at"],
            "duration_seconds": r["duration_seconds"],
            "bytes_down": r["bytes_down"],
            "bytes_up": r["bytes_up"],
            "total_bytes": r["bytes_down"] + r["bytes_up"],
            "clients_count": r["clients_count"],
            "status": r["status"]
        }
        for r in rows
    ]


def start_or_update_hotspot_session(is_on: bool, current_clients: int, down_delta: int = 0, up_delta: int = 0):
    conn = get_connection()
    cursor = conn.cursor()
    now_dt = datetime.now()
    now_str = now_dt.isoformat()

    cursor.execute("SELECT id, started_at, duration_seconds, bytes_down, bytes_up, clients_count FROM hotspot_sessions WHERE status = 'active' ORDER BY id DESC LIMIT 1")
    active_session = cursor.fetchone()

    if is_on:
        if active_session:
            # Update existing active session
            started_dt = datetime.fromisoformat(active_session["started_at"])
            duration = int((now_dt - started_dt).total_seconds())
            new_down = active_session["bytes_down"] + down_delta
            new_up = active_session["bytes_up"] + up_delta
            new_max_clients = max(active_session["clients_count"], current_clients)

            cursor.execute("""
                UPDATE hotspot_sessions
                SET ended_at = ?, duration_seconds = ?, bytes_down = ?, bytes_up = ?, clients_count = ?
                WHERE id = ?
            """, (now_str, duration, new_down, new_up, new_max_clients, active_session["id"]))
        else:
            # Start a new session
            cursor.execute("""
                INSERT INTO hotspot_sessions (started_at, ended_at, duration_seconds, bytes_down, bytes_up, clients_count, status)
                VALUES (?, ?, 0, ?, ?, ?, 'active')
            """, (now_str, now_str, down_delta, up_delta, current_clients))
    else:
        if active_session:
            # Close active session
            started_dt = datetime.fromisoformat(active_session["started_at"])
            duration = int((now_dt - started_dt).total_seconds())
            cursor.execute("""
                UPDATE hotspot_sessions
                SET ended_at = ?, duration_seconds = ?, status = 'closed'
                WHERE id = ?
            """, (now_str, duration, active_session["id"]))

    conn.commit()
    conn.close()
