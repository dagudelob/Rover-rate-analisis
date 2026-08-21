"""
Analytics service — market statistics, pricing optimizer, CDF curves, cross-service benchmarks,
neighborhood aggregations, and dedicated per-service analytics for all 5 Rover service categories.

All logic is pure Python/NumPy/Pandas. No FastAPI, no DB, no HTTP concerns.
"""
import logging
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger("rover.services.analytics")

CORE_SERVICES = [
    "dog-walking",
    "overnight-boarding",
    "house-sitting",
    "drop-in-visits",
    "day-care",
]

SERVICE_TITLES = {
    "dog-walking": "Dog Walking",
    "overnight-boarding": "Overnight Boarding",
    "house-sitting": "House Sitting",
    "drop-in-visits": "Drop-in Visits",
    "day-care": "Day Care",
}


def calculate_single_service_stats(
    service_type: str,
    records: List[Dict[str, Any]],
    excluded_indices: Optional[set] = None
) -> Dict[str, Any]:
    """
    Computes a full statistical & revenue optimization block for a single service category.
    """
    if excluded_indices is None:
        excluded_indices = set()

    # Extract all prices specific to this service type
    valid_items = []
    for idx, r in enumerate(records):
        if idx in excluded_indices:
            continue

        price_val = None
        # Check services list
        for s in r.get("services", []):
            if s.get("service_type") == service_type and s.get("price_numeric") is not None:
                price_val = float(s["price_numeric"])
                break

        # Fallback to primary record price if service matches
        if price_val is None and r.get("service_type") == service_type and r.get("price_numeric") is not None:
            price_val = float(r["price_numeric"])

        if price_val is not None and price_val > 0:
            valid_items.append({
                "record_idx": idx,
                "name": r.get("name", "Sitter"),
                "price": price_val,
                "reviews_count": float(r.get("reviews_count") or 0),
                "rating": r.get("rating") or "5.0",
                "neighborhood": r.get("neighborhood") or r.get("location_query") or "Local Area",
            })

    if not valid_items:
        return {
            "service_type": service_type,
            "service_title": SERVICE_TITLES.get(service_type, service_type.title()),
            "total_sitters": 0,
            "min_price": None,
            "avg_price": None,
            "median_price": None,
            "p10_price": None,
            "p25_price": None,
            "p75_price": None,
            "p90_price": None,
            "max_price": None,
            "std_dev": None,
            "variance": None,
            "trimmed_mean_10": None,
            "iqr": None,
            "outlier_bounds": {"lower": None, "upper": None},
            "price_distribution": [],
            "cdf_curve": [],
            "scatter_points": [],
            "pricing_optimizer": {
                "sweet_spot_price": None,
                "recommended_range": {"min": None, "max": None},
                "max_expected_revenue_index": None,
                "strategy": "No data",
                "curve": [],
            },
            "outlier_indices": [],
        }

    prices = pd.Series([item["price"] for item in valid_items])
    reviews = pd.Series([item["reviews_count"] for item in valid_items])

    q25 = float(prices.quantile(0.25))
    q75 = float(prices.quantile(0.75))
    iqr_val = q75 - q25
    lower_iqr_bound = round(max(0.0, q25 - 1.5 * iqr_val), 2)
    upper_iqr_bound = round(q75 + 1.5 * iqr_val, 2)

    std_val = float(prices.std()) if len(prices) > 1 else 0.0
    var_val = float(prices.var()) if len(prices) > 1 else 0.0

    trim_pct = 0.10
    if len(prices) >= 5:
        lower_cut = float(prices.quantile(trim_pct))
        upper_cut = float(prices.quantile(1.0 - trim_pct))
        trimmed_prices = prices[(prices >= lower_cut) & (prices <= upper_cut)]
        trimmed_mean = float(trimmed_prices.mean()) if len(trimmed_prices) > 0 else float(prices.mean())
    else:
        trimmed_mean = float(prices.mean())

    # Optimal Pricing Sweet Spot Calculation for this specific service
    optimizer_data = calculate_pricing_sweet_spot(prices, reviews)

    # 1. Price Distribution Histogram
    price_distribution = []
    try:
        min_p = float(prices.min())
        max_p = float(prices.max())
        if min_p == max_p:
            bins = [min_p - 5.0, min_p + 5.0]
        else:
            num_bins = min(8, max(4, len(prices.unique())))
            bins = np.linspace(min_p, max_p, num_bins + 1)

        hist, bin_edges = np.histogram(prices, bins=bins)
        price_distribution = [
            {
                "range": f"${bin_edges[i]:.0f} - ${bin_edges[i + 1]:.0f}",
                "count": int(hist[i]),
                "min": float(bin_edges[i]),
                "max": float(bin_edges[i + 1]),
            }
            for i in range(len(hist))
        ]
    except Exception as exc:
        logger.warning("Error computing price histogram for %s: %s", service_type, exc)

    # 2. Cumulative Distribution Function (CDF)
    cdf_curve = []
    try:
        sorted_prices = np.sort(prices.to_numpy())
        n = len(sorted_prices)
        cum_probs = np.arange(1, n + 1) / n * 100.0
        step = max(1, n // 20)
        cdf_curve = [
            {"price": round(float(sorted_prices[i]), 1), "percentile": round(float(cum_probs[i]), 1)}
            for i in range(0, n, step)
        ]
        if cdf_curve and cdf_curve[-1]["percentile"] < 100.0:
            cdf_curve.append({"price": round(float(sorted_prices[-1]), 1), "percentile": 100.0})
    except Exception as exc:
        logger.warning("Error computing CDF curve for %s: %s", service_type, exc)

    # 3. Scatter Points
    scatter_points = [
        {
            "name": item["name"],
            "price": item["price"],
            "reviews_count": item["reviews_count"],
            "rating": item["rating"],
            "neighborhood": item["neighborhood"],
        }
        for item in valid_items
    ]

    outlier_indices = [
        item["record_idx"] for item in valid_items
        if item["price"] < lower_iqr_bound or item["price"] > upper_iqr_bound
    ]

    return {
        "service_type": service_type,
        "service_title": SERVICE_TITLES.get(service_type, service_type.title()),
        "total_sitters": len(valid_items),
        "min_price": round(float(prices.min()), 2),
        "avg_price": round(float(prices.mean()), 2),
        "median_price": round(float(prices.median()), 2),
        "p10_price": round(float(prices.quantile(0.10)), 2),
        "p25_price": round(q25, 2),
        "p75_price": round(q75, 2),
        "p90_price": round(float(prices.quantile(0.90)), 2),
        "max_price": round(float(prices.max()), 2),
        "std_dev": round(std_val, 2),
        "variance": round(var_val, 2),
        "trimmed_mean_10": round(trimmed_mean, 2),
        "iqr": round(iqr_val, 2),
        "outlier_bounds": {"lower": lower_iqr_bound, "upper": upper_iqr_bound},
        "price_distribution": price_distribution,
        "cdf_curve": cdf_curve,
        "scatter_points": scatter_points,
        "pricing_optimizer": optimizer_data,
        "outlier_indices": outlier_indices,
    }


def calculate_market_statistics(
    records: List[Dict[str, Any]], excluded_indices: Optional[set] = None
) -> Dict[str, Any]:
    """
    Computes comprehensive market price metrics, percentiles, dispersion indicators,
    empirical CDF curves, cross-service comparatives, neighborhood breakdowns,
    AND generates dedicated per-service analytics for each of the 5 core Rover services.
    """
    if excluded_indices is None:
        excluded_indices = set()

    active_records = [
        r for idx, r in enumerate(records)
        if idx not in excluded_indices and r.get("price_numeric") is not None
    ]

    empty_stats = {
        "total_sitters": len(records),
        "active_sitters": 0,
        "excluded_sitters": len(excluded_indices),
        "min_price": None,
        "avg_price": None,
        "median_price": None,
        "p10_price": None,
        "p25_price": None,
        "p75_price": None,
        "p90_price": None,
        "max_price": None,
        "std_dev": None,
        "variance": None,
        "trimmed_mean_10": None,
        "iqr": None,
        "outlier_bounds": {"lower": None, "upper": None},
        "price_distribution": [],
        "cdf_curve": [],
        "service_comparisons": {},
        "neighborhood_breakdown": [],
        "per_service_analytics": {},
        "pricing_optimizer": {
            "sweet_spot_price": None,
            "recommended_range": {"min": None, "max": None},
            "max_expected_revenue_index": None,
            "strategy": "No data",
            "curve": [],
        },
    }

    if not active_records:
        return empty_stats

    # Compute dedicated statistical models for all 5 services
    per_service_analytics = {}
    for stype in CORE_SERVICES:
        per_service_analytics[stype] = calculate_single_service_stats(stype, records, excluded_indices)

    prices = pd.Series([float(r["price_numeric"]) for r in active_records])
    reviews = pd.Series([float(r.get("reviews_count") or 0) for r in active_records])

    q25 = float(prices.quantile(0.25))
    q75 = float(prices.quantile(0.75))
    iqr_val = q75 - q25
    lower_iqr_bound = round(max(0.0, q25 - 1.5 * iqr_val), 2)
    upper_iqr_bound = round(q75 + 1.5 * iqr_val, 2)

    std_val = float(prices.std()) if len(prices) > 1 else 0.0
    var_val = float(prices.var()) if len(prices) > 1 else 0.0

    trim_pct = 0.10
    if len(prices) >= 5:
        lower_cut = float(prices.quantile(trim_pct))
        upper_cut = float(prices.quantile(1.0 - trim_pct))
        trimmed_prices = prices[(prices >= lower_cut) & (prices <= upper_cut)]
        trimmed_mean = float(trimmed_prices.mean()) if len(trimmed_prices) > 0 else float(prices.mean())
    else:
        trimmed_mean = float(prices.mean())

    optimizer_data = calculate_pricing_sweet_spot(prices, reviews)

    # 1. Price Distribution Histogram
    price_distribution = []
    try:
        min_p = float(prices.min())
        max_p = float(prices.max())
        if min_p == max_p:
            bins = [min_p - 5.0, min_p + 5.0]
        else:
            num_bins = min(8, max(4, len(prices.unique())))
            bins = np.linspace(min_p, max_p, num_bins + 1)

        hist, bin_edges = np.histogram(prices, bins=bins)
        price_distribution = [
            {
                "range": f"${bin_edges[i]:.0f} - ${bin_edges[i + 1]:.0f}",
                "count": int(hist[i]),
                "min": float(bin_edges[i]),
                "max": float(bin_edges[i + 1]),
            }
            for i in range(len(hist))
        ]
    except Exception as exc:
        logger.warning("Error computing price histogram: %s", exc)

    # 2. CDF Curve
    cdf_curve = []
    try:
        sorted_prices = np.sort(prices.to_numpy())
        n = len(sorted_prices)
        cum_probs = np.arange(1, n + 1) / n * 100.0
        step = max(1, n // 20)
        cdf_curve = [
            {"price": round(float(sorted_prices[i]), 1), "percentile": round(float(cum_probs[i]), 1)}
            for i in range(0, n, step)
        ]
        if cdf_curve and cdf_curve[-1]["percentile"] < 100.0:
            cdf_curve.append({"price": round(float(sorted_prices[-1]), 1), "percentile": 100.0})
    except Exception as exc:
        logger.warning("Error computing CDF curve: %s", exc)

    service_comparisons = calculate_cross_service_stats(active_records)
    neighborhood_breakdown = calculate_neighborhood_stats(active_records)

    return {
        "total_sitters": len(records),
        "active_sitters": len(active_records),
        "excluded_sitters": len(records) - len(active_records),
        "min_price": round(float(prices.min()), 2),
        "avg_price": round(float(prices.mean()), 2),
        "median_price": round(float(prices.median()), 2),
        "p10_price": round(float(prices.quantile(0.10)), 2),
        "p25_price": round(q25, 2),
        "p75_price": round(q75, 2),
        "p90_price": round(float(prices.quantile(0.90)), 2),
        "max_price": round(float(prices.max()), 2),
        "std_dev": round(std_val, 2),
        "variance": round(var_val, 2),
        "trimmed_mean_10": round(trimmed_mean, 2),
        "iqr": round(iqr_val, 2),
        "outlier_bounds": {"lower": lower_iqr_bound, "upper": upper_iqr_bound},
        "price_distribution": price_distribution,
        "cdf_curve": cdf_curve,
        "service_comparisons": service_comparisons,
        "neighborhood_breakdown": neighborhood_breakdown,
        "per_service_analytics": per_service_analytics,
        "pricing_optimizer": optimizer_data,
    }


def calculate_cross_service_stats(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculates price distributions across all 5 Rover service categories."""
    service_prices: Dict[str, List[float]] = {stype: [] for stype in CORE_SERVICES}

    for r in records:
        services = r.get("services", [])
        for s in services:
            stype = s.get("service_type")
            price = s.get("price_numeric")
            if stype in service_prices and price is not None:
                service_prices[stype].append(float(price))

    result = {}
    for stype, p_list in service_prices.items():
        if p_list:
            s_series = pd.Series(p_list)
            result[stype] = {
                "count": len(p_list),
                "min": round(float(s_series.min()), 1),
                "avg": round(float(s_series.mean()), 1),
                "median": round(float(s_series.median()), 1),
                "max": round(float(s_series.max()), 1),
            }
    return result


def calculate_neighborhood_stats(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Groups sitters by neighborhood/area and calculates average and median rates."""
    hood_map: Dict[str, List[float]] = {}
    for r in records:
        hood = (r.get("neighborhood") or "General Area").strip()
        price = r.get("price_numeric")
        if price is not None:
            hood_map.setdefault(hood, []).append(float(price))

    breakdown = []
    for hood, p_list in hood_map.items():
        s_series = pd.Series(p_list)
        breakdown.append({
            "neighborhood": hood,
            "sitters_count": len(p_list),
            "avg_price": round(float(s_series.mean()), 1),
            "median_price": round(float(s_series.median()), 1),
            "min_price": round(float(s_series.min()), 1),
            "max_price": round(float(s_series.max()), 1),
        })

    breakdown.sort(key=lambda x: x["sitters_count"], reverse=True)
    return breakdown[:10]


def calculate_pricing_sweet_spot(prices: pd.Series, reviews: pd.Series) -> Dict[str, Any]:
    """Computes the optimal revenue sweet spot using empirical survival analysis & PED."""
    if prices.empty:
        return {
            "sweet_spot_price": None,
            "recommended_range": {"min": None, "max": None},
            "max_expected_index": None,
            "strategy": "No data",
            "curve": [],
        }

    price_array = prices.to_numpy(dtype=float)
    n = len(price_array)
    std_val = float(np.std(price_array)) if n > 1 else 5.0

    bandwidth = max(1.5, 1.06 * (std_val or 5.0) * (n ** (-0.2)))
    min_candidate = max(5.0, float(np.min(price_array)) * 0.75)
    max_candidate = float(np.max(price_array)) * 1.25

    candidate_prices = np.linspace(min_candidate, max_candidate, 35)
    curve = []
    best_price = float(np.median(price_array))
    max_expected_score = -1.0

    for p in candidate_prices:
        competitor_diffs = np.clip((p - price_array) / bandwidth, -15.0, 15.0)
        individual_win_probs = 1.0 / (1.0 + np.exp(competitor_diffs))
        conversion_prob = float(np.mean(individual_win_probs))
        conversion_pct = round(conversion_prob * 100, 1)
        expected_revenue_index = round(float(p * conversion_prob), 2)

        dp = 0.05
        diff_plus = np.clip((p + dp - price_array) / bandwidth, -15.0, 15.0)
        prob_plus = float(np.mean(1.0 / (1.0 + np.exp(diff_plus))))
        d_prob_dp = (prob_plus - conversion_prob) / dp
        elasticity = round(float((p / max(0.001, conversion_prob)) * d_prob_dp), 2)

        curve.append({
            "price": round(float(p), 1),
            "conversion_probability_pct": conversion_pct,
            "expected_revenue_index": expected_revenue_index,
            "elasticity": elasticity,
        })

        if expected_revenue_index > max_expected_score:
            max_expected_score = expected_revenue_index
            best_price = round(float(p), 1)

    median_p = float(np.median(price_array))
    if best_price > median_p * 1.1:
        strategy_name = "Premium Value Positioning (High margin with moderate booking volume)"
    elif best_price < median_p * 0.9:
        strategy_name = "Market Penetration (High volume acquisition strategy)"
    else:
        strategy_name = "Competitive Sweet Spot (Balanced margin and maximum expected yield)"

    return {
        "sweet_spot_price": best_price,
        "recommended_range": {"min": round(best_price * 0.90, 1), "max": round(best_price * 1.10, 1)},
        "max_expected_index": max_expected_score,
        "strategy": strategy_name,
        "curve": curve,
    }


def detect_outliers_iqr(records: List[Dict[str, Any]]) -> List[int]:
    """Returns indices of records that qualify as price outliers by the 1.5 × IQR rule."""
    valid_indices = [idx for idx, r in enumerate(records) if r.get("price_numeric") is not None]
    if len(valid_indices) < 4:
        return []

    prices = [float(records[idx]["price_numeric"]) for idx in valid_indices]
    s = pd.Series(prices)
    q25 = float(s.quantile(0.25))
    q75 = float(s.quantile(0.75))
    iqr = q75 - q25
    lower = q25 - 1.5 * iqr
    upper = q75 + 1.5 * iqr

    return [
        idx for idx in valid_indices
        if float(records[idx]["price_numeric"]) < lower or float(records[idx]["price_numeric"]) > upper
    ]
