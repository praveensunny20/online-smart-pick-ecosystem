"""
Metric normalization layer.

Each marketing platform names its metrics differently:
    - Meta Ads calls engagement "Link Clicks"
    - Pinterest calls it "Pin Clicks"
    - Google Ads calls it "Clicks"

This module provides a central dict-driven mapping that converts platform-specific
field names into a UNIFIED vocabulary we store in unified_metrics_cache. Queries
and AI prompts can then compare apples to apples across all platforms.

To add a new platform or a new metric, just extend NORMALIZATION_RULES below.
"""
from __future__ import annotations

from typing import Any, Dict, List

from app.models import PlatformType


# ============================================================
# UNIFIED METRIC VOCABULARY
# ============================================================
# These are the canonical names we store in the `metric_name` column of
# unified_metrics_cache. Everything else in the system (queries, AI prompts,
# dashboards, reports) speaks this vocabulary.

UNIFIED_METRICS = {
    "impressions",          # How many times ads / content were shown
    "clicks",               # Any click — ad, link, pin, story tap
    "spend_usd",            # Money spent in USD (or reporting currency)
    "conversions",          # Goal completions (purchases, signups, etc.)
    "revenue_usd",          # Revenue attributed to campaigns
    "sessions",             # Website sessions (analytics only)
    "users",                # Unique users (analytics only)
    "bounce_rate",          # Fraction [0..1] of sessions that bounced
    "ctr",                  # Click-through rate [0..1]
    "cost_per_click",       # Spend / clicks
    "cost_per_conversion",  # Spend / conversions
    "roas",                 # Return on ad spend (revenue / spend)
    "engagements",          # Likes + comments + shares + saves
    "followers",            # Social follower count snapshot
    "reach",                # Unique accounts reached
}


# ============================================================
# PER-PLATFORM MAPPING RULES
# ============================================================
# Each platform maps its raw field names to our unified names.
# Keys on the left are field names you'd expect from the platform's API
# response (or from a mock/fixture row in the same shape).
#
# A list value means "any of these raw names maps to this unified metric" —
# useful because providers sometimes change field casing or include both
# a snake_case and a camelCase version.
#
# The `normalize_platform_row()` function below does the actual translation.

_NORMALIZATION_RULES: Dict[PlatformType, Dict[str, str]] = {
    # --- Meta Ads (Facebook + Instagram paid) ---
    PlatformType.META_ADS: {
        "impressions": "impressions",
        "reach": "reach",
        "link_clicks": "clicks",
        "clicks": "clicks",
        "spend": "spend_usd",
        "cost": "spend_usd",
        "conversions": "conversions",
        "purchase_value": "revenue_usd",
        "action_value": "revenue_usd",
        "ctr": "ctr",
        "cpc": "cost_per_click",
        "cost_per_conversion": "cost_per_conversion",
        "roas": "roas",
        "post_engagement": "engagements",
    },

    # --- Google Ads ---
    PlatformType.GOOGLE_ADS: {
        "impressions": "impressions",
        "clicks": "clicks",
        "cost_micros": "spend_usd",   # Google reports spend in micros (÷1_000_000)
        "cost": "spend_usd",
        "conversions": "conversions",
        "conversion_value": "revenue_usd",
        "ctr": "ctr",
        "average_cpc": "cost_per_click",
        "cpc": "cost_per_click",
        "cost_per_conversion": "cost_per_conversion",
        "roas": "roas",
    },

    # --- Google Analytics 4 ---
    PlatformType.GOOGLE_ANALYTICS: {
        "sessions": "sessions",
        "total_users": "users",
        "users": "users",
        "screen_page_views": "impressions",
        "page_views": "impressions",
        "bounce_rate": "bounce_rate",
        "conversions": "conversions",
        "total_revenue": "revenue_usd",
        "purchase_revenue": "revenue_usd",
    },

    # --- Google Search Console ---
    PlatformType.GOOGLE_SEARCH_CONSOLE: {
        "impressions": "impressions",
        "clicks": "clicks",
        "ctr": "ctr",
    },

    # --- Meta Organic (Facebook + Instagram non-paid) ---
    PlatformType.META_ORGANIC: {
        "impressions": "impressions",
        "reach": "reach",
        "post_engagement": "engagements",
        "page_followers": "followers",
        "followers": "followers",
        "profile_views": "impressions",
    },

    # --- X Ads (formerly Twitter Ads) ---
    PlatformType.X_ADS: {
        "impressions": "impressions",
        "engagements": "engagements",
        "clicks": "clicks",
        "spend": "spend_usd",
        "conversions": "conversions",
        "ctr": "ctr",
        "cpc": "cost_per_click",
        "roas": "roas",
    },

    # --- Instagram (organic) ---
    PlatformType.INSTAGRAM: {
        "impressions": "impressions",
        "reach": "reach",
        "engagements": "engagements",
        "likes": "engagements",
        "comments": "engagements",
        "saves": "engagements",
        "follower_count": "followers",
        "followers": "followers",
        "profile_views": "impressions",
    },

    # --- TikTok Ads ---
    PlatformType.TIKTOK_ADS: {
        "impressions": "impressions",
        "clicks": "clicks",
        "spend": "spend_usd",
        "cost": "spend_usd",
        "conversions": "conversions",
        "conversion_value": "revenue_usd",
        "ctr": "ctr",
        "cpc": "cost_per_click",
        "roas": "roas",
        "video_views": "impressions",
    },

    # --- Pinterest Ads ---
    PlatformType.PINTEREST_ADS: {
        "impressions": "impressions",
        "pin_clicks": "clicks",
        "clicks": "clicks",
        "spend_in_dollar": "spend_usd",
        "spend": "spend_usd",
        "conversions": "conversions",
        "total_conversion_value_in_micro_dollar": "revenue_usd",
        "ctr": "ctr",
        "ecpc_in_dollar": "cost_per_click",
        "save": "engagements",
        "saves": "engagements",
    },

    # --- LinkedIn Ads ---
    PlatformType.LINKEDIN_ADS: {
        "impressions": "impressions",
        "clicks": "clicks",
        "cost_in_usd": "spend_usd",
        "spend": "spend_usd",
        "conversions": "conversions",
        "external_website_conversions": "conversions",
        "leads": "conversions",
        "ctr": "ctr",
        "cost_per_click": "cost_per_click",
        "engagement": "engagements",
    },

    # --- Email Marketing (Mailchimp, SendGrid, etc.) ---
    PlatformType.EMAIL_MARKETING: {
        "emails_sent": "impressions",
        "opens": "impressions",
        "clicks": "clicks",
        "unique_clicks": "clicks",
        "conversions": "conversions",
        "revenue": "revenue_usd",
        "bounce_rate": "bounce_rate",
        "open_rate": "ctr",   # treat open-rate as analog to ctr for normalization
        "click_rate": "ctr",
    },
}


# ============================================================
# FIELDS CARRIED THROUGH UNCHANGED
# ============================================================
# These are NOT metrics — they're metadata. normalize_platform_row() returns
# them as-is alongside the metric list so the caller can write them to
# unified_metrics_cache.campaign_id / campaign_name / metric_date.

_PASSTHROUGH_FIELDS = {
    "date",            # YYYY-MM-DD, converted by caller
    "metric_date",     # alt name
    "campaign_id",
    "campaign_name",
}


# ============================================================
# PUBLIC API
# ============================================================

def get_platforms_with_mappings() -> List[PlatformType]:
    """Return every platform that has at least one normalization rule."""
    return list(_NORMALIZATION_RULES.keys())


def normalize_platform_row(
    platform_type: PlatformType,
    raw_row: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Convert ONE raw provider row into a LIST of normalized-metric rows.

    Why a list: a single raw row usually contains many metrics side-by-side
    (e.g. {"impressions": 1000, "clicks": 50, "spend": 12.5}). We unpivot
    them into one row per metric because that's what our cache table stores.

    Args:
        platform_type: Which platform this row came from.
        raw_row: A dict from the platform's API / the mock provider.
            Expected shape (all fields optional except at least one metric):
                {
                    "date": "2026-04-18",
                    "campaign_id": "123",
                    "campaign_name": "Spring Sale",
                    "impressions": 1000,
                    "clicks": 50,
                    ...
                }

    Returns:
        A list of dicts, each ready to write into unified_metrics_cache:
            {
                "metric_name": "impressions",
                "metric_value": 1000.0,
                "metric_date": "2026-04-18",
                "campaign_id": "123",
                "campaign_name": "Spring Sale",
                "raw_json": {...},    # full original row for audit
            }
    """
    mappings = _NORMALIZATION_RULES.get(platform_type, {})

    # Extract passthrough metadata once
    meta_date = raw_row.get("date") or raw_row.get("metric_date")
    meta_campaign_id = raw_row.get("campaign_id")
    meta_campaign_name = raw_row.get("campaign_name")

    normalized: List[Dict[str, Any]] = []

    for raw_key, raw_value in raw_row.items():
        # Skip metadata keys and non-numeric values
        if raw_key in _PASSTHROUGH_FIELDS:
            continue
        if raw_value is None:
            continue
        if not isinstance(raw_value, (int, float)):
            continue
        if raw_key not in mappings:
            # Unknown field — silently skip. The raw row is still preserved
            # in raw_json on each emitted normalized row for audit / replay.
            continue

        unified_name = mappings[raw_key]

        # Special case: Google Ads reports cost in micros (millionths of a dollar)
        metric_value = float(raw_value)
        if platform_type == PlatformType.GOOGLE_ADS and raw_key == "cost_micros":
            metric_value = metric_value / 1_000_000.0
        elif (
            platform_type == PlatformType.PINTEREST_ADS
            and raw_key == "total_conversion_value_in_micro_dollar"
        ):
            metric_value = metric_value / 1_000_000.0

        normalized.append(
            {
                "metric_name": unified_name,
                "metric_value": metric_value,
                "metric_date": meta_date,
                "campaign_id": meta_campaign_id,
                "campaign_name": meta_campaign_name,
                "raw_json": raw_row,
            }
        )

    return normalized
