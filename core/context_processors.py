from django.conf import settings


def site_context(request):
    return {
        "site_name": "JKVAL",
        "demo_mode": settings.DEMO_MODE,
        "feature_riot_rso": settings.FEATURE_RIOT_RSO,
        "current_year": 2026,
    }
