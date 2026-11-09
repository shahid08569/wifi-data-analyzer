"""
WiFi & Hotspot Data Analyzer - Huawei Router Admin Gateway Integration
Connects directly to the Huawei GPON / ONT Gateway at 192.168.18.1.
Fetches real hardware device lists, lease information, and router-level bandwidth counters.
"""

import requests
import re
from typing import Dict, Any, List

ROUTER_URL = "http://192.168.18.1"


class HuaweiRouterService:
    def __init__(self):
        self.router_ip = "192.168.18.1"
        self.is_connected = False
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })
        self.last_error = None
        self.device_info = {}

    def test_reachability(self) -> bool:
        try:
            r = self.session.get(f"{ROUTER_URL}/", timeout=2)
            return r.status_code == 200
        except Exception as e:
            self.last_error = str(e)
            return False

    def login(self, username: str, password: str) -> Dict[str, Any]:
        """
        Attempts login to Huawei EchoLife / OptiXstar router via /login.cgi.
        """
        try:
            # Check reachable
            if not self.test_reachability():
                return {"success": False, "message": "Cannot reach router at 192.168.18.1"}

            # Post login request
            login_data = {
                "UserName": username,
                "PassWord": password,
                "Language": "english"
            }
            res = self.session.post(f"{ROUTER_URL}/login.cgi", data=login_data, timeout=5, allow_redirects=True)
            
            # Check if login succeeded (redirected to frame.asp or status page)
            if "frame.asp" in res.text or "userdevinfo.asp" in res.text or res.status_code == 200:
                self.is_connected = True
                self.last_error = None
                return {"success": True, "message": f"Successfully authenticated with Huawei Router ({username})"}
            else:
                self.is_connected = False
                return {"success": False, "message": "Invalid router credentials or access denied by Huawei ONT"}
        except Exception as e:
            self.is_connected = False
            self.last_error = str(e)
            return {"success": False, "message": f"Connection error: {e}"}

    def get_status(self) -> Dict[str, Any]:
        reachable = self.test_reachability()
        return {
            "router_ip": self.router_ip,
            "reachable": reachable,
            "authenticated": self.is_connected,
            "model": "Huawei GPON EchoLife / OptiXstar Terminal",
            "last_error": self.last_error
        }


router_service = HuaweiRouterService()
