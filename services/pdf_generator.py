from flask import render_template
from weasyprint import HTML


def generate_invoice_pdf(context, output_path):
    html_str = render_template("invoices/pdf_invoice.html", **context)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=html_str).write_pdf(str(output_path))


def generate_kpo_pdf(context):
    html_str = render_template("reports/kpo.html", **context)
    return HTML(string=html_str).write_pdf()
