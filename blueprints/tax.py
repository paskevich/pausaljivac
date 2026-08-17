from datetime import date

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from database import get_db
from blueprints.documents import save_uploaded_file
from services import tax_schedule

bp = Blueprint("tax", __name__, url_prefix="/tax")


@bp.route("/")
def list_resenja():
    db = get_db()
    resenja = db.execute(
        "SELECT tax_resenja.*, documents.title AS document_title, documents.id AS doc_id "
        "FROM tax_resenja LEFT JOIN documents ON documents.id = tax_resenja.document_id "
        "ORDER BY valid_from DESC"
    ).fetchall()
    return render_template("tax/resenja_list.html", resenja=resenja)


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

        document_id = None
        file = request.files.get("file")
        if file and file.filename:
            document_id = save_uploaded_file(
                db, file, "resenje",
                title=f"Rešenje {resenje_number}".strip(),
                period_year=int(valid_from[:4]),
            )

        db.execute(
            "INSERT INTO tax_resenja (resenje_number, valid_from, valid_to, "
            "pausal_tax_amount, pio_contribution, health_contribution, "
            "unemployment_contribution, document_id, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                resenje_number, valid_from, valid_to, pausal_tax_amount,
                pio_contribution, health_contribution, unemployment_contribution,
                document_id, notes,
            ),
        )
        db.commit()
        flash("Решение налоговой добавлено.", "success")
        return redirect(url_for("tax.list_resenja"))

    return render_template("tax/resenje_form.html")


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
