"""
WiFi & Hotspot Data Analyzer - Network Scanner
Discovers devices on Wi-Fi and Hotspot via ARP, NetNeighbor, and Subnet Probing.
Resolves MAC vendors and hostnames.
"""

import subprocess
import socket
import re
import ipaddress
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any

# Common MAC OUI vendor prefix dictionary for instant offline lookup
OUI_VENDORS = {
    "F4:96:34": "Samsung Electronics",
    "4C:1D:96": "Xiaomi Communications",
    "E0:AE:A2": "Huawei Technologies",
    "D0:C6:37": "Intel Corporate (Laptop)",
    "B8:27:EB": "Raspberry Pi",
    "DC:A6:32": "Raspberry Pi",
    "AC:DE:48": "Apple",
    "BC:D0:74": "Apple",
    "3C:06:30": "Apple",
    "9C:20:7B": "Apple",
    "FC:EC:DA": "Apple",
    "A4:83:E7": "Apple",
    "70:EE:50": "Apple",
    "50:C7:BF": "TP-Link Corporation",
    "00:0C:29": "VMware",
    "00:50:56": "VMware",
    "00:15:5D": "Microsoft Hyper-V",
    "74:D4:35": "Giga-Byte Technology",
    "30:9C:23": "Samsung Electronics",
    "44:00:10": "Samsung Electronics",
    "60:A4:4C": "OnePlus / Oppo",
    "94:65:2D": "OnePlus / Oppo",
    "58:24:29": "Google Pixel",
    "40:4E:36": "Google",
    "64:16:66": "Realtek Semiconductor"
}


def lookup_vendor(mac: str) -> str:
    cleaned = mac.upper().replace("-", ":")
    prefix = ":".join(cleaned.split(":")[:3]) if len(cleaned.split(":")) >= 3 else ""
    return OUI_VENDORS.get(prefix, "Network Device")


def guess_device_type(vendor: str, hostname: str) -> str:
    combined = f"{vendor} {hostname}".lower()
    if any(k in combined for k in ["samsung", "xiaomi", "redmi", "apple", "iphone", "pixel", "oneplus", "oppo", "vivo", "android", "galaxy"]):
        return "Mobile Phone"
    elif any(k in combined for k in ["intel", "dell", "hp", "lenovo", "asus", "acer", "desktop", "laptop", "pc", "macbook"]):
        return "Laptop / PC"
    elif any(k in combined for k in ["router", "gateway", "huawei", "tp-link", "cisco", "netgear", "d-link"]):
        return "Router / AP"
    return "Network Client"


def get_local_network_info() -> Dict[str, Any]:
    """Finds active local IP, Wi-Fi adapter name and subnet."""
    local_ip = "127.0.0.1"
    gateway = None
    adapter_name = "Wi-Fi"
    ssid = "Unknown"

    try:
        # Get active IP connected to internet
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        pass

    try:
        # Get SSID from netsh
        out = subprocess.check_output("netsh wlan show interfaces", shell=True, text=True, errors="ignore")
        ssid_match = re.search(r"^\s*SSID\s*:\s*(.+)$", out, re.MULTILINE)
        if ssid_match:
            ssid = ssid_match.group(1).strip()
    except Exception:
        pass

    # Determine subnet based on local_ip
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


def resolve_hostname(ip: str) -> str:
    orig_timeout = socket.getdefaulttimeout()
    try:
        socket.setdefaulttimeout(0.3)
        host, _, _ = socket.gethostbyaddr(ip)
        return host
    except Exception:
        return ""
    finally:
        socket.setdefaulttimeout(orig_timeout)


def ping_host(ip: str):
    """Pings a single IP with 1 packet, fast timeout (250ms)."""
    try:
        subprocess.run(
            ["ping", "-n", "1", "-w", "250", ip],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except Exception:
        pass


def probe_subnet_quickly(subnet_str: str, max_workers: int = 40):
    """Probes the first 30 common IPs in subnet to populate ARP table."""
    try:
        net = ipaddress.ip_network(subnet_str, strict=False)
        hosts = [str(ip) for ip in net.hosts()][:40]  # Probe top hosts quickly
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            executor.map(ping_host, hosts)
    except Exception:
        pass


def scan_devices() -> List[Dict[str, Any]]:
    """
    Scans network neighbors using PowerShell Get-NetNeighbor and arp -a.
    Returns list of discovered devices.
    """
    net_info = get_local_network_info()
    devices = []
    seen_macs = set()

    # 1. Try PowerShell Get-NetNeighbor (accurate on Windows)
    ps_cmd = (
        "Get-NetNeighbor -AddressFamily IPv4 | "
        "Where-Object { $_.State -ne 'Unreachable' -and $_.IPAddress -notlike '224.*' "
        "-and $_.IPAddress -notlike '239.*' -and $_.IPAddress -ne '255.255.255.255' } | "
        "Select-Object IPAddress, LinkLayerAddress, State, InterfaceAlias | "
        "ConvertTo-Json -Compress"
    )

    try:
        import json
        out = subprocess.check_output(["powershell", "-NoProfile", "-Command", ps_cmd], text=True, errors="ignore")
        if out.strip():
            parsed = json.loads(out)
            if isinstance(parsed, dict):
                parsed = [parsed]
            for item in parsed:
                ip = item.get("IPAddress", "").strip()
                mac = item.get("LinkLayerAddress", "").strip().upper()
                state = item.get("State", "")
                if ip and mac and mac != "FF-FF-FF-FF-FF-FF":
                    if mac not in seen_macs:
                        seen_macs.add(mac)
                        vendor = lookup_vendor(mac)
                        hostname = resolve_hostname(ip)
                        dev_type = guess_device_type(vendor, hostname)
                        devices.append({
                            "ip": ip,
                            "mac": mac,
                            "vendor": vendor,
                            "hostname": hostname or (f"Gateway ({vendor})" if ip == net_info.get("gateway") else f"Device-{ip.split('.')[-1]}"),
                            "device_type": "Gateway Router" if ip == net_info.get("gateway") else dev_type,
                            "is_active": 1 if state in ["Reachable", "Permanent", "Stale"] else 0
                        })
    except Exception:
        pass

    # 2. Fallback / supplement with arp -a
    try:
        arp_out = subprocess.check_output("arp -a", shell=True, text=True, errors="ignore")
        for line in arp_out.splitlines():
            line = line.strip()
            match = re.match(r"^(\d+\.\d+\.\d+\.\d+)\s+([0-9a-fA-F-]+)\s+(\w+)", line)
            if match:
                ip, raw_mac, entry_type = match.groups()
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
                            "hostname": hostname or (f"Gateway ({vendor})" if ip == net_info.get("gateway") else f"Device-{ip.split('.')[-1]}"),
                            "device_type": "Gateway Router" if ip == net_info.get("gateway") else dev_type,
                            "is_active": 1
                        })
    except Exception:
        pass

    return devices
