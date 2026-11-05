"""
Views for the core app.
"""
import json
import gzip
from pathlib import Path
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET
from django.views.decorators.cache import never_cache
import random

from .services import DemoService
# Store the random tier per session
random_tiers = {}


def get_random_tier():
    """Get a random tier and store it in session."""
    tiers = ['Ascendente', 'Inmortal', 'Radiante']
    tier = random.choice(tiers)
    return tier


def home(request):
    """Home page with featured tier, top agents and compositions."""
    # Get or create random tier for this session
    session_key = request.session.session_key
    if not session_key:
        request.session.create()
    
    if session_key not in random_tiers:
        random_tiers[session_key] = get_random_tier()
    
    featured_tier = random_tiers[session_key]
    
    # Get top 5 agents and compositions
    demo_service = DemoService()
    data = demo_service.get_overview()
    
    # Get filtered data for competitive mode
    filters = {
        'mode': 'competitive',
        'rank': featured_tier,
        'region': 'all',
        'act': 'latest',
        'patch': 'latest',
        'map': 'all'
    }
    
    filtered_data = demo_service.filter_demo_data(filters)
    
    context = {
        'featured_tier': featured_tier,
        'top_agents': filtered_data.get('agents', [])[:5],
        'top_compositions': filtered_data.get('compositions', [])[:5],
        'demo_mode': settings.DEMO_MODE,
        'feature_riot_rso': settings.FEATURE_RIOT_RSO,
        'current_filters': filters,
    }
    
    return render(request, 'core/home.html', context)


@require_GET
@never_cache
def stats_api(request):
    """API endpoint for statistics data with filtering."""
    demo_service = DemoService()
    
    # Parse query parameters
    filters = {}
    
    # Allowed filter parameters
    allowed_filters = ['mode', 'rank', 'region', 'act', 'patch', 'map', 'sort']
    
    for param in allowed_filters:
        if param in request.GET:
            filters[param] = request.GET[param]
    
    # Set defaults if not provided
    if 'mode' not in filters:
        filters['mode'] = 'competitive'
    if 'region' not in filters:
        filters['region'] = 'all'
    if 'act' not in filters:
        filters['act'] = 'latest'
    if 'patch' not in filters:
        filters['patch'] = 'latest'
    if 'map' not in filters:
        filters['map'] = 'all'
    if 'sort' not in filters:
        filters['sort'] = 'picks'
    
    # Handle rank filtering - if not competitive mode, set to 'No aplica'
    if filters['mode'] != 'competitive' and 'rank' not in filters:
        filters['rank'] = 'No aplica'
    
    # Handle deathmatch mode - no winrate, maps, or compositions
    if filters['mode'] == 'deathmatch':
        filters['rank'] = 'No aplica'
        filters['map'] = 'No aplica'
        filters['sort'] = 'picks'
    
    # Apply filters
    filtered_data = demo_service.filter_demo_data(filters)
    
    # Get metadata
    metadata = demo_service.get_metadata()
    
    # Get server timestamp
    from django.utils import timezone
    last_checked_at = timezone.now().isoformat()
    
    response_data = {
        'data': filtered_data,
        'metadata': metadata,
        'filters_applied': filters,
        'server_timestamp': last_checked_at,
        'source': metadata.get('source', 'DEMO · Datos ficticios'),
        'status': 'demo',
        'coverage_notes': {
            'agent_threshold': '200 picks',
            'composition_threshold': '500 usos',
        }
    }
    
    return JsonResponse(response_data)


# Basic placeholder pages
@never_cache
def sources(request):
    """Sources page."""
    return render(request, 'core/sources.html')


@never_cache
def privacy(request):
    """Privacy page."""
    return render(request, 'core/privacy.html')


@never_cache
def terms(request):
    """Terms page."""
    return render(request, 'core/terms.html')


@never_cache
def legal_notice(request):
    """Legal notice page."""
    return render(request, 'core/legal_notice.html')


@never_cache
def guides(request):
    """Guides page (placeholder)."""
    return render(request, 'core/guides.html')


@never_cache
def stats(request):
    """Stats page (placeholder)."""
    return render(request, 'core/stats.html')


@never_cache
def profiles(request):
    """Profiles page (placeholder)."""
    return render(request, 'core/profiles.html')


@never_cache
def aim_trainer(request):
    """Aim trainer page (placeholder)."""
    return render(request, 'core/aim_trainer.html')


@require_GET
def health(request):
    """Health check endpoint."""
    return JsonResponse({
        'status': 'healthy',
        'timestamp': timezone.now().isoformat(),
        'demo_mode': settings.DEMO_MODE,
    })