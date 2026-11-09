"""
WiFi & Hotspot Data Analyzer - Hotspot Service
Monitors Windows Mobile Hotspot state, active duration, data consumption, and connected clients.
"""

import subprocess
import json
import psutil
from typing import Dict, Any, List
from database import start_or_update_hotspot_session


class HotspotService:
    def __init__(self):
        self.is_active = False
        self.client_count = 0
        self.hotspot_adapter_name = None
        self.last_bytes_down = 0
        self.last_bytes_up = 0
        self.clients_list = []

    def check_hotspot_status(self) -> Dict[str, Any]:
        """
        Queries Windows to check if Mobile Hotspot is enabled and get connected clients.
        """
        # 1. Check network adapters for Wi-Fi Direct or Virtual Adapter
        is_on = False
        client_count = 0
        clients = []
        adapter_name = None

        ps_script = """
        $res = @{ IsActive = $false; ClientCount = 0; AdapterName = ''; Clients = @() }
        
        # Check adapters for virtual/direct adapters
        $adapters = Get-NetAdapter | Where-Object { 
            ($_.InterfaceDescription -like '*Wi-Fi Direct*' -or $_.Name -like '*Local Area Connection**' -or $_.Name -like '*Hotspot*') -and $_.Status -eq 'Up' 
        }
        
        if ($adapters) {
            $res.IsActive = $true
            $res.AdapterName = $adapters[0].Name
        }
        
        # Check TetheringManager via WinRT
        try {
            [Windows.Networking.Connectivity.NetworkInformation, Windows.Networking.Connectivity, ContentType = WindowsRuntime] | Out-Null
            $p = [Windows.Networking.Connectivity.NetworkInformation]::GetInternetConnectionProfile()
            if ($p) {
                [Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager, Windows.Networking.NetworkOperators, ContentType = WindowsRuntime] | Out-Null
                $tm = [Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager]::CreateFromConnectionProfile($p)
                if ($tm.TetheringOperationalState -eq [Windows.Networking.NetworkOperators.TetheringOperationalState]::On) {
                    $res.IsActive = $true
                    $res.ClientCount = $tm.ClientCount
                    $tClients = $tm.GetTetheringClients()
                    foreach ($c in $tClients) {
                        $res.Clients += @{ Mac = $c.MacAddress; Hostname = $c.HostName }
                    }
                }
            }
        } catch {}

        $res | ConvertTo-Json -Compress
        """

        try:
            out = subprocess.check_output(
                ["powershell", "-NoProfile", "-Command", ps_script],
                text=True, errors="ignore"
            )
            if out.strip():
                data = json.loads(out)
                is_on = bool(data.get("IsActive", False))
                client_count = int(data.get("ClientCount", 0))
                adapter_name = data.get("AdapterName", "")
                raw_clients = data.get("Clients", [])
                if isinstance(raw_clients, dict):
                    raw_clients = [raw_clients]
                clients = raw_clients
        except Exception:
            pass

        self.is_active = is_on
        self.client_count = client_count
        self.clients_list = clients
        self.hotspot_adapter_name = adapter_name

        # Calculate traffic delta if adapter is up
        down_delta = 0
        up_delta = 0

        if adapter_name:
            net_io = psutil.net_io_counters(pernic=True)
            if adapter_name in net_io:
                curr_down = net_io[adapter_name].bytes_recv
                curr_up = net_io[adapter_name].bytes_sent

                if self.last_bytes_down > 0 and curr_down >= self.last_bytes_down:
                    down_delta = curr_down - self.last_bytes_down
                if self.last_bytes_up > 0 and curr_up >= self.last_bytes_up:
                    up_delta = curr_up - self.last_bytes_up

                self.last_bytes_down = curr_down
                self.last_bytes_up = curr_up

        # Record or update hotspot session in SQLite
        start_or_update_hotspot_session(is_on, client_count, down_delta, up_delta)

        return {
            "is_active": is_on,
            "client_count": client_count,
            "clients": clients,
            "adapter_name": adapter_name,
            "down_delta": down_delta,
            "up_delta": up_delta
        }


hotspot_service = HotspotService()
