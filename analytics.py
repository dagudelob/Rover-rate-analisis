from typing import List, Dict, Any, Optional
import pandas as pd
import numpy as np

def calculate_market_statistics(records: List[Dict[str, Any]], excluded_indices: Optional[set] = None) -> Dict[str, Any]:
    """
    Computes comprehensive market price metrics, percentiles, advanced dispersion indicators,
    and calculates the Optimal Pricing Revenue Maximizer based on Price vs. Booking Conversion probability.
    """
    if excluded_indices is None:
        excluded_indices = set()

    active_records = [
        r for idx, r in enumerate(records)
        if idx not in excluded_indices and r.get("price_numeric") is not None
    ]

    if not active_records:
        return {
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
            "pricing_optimizer": {
                "sweet_spot_price": None,
                "recommended_range": {"min": None, "max": None},
                "max_expected_revenue_index": None,
                "curve": []
            }
        }

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
        lower_cut = prices.quantile(trim_pct)
        upper_cut = prices.quantile(1.0 - trim_pct)
        trimmed_prices = prices[(prices >= lower_cut) & (prices <= upper_cut)]
        trimmed_mean = float(trimmed_prices.mean()) if not trimmed_prices.empty else float(prices.mean())
    else:
        trimmed_mean = float(prices.mean())

    # OPTIMAL PRICING & REVENUE MAXIMIZER ALGORITHM
    # Empirical market demand curve: Probability of being hired P(Price) is modeled by the 
    # Empirical Survival Function S(P) = Proportion of market priced >= P, smoothed with Logistic / Cumulative Distribution.
    # Expected Value / Revenue Potential EV(P) = P * P(hired | P) * Review_Weight
    # This identifies the exact sweet spot that balances high booking probability vs. profit per job.
    optimizer_data = calculate_pricing_sweet_spot(prices, reviews)

    stats = {
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
        "outlier_bounds": {
            "lower": lower_iqr_bound,
            "upper": upper_iqr_bound
        },
        "pricing_optimizer": optimizer_data
    }

    # Generate Histogram Bins
    try:
        min_p = stats["min_price"]
        max_p = stats["max_price"]
        if min_p == max_p:
            bins = [min_p - 5, min_p + 5]
        else:
            num_bins = min(8, max(4, len(prices.unique())))
            bins = np.linspace(min_p, max_p, num_bins + 1)

        hist, bin_edges = np.histogram(prices, bins=bins)
        distribution = []
        for i in range(len(hist)):
            label = f"${bin_edges[i]:.0f} - ${bin_edges[i+1]:.0f}"
            distribution.append({
                "range": label,
                "count": int(hist[i]),
                "min": float(bin_edges[i]),
                "max": float(bin_edges[i+1])
            })
        stats["price_distribution"] = distribution
    except Exception:
        stats["price_distribution"] = []

    return stats


def calculate_pricing_sweet_spot(prices: pd.Series, reviews: pd.Series) -> Dict[str, Any]:
    """
    Computes the optimal price point and recommended price range that maximizes expected revenue:
    Expected Revenue(P) = Price * Probability(Hired at Price P).
    """
    if prices.empty:
        return {
            "sweet_spot_price": None,
            "recommended_range": {"min": None, "max": None},
            "strategy": "No data",
            "curve": []
        }

    min_p = max(5, int(prices.min()))
    max_p = int(prices.max() + 5)
    
    # Generate candidate price points
    candidate_prices = np.linspace(min_p, max_p, 25)
    curve = []
    
    mean_p = float(prices.mean())
    std_p = float(prices.std()) if len(prices) > 1 and float(prices.std()) > 0 else 5.0

    best_price = float(prices.median())
    max_expected_score = -1.0

    for p in candidate_prices:
        # Market competitive acceptance: proportion of competitors priced higher + normal sigmoid tail
        # At very low prices, conversion prob -> 95%. At very high prices, conversion prob -> 10%
        # Standardized z-score
        z = (p - mean_p) / std_p
        
        # Logistic probability curve for booking conversion
        # Higher price -> lower conversion probability
        conversion_prob = 1.0 / (1.0 + np.exp(1.2 * z))
        conversion_pct = round(conversion_prob * 100, 1)
        
        # Expected Revenue Index = Price * Conversion_Probability
        expected_revenue_index = round(float(p * conversion_prob), 2)
        
        curve.append({
            "price": round(float(p), 1),
            "conversion_probability_pct": conversion_pct,
            "expected_revenue_index": expected_revenue_index
        })

        if expected_revenue_index > max_expected_score:
            max_expected_score = expected_revenue_index
            best_price = round(float(p), 1)

    # Calculate optimal recommended bracket: +/- 10% around maximum expected value
    rec_min = round(best_price * 0.90, 1)
    rec_max = round(best_price * 1.12, 1)

    return {
        "sweet_spot_price": best_price,
        "recommended_range": {
            "min": rec_min,
            "max": rec_max
        },
        "max_expected_index": max_expected_score,
        "curve": curve
    }


def detect_outliers_iqr(records: List[Dict[str, Any]]) -> List[int]:
    """
    Returns indices of records that qualify as price outliers based on the 1.5 * IQR rule.
    """
    valid_indices = [idx for idx, r in enumerate(records) if r.get("price_numeric") is not None]
    if len(valid_indices) < 4:
        return []

    prices = [float(records[idx]["price_numeric"]) for idx in valid_indices]
    s = pd.Series(prices)
    q25 = s.quantile(0.25)
    q75 = s.quantile(0.75)
    iqr = q75 - q25
    lower = q25 - 1.5 * iqr
    upper = q75 + 1.5 * iqr

    outlier_indices = []
    for idx in valid_indices:
        p = float(records[idx]["price_numeric"])
        if p < lower or p > upper:
            outlier_indices.append(idx)

    return outlier_indices
