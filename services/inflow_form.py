import re
from datetime import date

import fitz

# Row 1 of "PODACI ZA STATISTIKU" is located relative to the "PODACI"
# table-header word found fresh in each uploaded PDF (not at absolute page
# coordinates), so the fill stays correct if the boilerplate text above the
# table wraps to a different number of lines. Within the row, each field's
# actual cell rectangle is then measured from the PDF's own grid lines
# (not a hardcoded offset) and the text is centered independently in it —
# a single shared baseline offset doesn't work here because fields use
# different font sizes, so they'd never line up in the same row visually.
# Page 2 fields are anchored the same way, off the "Mesto"/"Pečat" labels.

ROW1_COLUMN_HINTS = {
    # field: rough dx from anchor x0, just enough to pick out its column
    "redni_broj": 6.3,
    "sifra_osnova": 31.3,
    "invoice_number": 62.3,
    "date": 116.8,
    "description": 191.7,
    "amount": 377.4,
}
ROW1_FONT_SIZES = {
    "redni_broj": 12,
    "sifra_osnova": 12,
    "invoice_number": 9,
    "date": 9,
    "description": 9,
    "amount": 9,
}
CELL_PADDING = 2  # pt, horizontal margin kept clear of the grid lines when shrinking to fit

PLACE_DATE_OFFSET = (-30.1, -8.3, 12)  # relative to "Mesto" word
SIGNATURE_OFFSET = (-13.6, -39.1)  # relative to "Pečat" word, top-left of image
SIGNATURE_SIZE = (161, 35)  # width, height in pt

FONT = "helv"
_FONT_METRICS = fitz.Font(FONT)


def _find_word(page, text):
    for w in page.get_text("words"):
        if w[4] == text:
            return w[:4]
    return None


def _find_word_anywhere(doc, text):
    """Search every page for `text`, since some bank templates put the whole
    form (including the signature block) on a single page while others split
    it across two."""
    for page in doc:
        w = _find_word(page, text)
        if w is not None:
            return page, w
    return None, None


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


def _horizontal_lines(page, y_min, y_max):
    """(y, x0, x1) for every roughly-horizontal vector line segment on the
    page with y in [y_min, y_max]."""
    segs = []
    for d in page.get_drawings():
        for item in d["items"]:
            if item[0] == "l":
                p1, p2 = item[1], item[2]
                if abs(p1.y - p2.y) < 0.5:
                    y = (p1.y + p2.y) / 2
                    if y_min <= y <= y_max:
                        x0, x1 = sorted((p1.x, p2.x))
                        segs.append((y, x0, x1))
    return segs


def _row1_cells(page, anchor):
    """Locate row 1's cell rectangles under the "PODACI" table by finding the
    grid lines directly below the "Redni broj" column header. This is robust
    to single- vs double-ruled borders (some ALTA Banka templates draw table
    borders as two close parallel strokes) and to the table's absolute
    position on the page, which shifts with the boilerplate text above it."""
    ax, ay = anchor[0], anchor[1]
    header_word = _find_word(page, "broj")
    if header_word is None:
        raise ValueError("Не найден заголовок столбца «Redni broj» — формат бланка не распознан.")

    segs = _horizontal_lines(page, ay, ay + 150)

    row_ys = sorted({
        round(y, 1) for y, x0, x1 in segs
        if x0 - 1 <= header_word[0] <= x1 + 1 and y > header_word[3]
    })
    # Table borders are drawn as two close parallel strokes (~2pt apart), not
    # a single line, so cluster them before pairing dividers with rows.
    groups = []
    for y in row_ys:
        if not groups or y - groups[-1][-1] > 3.0:
            groups.append([y])
        else:
            groups[-1].append(y)
    if len(groups) < 2:
        raise ValueError("Не удалось определить границы строки таблицы — формат бланка не распознан.")
    top, bottom = max(groups[0]), min(groups[1])

    cells = {}
    for field, dx in ROW1_COLUMN_HINTS.items():
        fx = ax + dx
        col = next(
            ((x0, x1) for y, x0, x1 in segs if abs(y - top) < 1.5 and x0 - 1 <= fx <= x1 + 1),
            None,
        )
        if col is None:
            raise ValueError(f"Не удалось определить границы столбца «{field}» — формат бланка не распознан.")
        cells[field] = fitz.Rect(col[0], top, col[1], bottom)
    return cells


def _center_text(page, rect, text, base_size, min_size=4):
    size = base_size
    avail = rect.width - 2 * CELL_PADDING
    while size > min_size and fitz.get_text_length(text, fontname=FONT, fontsize=size) > avail:
        size -= 0.5

    text_width = fitz.get_text_length(text, fontname=FONT, fontsize=size)
    x = rect.x0 + (rect.width - text_width) / 2
    text_height = (_FONT_METRICS.ascender - _FONT_METRICS.descender) * size
    y = rect.y0 + (rect.height - text_height) / 2 + _FONT_METRICS.ascender * size
    page.insert_text((x, y), text, fontsize=size, fontname=FONT)


def fill_form(pdf_bytes, *, sifra_osnova, invoice_number, invoice_date_display,
              description, currency, amount_display, place, sign_date_display,
              signature_png_bytes):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    page0 = doc[0]
    anchor = _find_word(page0, "PODACI")
    if anchor is None:
        raise ValueError("Не найден заголовок таблицы «PODACI ZA STATISTIKU» — формат бланка не распознан.")

    cells = _row1_cells(page0, anchor)
    row1_values = {
        "redni_broj": "1",
        "sifra_osnova": str(sifra_osnova),
        "invoice_number": invoice_number,
        "date": invoice_date_display,
        "description": f"Uplata po Fakturi {invoice_number}",
        "amount": f"{currency} {amount_display}",
    }
    for field, text in row1_values.items():
        _center_text(page0, cells[field], text, ROW1_FONT_SIZES[field])

    mesto_page, mesto = _find_word_anywhere(doc, "Mesto")
    pecat_page, pecat = _find_word_anywhere(doc, "Pečat")
    if mesto is None or pecat is None:
        raise ValueError("Не найдены метки «Mesto i datum» / «Pečat i potpis» — формат бланка не распознан.")

    dx, dy, size = PLACE_DATE_OFFSET
    mesto_page.insert_text(
        (mesto[0] + dx, mesto[1] + dy), f"{place}, {sign_date_display}",
        fontsize=size, fontname=FONT,
    )

    dx, dy = SIGNATURE_OFFSET
    w, h = SIGNATURE_SIZE
    sig_rect = fitz.Rect(pecat[0] + dx, pecat[1] + dy, pecat[0] + dx + w, pecat[1] + dy + h)
    pecat_page.insert_image(sig_rect, stream=signature_png_bytes)

    out = doc.tobytes()
    doc.close()
    return out


def today_display():
    return date.today().strftime("%d.%m.%Y")
