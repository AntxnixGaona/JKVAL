import requests
import time
from typing import Dict, Any, Optional

class ValorantAPI:
    def __init__(self):
        self.base_url = "https://api.henrikdev.xyz/valorant/v2"
        self.headers = {
            "Authorization": "HDEV-7a810c6a-ac34-4486-b7ff-5e7c9b78da70",
            "User-Agent": "JKVAL-App/1.0"
        }
        self.timeout = 10
    
    def get_account(self, name: str, tag: str) -> Optional[Dict[Any, Any]]:
        """Get player account information"""
        try:
            url = f"{self.base_url}/account/{name}/{tag}"
            response = requests.get(url, headers=self.headers, timeout=self.timeout)
            
            if response.status_code == 404:
                return None
            elif response.status_code != 200:
                response.raise_for_status()
                
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching account data: {e}")
            return None
    
    def get_mmr(self, name: str, tag: str) -> Optional[Dict[Any, Any]]:
        """Get player MMR information"""
        try:
            url = f"{self.base_url}/mmr/{name}/{tag}"
            response = requests.get(url, headers=self.headers, timeout=self.timeout)
            
            if response.status_code == 404:
                return None
            elif response.status_code != 200:
                response.raise_for_status()
                
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching MMR data: {e}")
            return None
    
    def get_matches(self, name: str, tag: str) -> Optional[Dict[Any, Any]]:
        """Get player match history"""
        try:
            url = f"{self.base_url}/matches/{name}/{tag}"
            response = requests.get(url, headers=self.headers, timeout=self.timeout)
            
            if response.status_code == 404:
                return None
            elif response.status_code != 200:
                response.raise_for_status()
                
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching matches data: {e}")
            return None