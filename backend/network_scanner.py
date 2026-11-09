"""
WiFi & Hotspot Data Analyzer - High-Performance Layer-2 Network Scanner
Uses Windows Win32 SendARP API and multi-threading to bypass mobile firewalls 
and discover every device (phones, laptops, routers) on the local subnet.
"""

import subprocess
import socket
import struct
import ctypes
import re
import ipaddress
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any

# Windows Win32 API for Layer-2 hardware ARP resolution
try:
    send_arp = ctypes.windll.Iphlpapi.SendARP
except Exception:
    send_arp = None

# Comprehensive MAC OUI Vendor Prefix Database
OUI_VENDORS = {
    "F4:96:34": "Samsung Electronics",
    "30:9C:23": "Samsung Electronics",
    "44:00:10": "Samsung Electronics",
    "4C:1D:96": "Xiaomi Communications",
    "E0:AE:A2": "Huawei Technologies",
    "D0:C6:37": "Intel Corporate",
    "A4:E8:8D": "Intel Corporate",
    "C4:86:E9": "Realtek / OEM Device",
    "A8:6D:AA": "Apple",
    "AC:DE:48": "Apple",
    "BC:D0:74": "Apple",
    "3C:06:30": "Apple",
    "9C:20:7B": "Apple",
    "FC:EC:DA": "Apple",
    "A4:83:E7": "Apple",
    "70:EE:50": "Apple",
    "60:A4:4C": "OnePlus / Oppo",
    "94:65:2D": "OnePlus / Oppo",
    "58:24:29": "Google Pixel",
    "40:4E:36": "Google",
    "50:C7:BF": "TP-Link Corporation",
    "00:0C:29": "VMware Virtual Device",
    "B8:27:EB": "Raspberry Pi",
    "DC:A6:32": "Raspberry Pi"
}


def lookup_vendor(mac: str) -> str:
    cleaned = mac.upper().replace("-", ":")
    parts = cleaned.split(":")
    if len(parts) >= 3:
        prefix = ":".join(parts[:3])
        if prefix in OUI_VENDORS:
            return OUI_VENDORS[prefix]
    # Check if MAC has locally administered bit set (randomized MAC used by modern iOS/Android)
    try:
        first_byte = int(parts[0], 16)
        if first_byte & 0x02:
            return "Private / Randomized MAC (Mobile)"
    except Exception:
        pass
    return "Network Client"


def guess_device_type(vendor: str, hostname: str) -> str:
    combined = f"{vendor} {hostname}".lower()
    if any(k in combined for k in ["samsung", "xiaomi", "redmi", "apple", "iphone", "pixel", "oneplus", "oppo", "vivo", "android", "galaxy", "mobile", "randomized"]):
        return "Mobile Phone"
    elif any(k in combined for k in ["intel", "dell", "hp", "lenovo", "asus", "acer", "desktop", "laptop", "pc", "macbook", "win-"]):
        return "Laptop / PC"
    elif any(k in combined for k in ["router", "gateway", "huawei", "tp-link", "cisco", "netgear", "d-link"]):
        return "Gateway Router"
    return "Network Device"


def get_local_network_info() -> Dict[str, Any]:
    local_ip = "127.0.0.1"
    gateway = None
    adapter_name = "Wi-Fi"
    ssid = "Unknown"

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        pass

    try:
        out = subprocess.check_output("netsh wlan show interfaces", shell=True, text=True, errors="ignore")
        ssid_match = re.search(r"^\s*SSID\s*:\s*(.+)$", out, re.MULTILINE)
        if ssid_match:
            ssid = ssid_match.group(1).strip()
    except Exception:
        pass

    subnet = "192.168.1.0/24"
    if local_ip != "127.0.0.1":
        parts = local_ip.split(".")
        subnet = f"{parts[0]}.{parts[1]}.{parts[2]}.0/24"
        gateway = f"{parts[0]}.{parts[1]}.{parts[2]}.1"

    return {
        "local_ip": local_ip,
        "gateway": gateway,
        "ssid": ssid,
        "adapter_name": adapter_name,
        "subnet": subnet
    }


def probe_subnet_quickly(subnet_str: str = "", max_workers: int = 80):
    """Alias for subnet sweep."""
    return scan_devices()


def resolve_hostname(ip: str) -> str:
    orig_timeout = socket.getdefaulttimeout()
    try:
        socket.setdefaulttimeout(0.35)
        host, _, _ = socket.gethostbyaddr(ip)
        return host.split(".")[0]
    except Exception:
        return ""
    finally:
        socket.setdefaulttimeout(orig_timeout)


def query_arp_ip(ip: str):
    """Direct Layer-2 ARP request to an IP. Returns (ip, mac) if device is connected."""
    if not send_arp:
        return None
    try:
        dest_ip = struct.unpack('<I', socket.inet_aton(ip))[0]
        mac_addr = (ctypes.c_ubyte * 6)()
        mac_len = ctypes.c_ulong(6)
        res = send_arp(dest_ip, 0, ctypes.byref(mac_addr), ctypes.byref(mac_len))
        if res == 0:
            mac_str = '-'.join(f'{b:02X}' for b in mac_addr[:6])
            if mac_str not in ["00-00-00-00-00-00", "FF-FF-FF-FF-FF-FF"]:
                return ip, mac_str
    except Exception:
        pass
    return None


def scan_devices() -> List[Dict[str, Any]]:
    """
    Performs full Layer-2 ARP sweep across all 254 subnet hosts using 80 parallel threads.
    Bypasses mobile firewalls and returns every active phone/laptop.
    """
    net_info = get_local_network_info()
    local_ip = net_info.get("local_ip", "127.0.0.1")
    gateway = net_info.get("gateway", "192.168.18.1")
    
    parts = local_ip.split(".")
    base = f"{parts[0]}.{parts[1]}.{parts[2]}" if len(parts) == 4 else "192.168.18"
    ips = [f"{base}.{i}" for i in range(1, 255)]

    devices = []
    seen_macs = set()

    # 1. High-speed Layer-2 SendARP multi-threaded sweep
    with ThreadPoolExecutor(max_workers=80) as executor:
        results = list(filter(None, executor.map(query_arp_ip, ips)))

    for ip, mac in results:
        seen_macs.add(mac)
        vendor = lookup_vendor(mac)
        hostname = resolve_hostname(ip)
        dev_type = guess_device_type(vendor, hostname)

        if ip == gateway:
            dev_type = "Gateway Router"
            name = f"Router Gateway ({vendor})"
        elif ip == local_ip:
            dev_type = "Laptop / Host PC"
            name = f"My Laptop ({hostname or 'Local'})"
        else:
            name = hostname or f"{dev_type} ({vendor})"

        devices.append({
            "ip": ip,
            "mac": mac,
            "vendor": vendor,
            "hostname": name,
            "device_type": dev_type,
            "is_active": 1
        })

    # 2. Also check Windows ARP cache and NetNeighbor for any cached entries
    try:
        arp_out = subprocess.check_output("arp -a", shell=True, text=True, errors="ignore")
        for line in arp_out.splitlines():
            m = re.match(r"^\s*(\d+\.\d+\.\d+\.\d+)\s+([0-9a-fA-F-]+)\s+(\w+)", line)
            if m:
                ip, raw_mac, _ = m.groups()
                mac = raw_mac.upper().replace(":", "-")
                if not (ip.startswith("224.") or ip.startswith("239.") or ip.endswith(".255") or mac == "FF-FF-FF-FF-FF-FF"):
                    if mac not in seen_macs:
                        seen_macs.add(mac)
                        vendor = lookup_vendor(mac)
                        hostname = resolve_hostname(ip)
                        dev_type = guess_device_type(vendor, hostname)
                        devices.append({
                            "ip": ip,
                            "mac": mac,
                            "vendor": vendor,
                            "hostname": hostname or f"{dev_type} ({vendor})",
                            "device_type": dev_type,
                            "is_active": 1
                        })
    except Exception:
        pass

    return devices
