from flask import Blueprint, flash, redirect, render_template, request, url_for

import config
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
    (
        "invoice_number_format",
        "Формат номера инвойса (доступно: {seq}, {year}, {month}, {day}; "
        "для дополнения нулями — {month:02d}, {day:02d}, {seq:03d})",
    ),
    ("no_vat_clause", "Оговорка об отсутствии НДС в счёте"),
    ("tax_due_day", "День уплаты налога/взносов (число месяца)"),
    ("bank_form_sifra_osnova", "Šifra osnova по умолчанию для «Obaveštenje o prilivu»"),
    ("bank_form_place", "Место подписания для «Obaveštenje o prilivu»"),
]


@bp.route("/", methods=["GET", "POST"])
def edit_settings():
    if request.method == "POST":
        values = {key: request.form.get(key, "").strip() for key, _ in FIELDS}
        settings_store.set_many(values)
        flash("Настройки сохранены.", "success")
        return redirect(url_for("settings.edit_settings"))

    values = settings_store.get_all()
    return render_template(
        "settings/form.html", fields=FIELDS, values=values,
        has_signature=config.SIGNATURE_PATH.exists(),
    )


@bp.route("/signature", methods=["POST"])
def upload_signature():
    file = request.files.get("signature")
    if not file or file.filename == "":
        flash("Выберите PNG-файл подписи.", "error")
        return redirect(url_for("settings.edit_settings"))
    if file.mimetype != "image/png":
        flash("Подпись должна быть в формате PNG.", "error")
        return redirect(url_for("settings.edit_settings"))

    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    file.save(config.SIGNATURE_PATH)
    flash("Подпись сохранена.", "success")
    return redirect(url_for("settings.edit_settings"))
