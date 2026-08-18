import re
from datetime import date

import fitz

# All coordinates below were reverse-engineered from a real ALTA Banka
# "Obaveštenje o prilivu" template (no AcroForm fields — this is a flat,
# bank-generated PDF). To stay robust if the boilerplate text above the
# table wraps to a different number of lines (long remitter name, long
# payment reference), row-1 cells are positioned relative to the
# "PODACI" table-header word found fresh in each uploaded PDF, not at
# absolute page coordinates. Page 2 fields are anchored the same way,
# off the "Mesto"/"Pecat" labels.

ROW1_OFFSETS = {
    # field: (dx from anchor x0, dy from anchor y0 to text baseline, base fontsize)
    "redni_broj": (6.3, 55.6, 12),
    "sifra_osnova": (31.3, 56.4, 12),
    "invoice_number": (62.3, 47.7, 7),
    "date": (116.8, 54.0, 7),
    "description": (191.7, 54.8, 7),
    "amount": (377.4, 57.2, 9),
}
INVOICE_NUMBER_COL_WIDTH = 40  # pt, for shrink-to-fit

PLACE_DATE_OFFSET = (-30.1, -8.3, 12)  # relative to "Mesto" word
SIGNATURE_OFFSET = (-13.6, -39.1)  # relative to "Pecat" word, top-left of image
SIGNATURE_SIZE = (161, 35)  # width, height in pt

FONT = "helv"


def _find_word(page, text):
    for w in page.get_text("words"):
        if w[4] == text:
            return w[:4]
    return None


def parse_blank_form(pdf_bytes):
    """Extract what the bank already pre-filled: invoice number and amount."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    text = doc[0].get_text()
    doc.close()

    invoice_match = re.search(r"INVOICE NUMBER:\s*(\S+)", text)
    amount_match = re.search(r"^Iznos\n([A-Z]{3})\s+([\d,]+\.\d{2})$", text, re.MULTILINE)

    return {
        "invoice_number": invoice_match.group(1) if invoice_match else "",
        "currency": amount_match.group(1) if amount_match else "",
        "amount_display": amount_match.group(2) if amount_match else "",
    }


def _shrink_to_fit(page, text, max_width, base_size, min_size=4):
    size = base_size
    while size > min_size and fitz.get_text_length(text, fontname=FONT, fontsize=size) > max_width:
        size -= 0.5
    return size


def fill_form(pdf_bytes, *, sifra_osnova, invoice_number, invoice_date_display,
              description, currency, amount_display, place, sign_date_display,
              signature_png_bytes):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    page0 = doc[0]
    anchor = _find_word(page0, "PODACI")
    if anchor is None:
        raise ValueError("Не найден заголовок таблицы «PODACI ZA STATISTIKU» — формат бланка не распознан.")
    ax, ay = anchor[0], anchor[1]

    def put(field, text, size=None):
        dx, dy, base_size = ROW1_OFFSETS[field]
        fs = size or base_size
        page0.insert_text((ax + dx, ay + dy), text, fontsize=fs, fontname=FONT)

    put("redni_broj", "1")
    put("sifra_osnova", str(sifra_osnova))
    inv_size = _shrink_to_fit(page0, invoice_number, INVOICE_NUMBER_COL_WIDTH, ROW1_OFFSETS["invoice_number"][2])
    put("invoice_number", invoice_number, size=inv_size)
    put("date", invoice_date_display)
    put("description", f"Uplata po Fakturi {invoice_number}")
    put("amount", f"{currency} {amount_display}")

    page1 = doc[1]
    mesto = _find_word(page1, "Mesto")
    pecat = _find_word(page1, "Pecat")
    if mesto is None or pecat is None:
        raise ValueError("Не найдены метки «Mesto i datum» / «Pecat i potpis» — формат бланка не распознан.")

    dx, dy, size = PLACE_DATE_OFFSET
    page1.insert_text(
        (mesto[0] + dx, mesto[1] + dy), f"{place}, {sign_date_display}",
        fontsize=size, fontname=FONT,
    )

    dx, dy = SIGNATURE_OFFSET
    w, h = SIGNATURE_SIZE
    sig_rect = fitz.Rect(pecat[0] + dx, pecat[1] + dy, pecat[0] + dx + w, pecat[1] + dy + h)
    page1.insert_image(sig_rect, stream=signature_png_bytes)

    out = doc.tobytes()
    doc.close()
    return out


def today_display():
    return date.today().strftime("%d.%m.%Y")
