from database import get_db

DEFAULTS = {
    "business_name": "",
    "owner_full_name": "",
    "address": "",
    "pib": "",
    "maticni_broj": "",
    "bank_name": "",
    "bank_iban": "",
    "invoice_number_format": "{seq}-{year}-{month}",
    "no_vat_clause": "VAT is not charged in accordance with Article 33 of the VAT Law of the Republic of Serbia.",
    "tax_due_day": "15",
    "bank_form_sifra_osnova": "302",
    "bank_form_place": "Novi Sad",
}


def get_all():
    db = get_db()
    rows = db.execute("SELECT key, value FROM app_settings").fetchall()
    values = dict(DEFAULTS)
    for row in rows:
        values[row["key"]] = row["value"]
    return values


def get(key, default=None):
    return get_all().get(key, default if default is not None else DEFAULTS.get(key))


def set_many(values: dict):
    db = get_db()
    for key, value in values.items():
        db.execute(
            "INSERT INTO app_settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
    db.commit()
