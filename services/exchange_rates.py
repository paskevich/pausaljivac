import requests

import config


def get_rate(db, currency, date_str, manual_rate=None):
    """Resolve an RSD exchange rate for `currency` on `date_str` (YYYY-MM-DD).

    Order: manual override > exact cached match > best-effort NBS fetch (disabled
    by default, see config.ENABLE_NBS_AUTO_FETCH) > nearest earlier cached date.
    Returns a dict with rate/date/source/fallback, or None if nothing is available.
    """
    if currency == "RSD":
        return {"rate": 1.0, "date": date_str, "source": "same_currency", "fallback": False}

    if manual_rate:
        rate = float(manual_rate)
        _save_rate(db, date_str, currency, rate, "manual")
        return {"rate": rate, "date": date_str, "source": "manual", "fallback": False}

    row = db.execute(
        "SELECT rsd_rate, source FROM exchange_rates WHERE rate_date = ? AND currency = ?",
        (date_str, currency),
    ).fetchone()
    if row:
        return {
            "rate": row["rsd_rate"],
            "date": date_str,
            "source": row["source"],
            "fallback": False,
        }

    fetched = _fetch_from_nbs(currency, date_str)
    if fetched is not None:
        _save_rate(db, date_str, currency, fetched, "nbs_fetch")
        return {"rate": fetched, "date": date_str, "source": "nbs_fetch", "fallback": False}

    fallback = db.execute(
        "SELECT rsd_rate, rate_date, source FROM exchange_rates "
        "WHERE currency = ? AND rate_date <= ? ORDER BY rate_date DESC LIMIT 1",
        (currency, date_str),
    ).fetchone()
    if fallback:
        return {
            "rate": fallback["rsd_rate"],
            "date": fallback["rate_date"],
            "source": fallback["source"],
            "fallback": True,
        }

    return None


def _fetch_from_nbs(currency, date_str):
    if not config.ENABLE_NBS_AUTO_FETCH:
        return None
    url = f"{config.NBS_RATE_API_BASE}/currencies/{currency.lower()}/rates/{date_str}"
    try:
        response = requests.get(url, timeout=config.NBS_RATE_API_TIMEOUT)
        if response.status_code != 200:
            return None
        data = response.json()
        return float(data["exchange_middle"])
    except (requests.RequestException, ValueError, KeyError, TypeError):
        return None


def _save_rate(db, date_str, currency, rate, source):
    db.execute(
        "INSERT INTO exchange_rates (rate_date, currency, rsd_rate, source) "
        "VALUES (?, ?, ?, ?) "
        "ON CONFLICT(rate_date, currency) DO UPDATE SET "
        "rsd_rate = excluded.rsd_rate, source = excluded.source, fetched_at = CURRENT_TIMESTAMP",
        (date_str, currency, rate, source),
    )
    db.commit()
