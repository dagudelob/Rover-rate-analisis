import pytest
import pandas as pd
import numpy as np
from app.services.analytics import (
    calculate_market_statistics,
    calculate_pricing_sweet_spot,
    detect_outliers_iqr,
    calculate_hedonic_decomposition,
    fit_parametric_distribution,
    calculate_spatial_neighborhood_premiums,
)

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
    assert "per_service_analytics" in stats
    assert "dog-walking" in stats["per_service_analytics"]
    assert "hedonic_decomposition" in stats
    assert "parametric_distribution" in stats
    assert "spatial_premiums" in stats

def test_hedonic_decomposition_regression():
    records = [
        {"name": "A", "headline": "Star Sitter", "price_numeric": 35.0, "reviews_count": 15},
        {"name": "B", "headline": "Star Sitter", "price_numeric": 45.0, "reviews_count": 40},
        {"name": "C", "headline": "Star Sitter", "price_numeric": 55.0, "reviews_count": 80},
        {"name": "D", "headline": "Friendly walker", "price_numeric": 22.0, "reviews_count": 2},
        {"name": "E", "headline": "Reliable care", "price_numeric": 26.0, "reviews_count": 10},
        {"name": "F", "headline": "Passionate sitter", "price_numeric": 28.0, "reviews_count": 18},
    ]
    res = calculate_hedonic_decomposition(records)
    assert res["status"] == "success"
    assert res["r_squared"] > 0
    assert res["review_elasticity"] is not None
    assert res["star_sitter_premium_pct"] is not None

def test_parametric_lognormal_distribution_fit():
    prices = [20.0, 25.0, 28.0, 30.0, 32.0, 35.0, 45.0, 60.0]
    fit = fit_parametric_distribution(prices)
    assert fit["status"] == "success"
    assert "mu" in fit and "sigma" in fit
    assert len(fit["curve"]) > 0

def test_spatial_neighborhood_premiums():
    records = [
        {"name": "A", "price_numeric": 60.0, "postal_code": "M5V", "neighborhood": "King West"},
        {"name": "B", "price_numeric": 65.0, "postal_code": "M5V", "neighborhood": "King West"},
        {"name": "C", "price_numeric": 30.0, "postal_code": "M1B", "neighborhood": "Malvern"},
        {"name": "D", "price_numeric": 32.0, "postal_code": "M1B", "neighborhood": "Malvern"},
    ]
    premiums = calculate_spatial_neighborhood_premiums(records, metro_median=45.0)
    assert len(premiums) == 2
    fsa_map = {p["postal_code"]: p for p in premiums}
    assert fsa_map["M5V"]["premium_pct"] > 0
    assert fsa_map["M1B"]["premium_pct"] < 0

def test_market_statistics_multi_service_separation():
    records = [
        {
            "name": "Sarah",
            "price_numeric": 25.0,
            "services": [
                {"service_type": "dog-walking", "price_numeric": 25.0},
                {"service_type": "overnight-boarding", "price_numeric": 70.0}
            ]
        },
        {
            "name": "David",
            "price_numeric": 30.0,
            "services": [
                {"service_type": "dog-walking", "price_numeric": 30.0},
                {"service_type": "overnight-boarding", "price_numeric": 80.0}
            ]
        }
    ]
    stats = calculate_market_statistics(records)
    walking_stats = stats["per_service_analytics"]["dog-walking"]
    boarding_stats = stats["per_service_analytics"]["overnight-boarding"]

    assert walking_stats["median_price"] == 27.5
    assert boarding_stats["median_price"] == 75.0
    assert walking_stats["pricing_optimizer"]["sweet_spot_price"] < boarding_stats["pricing_optimizer"]["sweet_spot_price"]

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
    
    first_pt = res["curve"][0]
    last_pt = res["curve"][-1]
    assert first_pt["conversion_probability_pct"] > last_pt["conversion_probability_pct"]
    assert "elasticity" in first_pt


def test_per_service_analytics_with_dynamic_exclusion():
    records = [
        {
            "name": "Sitter 1",
            "price_numeric": 25.0,
            "reviews_count": 10,
            "services": [
                {"service_type": "dog-walking", "price_numeric": 25.0},
                {"service_type": "house-sitting", "price_numeric": 70.0},
                {"service_type": "day-care", "price_numeric": 45.0},
            ]
        },
        {
            "name": "Sitter 2",
            "price_numeric": 28.0,
            "reviews_count": 15,
            "services": [
                {"service_type": "dog-walking", "price_numeric": 28.0},
                {"service_type": "house-sitting", "price_numeric": 75.0},
                {"service_type": "day-care", "price_numeric": 50.0},
            ]
        },
        {
            "name": "Outlier Sitter",
            "price_numeric": 90.0,
            "reviews_count": 1,
            "services": [
                {"service_type": "dog-walking", "price_numeric": 90.0},
                {"service_type": "house-sitting", "price_numeric": 250.0},
                {"service_type": "day-care", "price_numeric": 180.0},
            ]
        },
    ]

    # Without exclusion
    stats_all = calculate_market_statistics(records)
    hs_all = stats_all["per_service_analytics"]["house-sitting"]
    assert hs_all["max_price"] == 250.0
    assert hs_all["total_sitters"] == 3

    # With outlier excluded (idx 2)
    stats_filtered = calculate_market_statistics(records, excluded_indices={2})
    hs_filtered = stats_filtered["per_service_analytics"]["house-sitting"]
    assert hs_filtered["max_price"] == 75.0
    assert hs_filtered["total_sitters"] == 2
    assert hs_filtered["pricing_optimizer"]["sweet_spot_price"] is not None
    assert hs_filtered["pricing_optimizer"]["sweet_spot_price"] < 100.0

