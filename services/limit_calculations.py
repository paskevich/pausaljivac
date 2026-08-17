from datetime import date, timedelta

import config


def calendar_year_totals(db):
    rows = db.execute(
        "SELECT strftime('%Y', issue_date) AS yr, SUM(amount_rsd) AS total "
        "FROM invoices WHERE status != 'cancelled' AND amount_rsd IS NOT NULL "
        "GROUP BY yr ORDER BY yr DESC"
    ).fetchall()
    return [{"year": int(r["yr"]), "total": r["total"] or 0} for r in rows]


def current_calendar_year_total(db):
    current_year = str(date.today().year)
    row = db.execute(
        "SELECT SUM(amount_rsd) AS total FROM invoices "
        "WHERE status != 'cancelled' AND amount_rsd IS NOT NULL "
        "AND strftime('%Y', issue_date) = ?",
        (current_year,),
    ).fetchone()
    return row["total"] or 0


def rolling_365_day_total(db):
    cutoff = (date.today() - timedelta(days=365)).isoformat()
    today = date.today().isoformat()
    row = db.execute(
        "SELECT SUM(amount_rsd) AS total FROM invoices "
        "WHERE status != 'cancelled' AND amount_rsd IS NOT NULL "
        "AND issue_date > ? AND issue_date <= ?",
        (cutoff, today),
    ).fetchone()
    return row["total"] or 0


def limit_status(total, limit):
    ratio = total / limit if limit else 0
    if ratio >= config.LIMIT_DANGER_RATIO:
        level = "danger"
    elif ratio >= config.LIMIT_WARN_RATIO:
        level = "warn"
    else:
        level = "ok"
    return {
        "total": total,
        "limit": limit,
        "ratio": min(ratio, 1.0),
        "percent": round(ratio * 100, 1),
        "level": level,
    }


def get_dashboard_limits(db):
    pausal = limit_status(current_calendar_year_total(db), config.PAUSAL_LIMIT_RSD)
    vat = limit_status(rolling_365_day_total(db), config.VAT_THRESHOLD_RSD)
    return {
        "pausal": pausal,
        "vat": vat,
        "by_year": calendar_year_totals(db),
    }
