import random
from typing import Dict, Any

class MockProvider:
    """Datos sintéticos de desarrollo. No se usa como fallback del tracker."""
    
    def get_account(self, name: str, tag: str) -> Dict[Any, Any]:
        """Return mock account data"""
        return {
            "data": {
                "name": name,
                "tag": tag,
                "puuid": "mock-puuid-12345",
                "created": "2023-01-01T00:00:00Z"
            }
        }
    
    def get_mmr(self, name: str, tag: str) -> Dict[Any, Any]:
        """Return mock MMR data"""
        tiers = ["Unranked", "Iron 1", "Iron 2", "Iron 3", "Bronze 1", "Bronze 2", 
                 "Bronze 3", "Silver 1", "Silver 2", "Silver 3", "Gold 1", "Gold 2", 
                 "Gold 3", "Platinum 1", "Platinum 2", "Platinum 3", "Diamond 1", 
                 "Diamond 2", "Diamond 3", "Ascendant 1", "Ascendant 2", "Ascendant 3", 
                 "Immortal 1", "Immortal 2", "Immortal 3", "Radiant"]
        
        return {
            "data": {
                "currenttier": random.choice(tiers),
                "currenttierpatched": random.choice(tiers),
                "mmr_change_to_last_tier": random.randint(-50, 50),
                "leaderboard_rank": random.randint(1, 10000),
                "ranked_rating": random.randint(0, 2000)
            }
        }
    
    def get_matches(self, name: str, tag: str) -> Dict[Any, Any]:
        """Return mock match data"""
        maps = ["Bind", "Haven", "Split", "Ascent", "Icebox", "Breeze", "Fracture"]
        modes = ["Competitive", "Unrated", "Deathmatch"]
        agents = ["Jett", "Omen", "Sova", "Killjoy", "Reyna", "Phoenix", "Cypher", "Breach"]
        
        matches = []
        for i in range(10):
            match = {
                "map": random.choice(maps),
                "mode": random.choice(modes),
                "kills": random.randint(0, 20),
                "deaths": random.randint(0, 20),
                "assists": random.randint(0, 10),
                "hs_percent": random.randint(0, 100),
                "result": random.choice(["Victory", "Defeat"]),
                "agent": random.choice(agents)
            }
            matches.append(match)
        
        return matches