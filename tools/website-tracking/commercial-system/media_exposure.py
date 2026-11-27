"""Offline G050 planning calculation for standard Search budget pools in AED."""

from collections.abc import Iterable


def _fils(value: int, field: str, *, allow_zero: bool = False) -> int:
    if type(value) is not int or value < (0 if allow_zero else 1):
        raise ValueError(f"{field} must be an integer amount in fils")
    return value


def _comparison(exposure: int | None, ceiling: int | None) -> dict:
    if exposure is None or ceiling is None:
        return {"status": "UNKNOWN", "headroom_fils": None}
    return {
        "status": "WITHIN_CEILING" if exposure <= ceiling else "EXCEEDS_CEILING",
        "headroom_fils": ceiling - exposure,
    }


def standard_search_exposure(
    pools: Iterable[tuple[str, int]],
    expected_average_daily_fils: int,
    *,
    unchanged_full_month: bool,
    approved_monthly_media_fils: int | None = None,
    approved_monthly_cash_risk_fils: int | None = None,
    verified_monthly_cash_exposure_fils: int | None = None,
) -> dict:
    """Project media exposure from one budget per distinct standard Search pool.

    Inputs and media outputs exclude VAT. A separately verified cash exposure,
    including applicable taxes and charges, must refer to the same scope and
    month as its approved cash ceiling. The caller owns those evidence checks.
    """
    expected = _fils(expected_average_daily_fils, "expected_average_daily_fils")
    if type(unchanged_full_month) is not bool:
        raise ValueError("unchanged_full_month must be boolean")
    if approved_monthly_media_fils is not None:
        _fils(approved_monthly_media_fils, "approved_monthly_media_fils")
    if approved_monthly_cash_risk_fils is not None:
        _fils(approved_monthly_cash_risk_fils, "approved_monthly_cash_risk_fils")
    if verified_monthly_cash_exposure_fils is not None:
        _fils(verified_monthly_cash_exposure_fils, "verified_monthly_cash_exposure_fils", allow_zero=True)

    pool_amounts = {}
    for pool_id, amount in pools:
        if not isinstance(pool_id, str) or not pool_id or pool_id != pool_id.strip():
            raise ValueError("budget pool identifier must be a nonempty, unpadded string")
        if pool_id in pool_amounts:
            raise ValueError("duplicate budget pool")
        pool_amounts[pool_id] = _fils(amount, "pool average daily budget")
    if sum(pool_amounts.values()) != expected:
        raise ValueError("budget pools do not reconcile to the expected average daily budget")

    daily = None
    monthly = None
    if unchanged_full_month:
        daily = expected * 2
        # Round each pool upward to a whole fil for conservative planning.
        monthly = sum((amount * 304 + 9) // 10 for amount in pool_amounts.values())
    return {
        "currency": "AED",
        "media_excludes_vat": True,
        "budget_pool_count": len(pool_amounts),
        "budget_pool_average_daily_fils": dict(sorted(pool_amounts.items())),
        "aggregate_average_daily_fils": expected,
        "scenario_status": "MODELED_STANDARD_FULL_MONTH" if unchanged_full_month else "UNMODELED_BUDGET_HISTORY",
        "modeled_daily_media_fils": daily,
        "modeled_monthly_media_fils": monthly,
        "approved_monthly_media_fils": approved_monthly_media_fils,
        "monthly_media_comparison": _comparison(monthly, approved_monthly_media_fils),
        "verified_monthly_cash_exposure_fils": verified_monthly_cash_exposure_fils,
        "approved_monthly_cash_risk_fils": approved_monthly_cash_risk_fils,
        "monthly_cash_comparison": _comparison(verified_monthly_cash_exposure_fils, approved_monthly_cash_risk_fils),
        "release_authorized_by_calculation": False,
    }
