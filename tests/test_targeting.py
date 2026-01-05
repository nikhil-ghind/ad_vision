import pytest
from backend.targeting.engine import UserProfile, AdCampaign, run_auction, predict_ctr, compute_relevance_score


def make_campaign(cid="c1", interests=("tech",), age_groups=("25-34",)):
    return AdCampaign(cid, "Adv", 5.0, list(interests), list(age_groups), ["US"], 100.0)


def test_high_relevance_for_matching_user():
    user = UserProfile("u1", "25-34", ["tech", "gadgets"], "US")
    camp = make_campaign(interests=["tech", "gadgets"])
    score = compute_relevance_score(user, camp)
    assert score > 0.5


def test_low_relevance_for_mismatched_user():
    user = UserProfile("u1", "25-34", ["cooking"], "US")
    camp = make_campaign(interests=["tech", "gadgets"])
    score = compute_relevance_score(user, camp)
    assert score < 0.4


def test_auction_returns_winner():
    user = UserProfile("u1", "25-34", ["tech"], "US")
    campaigns = [make_campaign("c1", ["tech"]), make_campaign("c2", ["fitness"])]
    result = run_auction(user, campaigns)
    assert result.winner is not None
    assert result.clearing_price >= 0


def test_auction_no_budget():
    user = UserProfile("u1", "25-34", ["tech"], "US")
    c = make_campaign()
    c.spent_today = c.daily_budget
    result = run_auction(user, [c])
    assert result.winner is None
