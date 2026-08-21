import pytest
import pandas as pd
import numpy as np
from analytics import calculate_market_statistics, calculate_pricing_sweet_spot, detect_outliers_iqr

def test_market_statistics_basic():
    records = [
        {"name": "A", "price_numeric": 20.0, "reviews_count": 10},
        {"name": "B", "price_numeric": 25.0, "reviews_count": 5},
        {"name": "C", "price_numeric": 30.0, "reviews_count": 12},
        {"name": "D", "price_numeric": 35.0, "reviews_count": 2},
        {"name": "E", "price_numeric": 40.0, "reviews_count": 8},
    ]
    stats = calculate_market_statistics(records)
    assert stats["total_sitters"] == 5
    assert stats["active_sitters"] == 5
    assert stats["min_price"] == 20.0
    assert stats["max_price"] == 40.0
    assert stats["median_price"] == 30.0
    assert stats["avg_price"] == 30.0
    assert stats["iqr"] > 0
    assert "pricing_optimizer" in stats
    assert stats["pricing_optimizer"]["sweet_spot_price"] is not None

def test_market_statistics_empty():
    stats = calculate_market_statistics([])
    assert stats["total_sitters"] == 0
    assert stats["active_sitters"] == 0
    assert stats["min_price"] is None
    assert stats["pricing_optimizer"]["sweet_spot_price"] is None

def test_market_statistics_with_exclusions():
    records = [
        {"name": "A", "price_numeric": 20.0},
        {"name": "B", "price_numeric": 25.0},
        {"name": "C", "price_numeric": 300.0}, # outlier to exclude
    ]
    stats = calculate_market_statistics(records, excluded_indices={2})
    assert stats["total_sitters"] == 3
    assert stats["active_sitters"] == 2
    assert stats["excluded_sitters"] == 1
    assert stats["max_price"] == 25.0
    assert stats["avg_price"] == 22.5

def test_detect_outliers_iqr():
    records = [
        {"name": "A", "price_numeric": 20.0},
        {"name": "B", "price_numeric": 22.0},
        {"name": "C", "price_numeric": 24.0},
        {"name": "D", "price_numeric": 25.0},
        {"name": "E", "price_numeric": 26.0},
        {"name": "F", "price_numeric": 28.0},
        {"name": "G", "price_numeric": 95.0}, # High outlier (idx 6)
        {"name": "H", "price_numeric": 2.0},  # Low outlier (idx 7)
    ]
    outliers = detect_outliers_iqr(records)
    assert 6 in outliers
    assert 7 in outliers
    assert 0 not in outliers

def test_pricing_sweet_spot_empirical_survival():
    prices = pd.Series([15.0, 18.0, 20.0, 22.0, 25.0, 28.0, 30.0, 35.0])
    reviews = pd.Series([1, 4, 10, 8, 3, 5, 2, 0])
    
    res = calculate_pricing_sweet_spot(prices, reviews)
    assert res["sweet_spot_price"] is not None
    assert res["recommended_range"]["min"] < res["recommended_range"]["max"]
    assert len(res["curve"]) > 0
    
    # Check that conversion probability decreases as price increases
    first_pt = res["curve"][0]
    last_pt = res["curve"][-1]
    assert first_pt["conversion_probability_pct"] > last_pt["conversion_probability_pct"]
    assert "elasticity" in first_pt
