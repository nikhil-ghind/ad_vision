"""Ad targeting engine: user segment matching + CTR prediction + auction."""
from __future__ import annotations
import math
import hashlib
from dataclasses import dataclass, field
from typing import List, Dict, Optional


@dataclass
class UserProfile:
    user_id: str
    age_group: str = "25-34"
    interests: List[str] = field(default_factory=list)
    location: str = "US"
    device: str = "desktop"
    visit_count: int = 0


@dataclass
class AdCampaign:
    campaign_id: str
    advertiser: str
    bid_cpm: float
    target_interests: List[str]
    target_age_groups: List[str]
    target_locations: List[str]
    daily_budget: float
    spent_today: float = 0.0
    content_id: str = ""


@dataclass
class AuctionResult:
    winner: Optional[AdCampaign]
    clearing_price: float
    score: float
    reason: str


def compute_relevance_score(user: UserProfile, campaign: AdCampaign) -> float:
    """Interest overlap + age/location targeting signals."""
    interest_overlap = len(set(user.interests) & set(campaign.target_interests))
    interest_score = 1.0 - math.exp(-0.5 * interest_overlap)

    age_match = 1.0 if user.age_group in campaign.target_age_groups else 0.3
    loc_match = 1.0 if user.location in campaign.target_locations else 0.5

    return interest_score * age_match * loc_match


def predict_ctr(user: UserProfile, campaign: AdCampaign) -> float:
    """Logistic function over relevance and recency signals."""
    relevance = compute_relevance_score(user, campaign)
    recency_boost = min(1.0, user.visit_count / 10.0)
    logit = -2.0 + 3.0 * relevance + 0.5 * recency_boost
    return 1.0 / (1.0 + math.exp(-logit))


def run_auction(user: UserProfile, campaigns: List[AdCampaign]) -> AuctionResult:
    """Second-price CTR-weighted auction."""
    eligible = [c for c in campaigns if c.spent_today < c.daily_budget]
    if not eligible:
        return AuctionResult(None, 0.0, 0.0, "no eligible campaigns")

    scored = []
    for c in eligible:
        ctr   = predict_ctr(user, c)
        score = c.bid_cpm * ctr
        scored.append((score, c))

    scored.sort(key=lambda x: x[0], reverse=True)
    winner_score, winner = scored[0]
    second_price = scored[1][0] if len(scored) > 1 else winner_score * 0.5
    clearing = second_price / (winner_score / winner.bid_cpm + 1e-9)

    winner.spent_today += clearing / 1000.0
    return AuctionResult(
        winner=winner,
        clearing_price=clearing,
        score=winner_score,
        reason="second-price CTR-weighted auction",
    )
