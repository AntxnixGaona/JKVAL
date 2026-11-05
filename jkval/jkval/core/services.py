"""
Services for the core app.
"""
import gzip
import json
import os
from pathlib import Path
from datetime import datetime
import math
from django.conf import settings
from typing import Dict, List, Any, Optional
import random

class DemoService:
    """Service for loading and filtering demo data."""
    
    def __init__(self):
        self._demo_data = None
        self._metadata = None
        self.data_path = Path(__file__).resolve().parent.parent.parent.parent.parent.parent / 'data' / 'demo'
        self.matches_path = self.data_path / 'matches.json.gz'
        self.meta_path = self.data_path / 'meta.json'
    
    def load_demo_data(self) -> Dict[str, Any]:
        """Load demo data from gzip file."""
        if self._demo_data is not None:
            return self._demo_data
        
        try:
            with gzip.open(self.matches_path, 'rt', encoding='utf-8') as f:
                self._demo_data = json.load(f)
            return self._demo_data
        except Exception:
            # If file doesn't exist, create a minimal structure
            self._demo_data = {
                'matches': [],
                'agents': [],
                'compositions': [],
                'maps': []
            }
            return self._demo_data
    
    def load_metadata(self) -> Dict[str, Any]:
        """Load metadata from JSON file."""
        if self._metadata is not None:
            return self._metadata
        
        try:
            with open(self.meta_path, 'r', encoding='utf-8') as f:
                self._metadata = json.load(f)
            return self._metadata
        except Exception:
            # Create default metadata
            self._metadata = {
                'dataset': 'demo-v1',
                'seed': 20261028,
                'generated_at': datetime.now().isoformat(),
                'source': 'JKVAL DemoProvider (sintético)',
                'label': 'DEMO · Datos ficticios',
                'method': 'Generado sintéticamente para demostración',
                'published_at': datetime.now().isoformat(),
                'coverage': {
                    'modes': ['competitive', 'unrated', 'swiftplay', 'deathmatch'],
                    'ranks': ['Ascendente', 'Inmortal', 'Radiante'],
                    'regions': ['LATAM', 'NA', 'EU', 'APAC'],
                    'acts': ['V26 A3', 'V26 A2'],
                    'patches': ['13.09', '13.08', '13.07']
                },
                'thresholds': {
                    'agent': 200,
                    'composition': 500
                },
                'notas': 'Estos datos no se actualizan automáticamente. Son datos sintéticos para demostración.'
            }
            return self._metadata
    
    def get_overview(self) -> Dict[str, Any]:
        """Get overview data for the home page."""
        data = self.load_demo_data()
        
        # Calculate top agents by picks
        agents = []
        for agent in data.get('agents', []):
            agents.append(agent)
        
        agents.sort(key=lambda x: x.get('picks', 0), reverse=True)
        
        # Calculate top compositions by wins
        compositions = []
        for comp in data.get('compositions', []):
            compositions.append(comp)
        
        compositions.sort(key=lambda x: x.get('wins', 0), reverse=True)
        
        return {
            'agents': agents[:5],
            'compositions': compositions[:5]
        }
    
    def filter_demo_data(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Filter demo data based on query parameters."""
        data = self.load_demo_data()
        
        # Apply filters to matches
        filtered_matches = []
        for match in data.get('matches', []):
            # Apply mode filter
            if filters.get('mode') != 'all' and match.get('mode') != filters['mode']:
                continue
            
            # Apply rank filter
            if filters.get('rank') and filters['rank'] != 'all':
                if filters['rank'] != 'No aplica' and match.get('rank') != filters['rank']:
                    continue
            
            # Apply region filter
            if filters.get('region') != 'all' and match.get('region') != filters['region']:
                continue
            
            # Apply act filter
            if filters.get('act') != 'all' and match.get('act') != filters['act']:
                continue
            
            # Apply patch filter
            if filters.get('patch') != 'all' and match.get('patch') != filters['patch']:
                continue
            
            # Apply map filter
            if filters.get('map') != 'all' and match.get('map') != filters['map']:
                continue
            
            filtered_matches.append(match)
        
        # Recalculate agents and compositions based on filtered matches
        agents_stats = self._calculate_agent_stats(filtered_matches, filters)
        compositions_stats = self._calculate_composition_stats(filtered_matches, filters)
        
        # Apply sorting
        if filters.get('sort') == 'winrate':
            agents_stats.sort(key=lambda x: x.get('win_rate', 0), reverse=True)
            compositions_stats.sort(key=lambda x: x.get('win_rate', 0), reverse=True)
        else:  # picks (default)
            agents_stats.sort(key=lambda x: x.get('picks', 0), reverse=True)
            compositions_stats.sort(key=lambda x: x.get('picks', 0), reverse=True)
        
        return {
            'matches': filtered_matches,
            'agents': agents_stats,
            'compositions': compositions_stats,
            'maps': self._get_maps(filtered_matches, filters)
        }
    
    def _calculate_agent_stats(self, matches: List[Dict[str, Any]], filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Calculate agent statistics from matches."""
        agent_stats = {}
        
        for match in matches:
            for pick in match.get('picks', []):
                agent_name = pick.get('agent')
                team = pick.get('team')
                
                if agent_name not in agent_stats:
                    agent_stats[agent_name] = {
                        'agent': agent_name,
                        'picks': 0,
                        'wins': 0,
                        'win_rate': 0,
                        'wilson_lower': 0,
                        'wilson_upper': 0,
                        'insufficient': False
                    }
                
                agent_stats[agent_name]['picks'] += 1
                
                # Check if this agent was on the winning team
                if pick.get('team') == match.get('winner'):
                    agent_stats[agent_name]['wins'] += 1
        
        # Calculate win rates and Wilson intervals
        for agent_name, stats in agent_stats.items():
            if stats['picks'] > 0:
                stats['win_rate'] = (stats['wins'] / stats['picks']) * 100
                
                # Wilson interval calculation
                stats['wilson_lower'], stats['wilson_upper'] = self._wilson_interval(
                    stats['wins'], stats['picks']
                )
                
                # Check if sample is sufficient
                stats['insufficient'] = stats['picks'] < settings.get('AGENT_THRESHOLD', 200)
        
        return list(agent_stats.values())
    
    def _calculate_composition_stats(self, matches: List[Dict[str, Any]], filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Calculate composition statistics from matches."""
        composition_stats = {}
        
        for match in matches:
            comp_a = match.get('comp_a')
            comp_b = match.get('comp_b')
            
            for comp_name, comp in [('A', comp_a), ('B', comp_b)]:
                if not comp:
                    continue
                
                if comp not in composition_stats:
                    composition_stats[comp] = {
                        'composition': comp,
                        'uses': 0,
                        'wins': 0,
                        'win_rate': 0,
                        'wilson_lower': 0,
                        'wilson_upper': 0,
                        'insufficient': False
                    }
                
                composition_stats[comp]['uses'] += 1
                
                # Check if this composition was on the winning team
                if comp_name == match.get('winner'):
                    composition_stats[comp]['wins'] += 1
        
        # Calculate win rates and Wilson intervals
        for comp_name, stats in composition_stats.items():
            if stats['uses'] > 0:
                stats['win_rate'] = (stats['wins'] / stats['uses']) * 100
                
                # Wilson interval calculation
                stats['wilson_lower'], stats['wilson_upper'] = self._wilson_interval(
                    stats['wins'], stats['uses']
                )
                
                # Check if sample is sufficient
                stats['insufficient'] = stats['uses'] < settings.get('COMPOSITION_THRESHOLD', 500)
        
        return list(composition_stats.values())
    
    def _get_maps(self, matches: List[Dict[str, Any]], filters: Dict[str, Any]) -> List[str]:
        """Get unique maps from matches."""
        maps = set()
        for match in matches:
            if match.get('map'):
                maps.add(match['map'])
        return sorted(list(maps))
    
    def _wilson_interval(self, successes: int, trials: int, confidence: float = 0.95) -> tuple:
        """Calculate Wilson score interval for binomial proportion."""
        if trials == 0:
            return (0.0, 0.0)
        
        z = 1.96  # For 95% confidence
        p = successes / trials
        denominator = 1 + (z ** 2) / trials
        centre = (p + (z ** 2) / (2 * trials)) / denominator
        adjustment = (z * math.sqrt((p * (1 - p) + (z ** 2) / (4 * trials)) / trials)) / denominator
        
        lower = centre - adjustment
        upper = centre + adjustment
        
        return max(0.0, lower), min(1.0, upper)
    
    def get_metadata(self) -> Dict[str, Any]:
        """Get metadata."""
        return self.load_metadata()