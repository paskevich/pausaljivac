from datetime import date

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from database import get_db
from services import tax_schedule

bp = Blueprint("tax", __name__, url_prefix="/tax")


@bp.route("/")
def list_resenja():
    db = get_db()
    resenja = db.execute("SELECT * FROM tax_resenja ORDER BY valid_from DESC").fetchall()
    documents_by_resenje = {}
    for r in resenja:
        docs = db.execute(
            "SELECT id, title FROM documents WHERE resenje_id = ? ORDER BY uploaded_at",
            (r["id"],),
        ).fetchall()
        documents_by_resenje[r["id"]] = docs
    return render_template(
        "tax/resenja_list.html", resenja=resenja, documents_by_resenje=documents_by_resenje
    )


@bp.route("/resenja/new", methods=["GET", "POST"])
def new_resenje():
    db = get_db()
    if request.method == "POST":
        form = request.form
        resenje_number = form.get("resenje_number", "").strip()
        valid_from = form.get("valid_from")
        valid_to = form.get("valid_to") or None
        notes = form.get("notes", "").strip()

        try:
            pausal_tax_amount = float(form.get("pausal_tax_amount", "0") or 0)
            pio_contribution = float(form.get("pio_contribution", "0") or 0)
            health_contribution = float(form.get("health_contribution", "0") or 0)
            unemployment_contribution = float(form.get("unemployment_contribution", "0") or 0)
        except ValueError:
            flash("Суммы должны быть числами.", "error")
            return redirect(url_for("tax.new_resenje"))

        if not valid_from:
            flash("Укажите дату начала действия решения.", "error")
            return redirect(url_for("tax.new_resenje"))

        db.execute(
            "INSERT INTO tax_resenja (resenje_number, valid_from, valid_to, "
            "pausal_tax_amount, pio_contribution, health_contribution, "
            "unemployment_contribution, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                resenje_number, valid_from, valid_to, pausal_tax_amount,
                pio_contribution, health_contribution, unemployment_contribution,
                notes,
            ),
        )
        db.commit()
        flash("Решение налоговой добавлено.", "success")
        return redirect(url_for("tax.list_resenja"))

    return render_template("tax/resenje_form.html")


@bp.route("/resenja/<int:resenje_id>/edit", methods=["GET", "POST"])
def edit_resenje(resenje_id):
    db = get_db()
    resenje = db.execute(
        "SELECT * FROM tax_resenja WHERE id = ?", (resenje_id,)
    ).fetchone()
    if resenje is None:
        abort(404)

    if request.method == "POST":
        form = request.form
        resenje_number = form.get("resenje_number", "").strip()
        valid_from = form.get("valid_from")
        valid_to = form.get("valid_to") or None
        notes = form.get("notes", "").strip()

        try:
            pausal_tax_amount = float(form.get("pausal_tax_amount", "0") or 0)
            pio_contribution = float(form.get("pio_contribution", "0") or 0)
            health_contribution = float(form.get("health_contribution", "0") or 0)
            unemployment_contribution = float(form.get("unemployment_contribution", "0") or 0)
        except ValueError:
            flash("Суммы должны быть числами.", "error")
            return redirect(url_for("tax.edit_resenje", resenje_id=resenje_id))

        if not valid_from:
            flash("Укажите дату начала действия решения.", "error")
            return redirect(url_for("tax.edit_resenje", resenje_id=resenje_id))

        db.execute(
            "UPDATE tax_resenja SET resenje_number = ?, valid_from = ?, valid_to = ?, "
            "pausal_tax_amount = ?, pio_contribution = ?, health_contribution = ?, "
            "unemployment_contribution = ?, notes = ? WHERE id = ?",
            (
                resenje_number, valid_from, valid_to, pausal_tax_amount,
                pio_contribution, health_contribution, unemployment_contribution,
                notes, resenje_id,
            ),
        )

        unpaid = db.execute(
            "SELECT id, period_year, period_month FROM tax_payments "
            "WHERE resenje_id = ? AND status != 'paid'",
            (resenje_id,),
        ).fetchall()
        to_delete = [
            p["id"] for p in unpaid
            if date(p["period_year"], p["period_month"], 1).isoformat() < valid_from
            or (valid_to and date(p["period_year"], p["period_month"], 1).isoformat() > valid_to)
        ]
        if to_delete:
            db.executemany(
                "DELETE FROM tax_payments WHERE id = ?", [(i,) for i in to_delete]
            )
            flash(
                f"Удалено неоплаченных платежей вне нового периода действия решения: {len(to_delete)}.",
                "warning",
            )

        db.commit()
        flash("Решение налоговой обновлено.", "success")
        return redirect(url_for("tax.list_resenja"))

    return render_template("tax/resenje_form.html", resenje=resenje)


@bp.route("/resenja/<int:resenje_id>/delete", methods=["GET"])
def confirm_delete_resenje(resenje_id):
    db = get_db()
    resenje = db.execute(
        "SELECT * FROM tax_resenja WHERE id = ?", (resenje_id,)
    ).fetchone()
    if resenje is None:
        abort(404)
    linked_payments = db.execute(
        "SELECT COUNT(*) AS n FROM tax_payments WHERE resenje_id = ?", (resenje_id,)
    ).fetchone()
    linked_documents = db.execute(
        "SELECT COUNT(*) AS n FROM documents WHERE resenje_id = ?", (resenje_id,)
    ).fetchone()
    return render_template(
        "tax/confirm_delete_resenje.html",
        resenje=resenje,
        linked_payments_count=linked_payments["n"],
        linked_documents_count=linked_documents["n"],
    )


@bp.route("/resenja/<int:resenje_id>/delete", methods=["POST"])
def delete_resenje(resenje_id):
    db = get_db()
    resenje = db.execute(
        "SELECT * FROM tax_resenja WHERE id = ?", (resenje_id,)
    ).fetchone()
    if resenje is None:
        abort(404)

    linked_payments = db.execute(
        "SELECT COUNT(*) AS n FROM tax_payments WHERE resenje_id = ?", (resenje_id,)
    ).fetchone()
    if linked_payments["n"]:
        db.execute(
            "UPDATE tax_payments SET resenje_id = NULL WHERE resenje_id = ?", (resenje_id,)
        )
        flash(f"Решение также откреплено от {linked_payments['n']} платеж(ей).", "warning")

    linked_documents = db.execute(
        "SELECT COUNT(*) AS n FROM documents WHERE resenje_id = ?", (resenje_id,)
    ).fetchone()
    if linked_documents["n"]:
        db.execute(
            "UPDATE documents SET resenje_id = NULL WHERE resenje_id = ?", (resenje_id,)
        )
        flash(f"Документы также откреплены от решения: {linked_documents['n']}.", "warning")

    db.execute("DELETE FROM tax_resenja WHERE id = ?", (resenje_id,))
    db.commit()

    flash("Решение налоговой удалено.", "success")
    return redirect(url_for("tax.list_resenja"))


@bp.route("/payments")
def list_payments():
    db = get_db()
    tax_schedule.ensure_tax_payments_for_current_month(db)
    payments = db.execute(
        "SELECT * FROM tax_payments ORDER BY period_year DESC, period_month DESC"
    ).fetchall()
    today = date.today().isoformat()
    return render_template("tax/payments_list.html", payments=payments, today=today)


@bp.route("/payments/<int:payment_id>/mark-paid", methods=["POST"])
def mark_paid(payment_id):
    db = get_db()
    payment = db.execute(
        "SELECT * FROM tax_payments WHERE id = ?", (payment_id,)
    ).fetchone()
    if payment is None:
        abort(404)
    db.execute(
        "UPDATE tax_payments SET status = 'paid', paid_date = ? WHERE id = ?",
        (date.today().isoformat(), payment_id),
    )
    db.commit()
    flash("Платёж отмечен как оплаченный.", "success")
    return redirect(url_for("tax.list_payments"))
