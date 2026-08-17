from flask import Blueprint, flash, redirect, render_template, request, url_for

from services import settings_store

bp = Blueprint("settings", __name__, url_prefix="/settings")

FIELDS = [
    ("business_name", "Название бизнеса / ФИО (radnja)"),
    ("owner_full_name", "Владелец (ФИО)"),
    ("address", "Адрес регистрации"),
    ("pib", "ПИБ"),
    ("maticni_broj", "Матичный номер"),
    ("bank_name", "Банк"),
    ("bank_iban", "IBAN"),
    ("invoice_number_format", "Формат номера инвойса (доступно: {seq}, {year})"),
    ("no_vat_clause", "Оговорка об отсутствии НДС в счёте"),
    ("tax_due_day", "День уплаты налога/взносов (число месяца)"),
]


@bp.route("/", methods=["GET", "POST"])
def edit_settings():
    if request.method == "POST":
        values = {key: request.form.get(key, "").strip() for key, _ in FIELDS}
        settings_store.set_many(values)
        flash("Настройки сохранены.", "success")
        return redirect(url_for("settings.edit_settings"))

    values = settings_store.get_all()
    return render_template("settings/form.html", fields=FIELDS, values=values)
