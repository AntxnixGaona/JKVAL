from collections import Counter
from typing import List, Dict, Any

def calculate_stats(matches: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate player statistics from match data"""
    
    # Initialize counters
    total_kills = 0
    total_deaths = 0
    total_assists = 0
    total_hs = 0
    total_matches = len(matches)
    wins = 0
    agent_counts = Counter()
    
    # Process matches
    for match in matches:
        # Add to totals
        total_kills += match.get('kills', 0)
        total_deaths += match.get('deaths', 0)
        total_assists += match.get('assists', 0)
        total_hs += match.get('hs_percent', 0)
        
        # Count wins
        if match.get('result') == 'Victory':
            wins += 1
            
        # Count agents
        agent = match.get('agent')
        if agent:
            agent_counts[agent] += 1
    
    # Calculate K/D ratio
    kd_ratio = total_kills / total_deaths if total_deaths > 0 else total_kills
    
    # Calculate headshot percentage
    avg_hs_percent = total_hs / total_matches if total_matches > 0 else 0
    
    # Calculate win rate
    winrate = (wins / total_matches) * 100 if total_matches > 0 else 0
    
    # Get top 3 agents
    top_agents = []
    for agent, count in agent_counts.most_common(3):
        top_agents.append({
            'name': agent,
            'plays': count
        })
    
    return {
        'kd': kd_ratio,
        'hs_percent': avg_hs_percent,
        'winrate': winrate,
        'top_agents': top_agents
    }