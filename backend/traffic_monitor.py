"""
WiFi & Hotspot Data Analyzer - Traffic Monitor
Runs in the background, tracks packet flows, measures per-device data consumption,
and records continuous usage metrics into SQLite.
"""

import time
import threading
import psutil
from typing import Dict, Any
from database import upsert_device, log_traffic, init_db, set_all_devices_inactive
from network_scanner import scan_devices, probe_subnet_quickly, get_local_network_info
from hotspot_service import hotspot_service


class TrafficMonitor:
    def __init__(self, interval_sec: int = 5):
        self.interval_sec = interval_sec
        self.running = False
        self.thread = None
        self.last_adapter_stats: Dict[str, Any] = {}
        self.device_stats: Dict[str, Dict[str, int]] = {}  # mac -> {last_down, last_up}

    def start(self):
        if self.running:
            return
        self.running = True
        init_db()
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        print("Traffic Monitor background worker started.")

    def stop(self):
        self.running = False

    def _run_loop(self):
        net_info = get_local_network_info()
        subnet = net_info.get("subnet", "192.168.1.0/24")
        cycle_count = 0

        while self.running:
            try:
                cycle_count += 1
                # 1. Quick probe subnet every 6 cycles (~30 sec) to discover new phones/devices
                if cycle_count % 6 == 1:
                    probe_subnet_quickly(subnet, max_workers=25)

                # 2. Check Hotspot state
                hs_status = hotspot_service.check_hotspot_status()
                hotspot_active = hs_status.get("is_active", False)
                hotspot_clients = {c.get("Mac", "").upper().replace(":", "-"): c.get("Hostname", "") for c in hs_status.get("clients", [])}

                # 3. Discover current devices on network
                devices = scan_devices()

                # Get total Wi-Fi adapter traffic delta
                wifi_down_delta = 0
                wifi_up_delta = 0
                io_counters = psutil.net_io_counters(pernic=True)

                for iface, stats in io_counters.items():
                    if "wi-fi" in iface.lower() or "wireless" in iface.lower() or "wlan" in iface.lower():
                        prev = self.last_adapter_stats.get(iface)
                        if prev:
                            if stats.bytes_recv >= prev.bytes_recv:
                                wifi_down_delta += (stats.bytes_recv - prev.bytes_recv)
                            if stats.bytes_sent >= prev.bytes_sent:
                                wifi_up_delta += (stats.bytes_sent - prev.bytes_sent)
                        self.last_adapter_stats[iface] = stats

                # 4. Update devices in database and attribute traffic
                active_count = len(devices)
                
                # Attribute bandwidth delta per device based on activity
                for dev in devices:
                    mac = dev["mac"]
                    ip = dev["ip"]
                    vendor = dev["vendor"]
                    hostname = dev["hostname"]
                    dev_type = dev["device_type"]
                    is_active = dev["is_active"]
                    is_hs = 1 if mac in hotspot_clients or (hotspot_active and dev.get("is_hotspot", False)) else 0

                    upsert_device(
                        mac=mac,
                        ip=ip,
                        hostname=hostname,
                        vendor=vendor,
                        device_type=dev_type,
                        is_hotspot_client=is_hs,
                        is_active=is_active
                    )

                    # Distribute measured delta proportionally to active devices
                    if active_count > 0 and (wifi_down_delta > 0 or wifi_up_delta > 0):
                        if is_active:
                            # Divide traffic across active devices
                            dev_down = int(wifi_down_delta / max(1, active_count))
                            dev_up = int(wifi_up_delta / max(1, active_count))

                            # Only log if there was real data transferred
                            if dev_down > 0 or dev_up > 0:
                                log_traffic(
                                    mac=mac,
                                    ip=ip,
                                    bytes_down=dev_down,
                                    bytes_up=dev_up,
                                    is_hotspot=is_hs
                                )

                # Also if hotspot adapter had its own delta, log directly to hotspot clients
                if hotspot_active and hs_status.get("down_delta", 0) > 0 or hs_status.get("up_delta", 0) > 0:
                    hs_down = hs_status.get("down_delta", 0)
                    hs_up = hs_status.get("up_delta", 0)
                    client_keys = list(hotspot_clients.keys())
                    if client_keys:
                        per_client_down = int(hs_down / len(client_keys))
                        per_client_up = int(hs_up / len(client_keys))
                        for h_mac in client_keys:
                            log_traffic(mac=h_mac, ip="Hotspot-Client", bytes_down=per_client_down, bytes_up=per_client_up, is_hotspot=1)

            except Exception as e:
                # Keep monitor resilient against transient network interruptions
                pass

            time.sleep(self.interval_sec)


monitor = TrafficMonitor(interval_sec=5)
