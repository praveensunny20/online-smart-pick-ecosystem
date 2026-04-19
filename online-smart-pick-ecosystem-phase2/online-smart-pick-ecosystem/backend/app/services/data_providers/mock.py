"""
Mock data provider.

Produces DETERMINISTIC fake-but-plausible metric data so the whole sync pipeline
can be developed, tested, and demoed with zero external API credentials.

Determinism matters:
    - Running the sync twice on the same day for the same client should produce
      the same numbers (so upsert-logic tests are stable).
    - Numbers should LOOK different across platforms (otherwise cross-platform
      comparisons would be meaningless in the demo).

We achieve that with a seeded PRNG whose seed is a hash of
(client_id, platform_type, date). Same inputs → same numbers, always.
"""
from __future__ import annotations

import hashlib
import random
from datetime import date, timedelta
from typing import Any, Dict, List

from app.models import PlatformConnection, PlatformType
from app.services.data_providers.base import BaseProvider


# ============================================================
# Per-platform baseline ranges
# ============================================================
# (impressions_range, click_rate_range, spend_per_click_range, conv_rate_range)
# These baselines are tuned so Meta looks like a decent paid channel, Google
# Ads looks like an expensive-but-high-intent channel, TikTok looks like a
# cheap-high-volume channel, and so on. Feel free to tweak.

_PLATFORM_BASELINES: Dict[PlatformType, Dict[str, Any]] = {
    PlatformType.META_ADS: {
        "imp_range": (8_000, 25_000),
        "ctr_range": (0.012, 0.028),
        "cpc_range": (0.35, 1.20),
        "cvr_range": (0.015, 0.04),
        "aov_range": (35.0, 85.0),
    },
    PlatformType.META_ORGANIC: {
        "imp_range": (2_000, 12_000),
        "ctr_range": (0.005, 0.015),
        "cpc_range": (0.0, 0.0),
        "cvr_range": (0.001, 0.004),
        "aov_range": (0.0, 0.0),
    },
    PlatformType.GOOGLE_ADS: {
        "imp_range": (5_000, 18_000),
        "ctr_range": (0.025, 0.065),
        "cpc_range": (0.80, 3.50),
        "cvr_range": (0.03, 0.09),
        "aov_range": (60.0, 180.0),
    },
    PlatformType.GOOGLE_ANALYTICS: {
        "imp_range": (4_000, 20_000),  # page views
        "ctr_range": (0.0, 0.0),
        "cpc_range": (0.0, 0.0),
        "cvr_range": (0.01, 0.045),
        "aov_range": (40.0, 140.0),
    },
    PlatformType.GOOGLE_SEARCH_CONSOLE: {
        "imp_range": (10_000, 60_000),
        "ctr_range": (0.015, 0.055),
        "cpc_range": (0.0, 0.0),
        "cvr_range": (0.0, 0.0),
        "aov_range": (0.0, 0.0),
    },
    PlatformType.X_ADS: {
        "imp_range": (6_000, 22_000),
        "ctr_range": (0.009, 0.024),
        "cpc_range": (0.30, 1.10),
        "cvr_range": (0.01, 0.03),
        "aov_range": (30.0, 70.0),
    },
    PlatformType.INSTAGRAM: {
        "imp_range": (3_000, 18_000),
        "ctr_range": (0.0, 0.0),
        "cpc_range": (0.0, 0.0),
        "cvr_range": (0.0, 0.0),
        "aov_range": (0.0, 0.0),
    },
    PlatformType.TIKTOK_ADS: {
        "imp_range": (15_000, 60_000),
        "ctr_range": (0.007, 0.022),
        "cpc_range": (0.15, 0.55),
        "cvr_range": (0.008, 0.025),
        "aov_range": (25.0, 70.0),
    },
    PlatformType.PINTEREST_ADS: {
        "imp_range": (3_500, 14_000),
        "ctr_range": (0.012, 0.028),
        "cpc_range": (0.25, 0.85),
        "cvr_range": (0.015, 0.035),
        "aov_range": (40.0, 95.0),
    },
    PlatformType.LINKEDIN_ADS: {
        "imp_range": (1_500, 6_000),
        "ctr_range": (0.004, 0.012),
        "cpc_range": (3.00, 9.00),
        "cvr_range": (0.02, 0.06),
        "aov_range": (150.0, 650.0),
    },
    PlatformType.EMAIL_MARKETING: {
        "imp_range": (1_000, 8_000),  # emails sent
        "ctr_range": (0.02, 0.10),
        "cpc_range": (0.0, 0.0),
        "cvr_range": (0.01, 0.05),
        "aov_range": (30.0, 120.0),
    },
}


def _seeded_rng(client_id: str, platform_type: PlatformType, day: date) -> random.Random:
    """Build a reproducible RNG for a single (client, platform, date) triple."""
    seed_str = f"{client_id}|{platform_type.value}|{day.isoformat()}"
    seed_int = int.from_bytes(
        hashlib.sha256(seed_str.encode("utf-8")).digest()[:8], "big"
    )
    return random.Random(seed_int)


def _round_metric(v: float) -> float:
    """Round metric values to 2 decimals for cleaner numbers in the UI."""
    return round(v, 2)


def _build_row_for_day(
    client_id: str,
    platform_type: PlatformType,
    day: date,
    campaign_id: str,
    campaign_name: str,
) -> Dict[str, Any]:
    """Build a single raw-row dict for this platform on this day."""
    baseline = _PLATFORM_BASELINES.get(platform_type)
    if baseline is None:
        # Unknown platform — return an empty-ish row so caller can skip
        return {
            "date": day.isoformat(),
            "campaign_id": campaign_id,
            "campaign_name": campaign_name,
            "impressions": 0,
        }

    rng = _seeded_rng(client_id, platform_type, day)

    impressions = rng.randint(*baseline["imp_range"])
    ctr_lo, ctr_hi = baseline["ctr_range"]
    ctr = rng.uniform(ctr_lo, ctr_hi) if ctr_hi > 0 else 0.0
    clicks = int(impressions * ctr)

    cpc_lo, cpc_hi = baseline["cpc_range"]
    cpc = rng.uniform(cpc_lo, cpc_hi) if cpc_hi > 0 else 0.0
    spend = clicks * cpc

    cvr_lo, cvr_hi = baseline["cvr_range"]
    cvr = rng.uniform(cvr_lo, cvr_hi) if cvr_hi > 0 else 0.0
    conversions = int(clicks * cvr)

    aov_lo, aov_hi = baseline["aov_range"]
    aov = rng.uniform(aov_lo, aov_hi) if aov_hi > 0 else 0.0
    revenue = conversions * aov

    # Common base every row has
    row: Dict[str, Any] = {
        "date": day.isoformat(),
        "campaign_id": campaign_id,
        "campaign_name": campaign_name,
    }

    # Platform-specific field names — these match the keys in normalization.py
    if platform_type == PlatformType.META_ADS:
        row.update({
            "impressions": impressions,
            "reach": int(impressions * 0.75),
            "link_clicks": clicks,
            "spend": _round_metric(spend),
            "conversions": conversions,
            "purchase_value": _round_metric(revenue),
            "ctr": _round_metric(ctr),
            "cpc": _round_metric(cpc),
            "post_engagement": int(impressions * rng.uniform(0.01, 0.04)),
        })
    elif platform_type == PlatformType.META_ORGANIC:
        row.update({
            "impressions": impressions,
            "reach": int(impressions * 0.7),
            "post_engagement": int(impressions * rng.uniform(0.02, 0.06)),
            "page_followers": 5_000 + rng.randint(0, 3_000),
            "profile_views": int(impressions * 0.08),
        })
    elif platform_type == PlatformType.GOOGLE_ADS:
        row.update({
            "impressions": impressions,
            "clicks": clicks,
            "cost_micros": int(spend * 1_000_000),
            "conversions": conversions,
            "conversion_value": _round_metric(revenue),
            "ctr": _round_metric(ctr),
            "average_cpc": _round_metric(cpc),
        })
    elif platform_type == PlatformType.GOOGLE_ANALYTICS:
        sessions = int(impressions * rng.uniform(0.25, 0.6))
        users = int(sessions * rng.uniform(0.6, 0.85))
        row.update({
            "sessions": sessions,
            "total_users": users,
            "screen_page_views": impressions,
            "bounce_rate": _round_metric(rng.uniform(0.35, 0.62)),
            "conversions": conversions,
            "total_revenue": _round_metric(revenue),
        })
    elif platform_type == PlatformType.GOOGLE_SEARCH_CONSOLE:
        row.update({
            "impressions": impressions,
            "clicks": clicks,
            "ctr": _round_metric(ctr),
        })
    elif platform_type == PlatformType.X_ADS:
        row.update({
            "impressions": impressions,
            "engagements": int(impressions * rng.uniform(0.015, 0.04)),
            "clicks": clicks,
            "spend": _round_metric(spend),
            "conversions": conversions,
            "ctr": _round_metric(ctr),
            "cpc": _round_metric(cpc),
        })
    elif platform_type == PlatformType.INSTAGRAM:
        row.update({
            "impressions": impressions,
            "reach": int(impressions * 0.72),
            "engagements": int(impressions * rng.uniform(0.03, 0.08)),
            "likes": int(impressions * rng.uniform(0.02, 0.05)),
            "comments": int(impressions * rng.uniform(0.002, 0.008)),
            "saves": int(impressions * rng.uniform(0.004, 0.012)),
            "follower_count": 12_000 + rng.randint(0, 4_000),
        })
    elif platform_type == PlatformType.TIKTOK_ADS:
        row.update({
            "impressions": impressions,
            "video_views": int(impressions * rng.uniform(0.4, 0.8)),
            "clicks": clicks,
            "spend": _round_metric(spend),
            "conversions": conversions,
            "conversion_value": _round_metric(revenue),
            "ctr": _round_metric(ctr),
            "cpc": _round_metric(cpc),
        })
    elif platform_type == PlatformType.PINTEREST_ADS:
        row.update({
            "impressions": impressions,
            "pin_clicks": clicks,
            "spend_in_dollar": _round_metric(spend),
            "conversions": conversions,
            "total_conversion_value_in_micro_dollar": int(revenue * 1_000_000),
            "ctr": _round_metric(ctr),
            "ecpc_in_dollar": _round_metric(cpc),
            "saves": int(impressions * rng.uniform(0.01, 0.03)),
        })
    elif platform_type == PlatformType.LINKEDIN_ADS:
        row.update({
            "impressions": impressions,
            "clicks": clicks,
            "cost_in_usd": _round_metric(spend),
            "conversions": conversions,
            "leads": conversions,
            "ctr": _round_metric(ctr),
            "cost_per_click": _round_metric(cpc),
            "engagement": int(impressions * rng.uniform(0.008, 0.025)),
        })
    elif platform_type == PlatformType.EMAIL_MARKETING:
        row.update({
            "emails_sent": impressions,
            "opens": int(impressions * rng.uniform(0.18, 0.42)),
            "clicks": clicks,
            "conversions": conversions,
            "revenue": _round_metric(revenue),
            "bounce_rate": _round_metric(rng.uniform(0.005, 0.03)),
            "open_rate": _round_metric(rng.uniform(0.18, 0.42)),
            "click_rate": _round_metric(ctr),
        })

    return row


class MockProvider(BaseProvider):
    """
    Deterministic fixture-data provider. Produces one row per day in the
    requested window, with two fake campaigns so you have some campaign
    variation in the data.
    """

    name = "mock"

    def fetch_metrics(
        self,
        connection: PlatformConnection,
        credentials: Dict[str, Any],  # unused in mock, accepted for interface parity
        start_date: date,
        end_date: date,
    ) -> List[Dict[str, Any]]:
        if start_date > end_date:
            return []

        client_id = str(connection.client_id)
        platform_type = connection.platform_type

        # Two fake campaigns per connection → shows campaign-level breakdown
        campaigns = [
            ("cmp_001", "Always-On Awareness"),
            ("cmp_002", "Weekly Promo"),
        ]

        rows: List[Dict[str, Any]] = []
        day = start_date
        while day <= end_date:
            for cid, cname in campaigns:
                rows.append(
                    _build_row_for_day(
                        client_id=client_id,
                        platform_type=platform_type,
                        day=day,
                        campaign_id=cid,
                        campaign_name=cname,
                    )
                )
            day += timedelta(days=1)

        return rows
