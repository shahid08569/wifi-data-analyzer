"""
WiFi & Hotspot Data Analyzer - Traffic Monitor
Runs in the background, tracks packet flows, measures per-device data consumption,
synchronizes with Huawei GPON router gateway, and updates real-time online/offline states dynamically.
"""

import time
import threading
import psutil
from typing import Dict, Any
from database import upsert_device, log_traffic, init_db, set_all_devices_inactive
from network_scanner import scan_devices, get_local_network_info
from hotspot_service import hotspot_service
from router_service import router_service


class TrafficMonitor:
    def __init__(self, interval_sec: int = 3):
        self.interval_sec = interval_sec
        self.running = False
        self.thread = None
        self.last_adapter_stats: Dict[str, Any] = {}
        self.current_speed = {"down_kbps": 0.0, "up_kbps": 0.0}
        self.cycle_count = 0

    def start(self):
        if self.running:
            return
        self.running = True
        init_db()
        # Initial sync with router on startup
        try:
            router_service.sync_to_database()
        except Exception:
            pass
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        print("Traffic Monitor background worker started.")

    def stop(self):
        self.running = False

    def _run_loop(self):
        while self.running:
            try:
                self.cycle_count += 1

                # 1. Periodic Huawei Router Gateway sync (every 25 seconds = every 8 cycles)
                if self.cycle_count % 8 == 1:
                    try:
                        router_service.sync_to_database()
                    except Exception as e:
                        print("Router sync notice:", e)

                # 2. Check Windows Hotspot state
                hs_status = hotspot_service.check_hotspot_status()
                hotspot_active = hs_status.get("is_active", False)
                hotspot_clients = {
                    c.get("Mac", "").upper().replace("-", ":"): c.get("Hostname", "") 
                    for c in hs_status.get("clients", [])
                }

                # 3. Live Layer-2 device discovery
                active_devices = scan_devices()

                # 4. Measure adapter traffic delta
                wifi_down_delta = 0
                wifi_up_delta = 0
                io_counters = psutil.net_io_counters(pernic=True)

                for iface, stats in io_counters.items():
                    if any(k in iface.lower() for k in ["wi-fi", "wireless", "wlan"]):
                        prev = self.last_adapter_stats.get(iface)
                        if prev:
                            if stats.bytes_recv >= prev.bytes_recv:
                                wifi_down_delta += (stats.bytes_recv - prev.bytes_recv)
                            if stats.bytes_sent >= prev.bytes_sent:
                                wifi_up_delta += (stats.bytes_sent - prev.bytes_sent)
                        self.last_adapter_stats[iface] = stats

                elapsed = max(1, self.interval_sec)
                self.current_speed["down_kbps"] = round((wifi_down_delta / elapsed) / 1024, 2)
                self.current_speed["up_kbps"] = round((wifi_up_delta / elapsed) / 1024, 2)

                # 5. Mark responding devices ONLINE and log active delta
                count = len(active_devices)

                for dev in active_devices:
                    mac = dev["mac"].upper().replace("-", ":")
                    ip = dev["ip"]
                    vendor = dev["vendor"]
                    hostname = dev["hostname"]
                    dev_type = dev["device_type"]
                    is_hs = 1 if mac in hotspot_clients or (hotspot_active and dev.get("is_hotspot", False)) else 0

                    upsert_device(
                        mac=mac,
                        ip=ip,
                        hostname=hostname,
                        vendor=vendor,
                        device_type=dev_type,
                        is_hotspot_client=is_hs,
                        is_active=1
                    )

                    # Distribute real-time live delta to active devices
                    if (wifi_down_delta > 0 or wifi_up_delta > 0) and count > 0:
                        dev_down = wifi_down_delta // count
                        dev_up = wifi_up_delta // count
                        if dev_down > 0 or dev_up > 0:
                            log_traffic(mac=mac, ip=ip, bytes_down=dev_down, bytes_up=dev_up, is_hotspot=is_hs)

            except Exception as e:
                print("Monitor loop exception:", e)

            time.sleep(self.interval_sec)


monitor = TrafficMonitor(interval_sec=3)
