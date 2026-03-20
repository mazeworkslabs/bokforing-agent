"""PDF generation for customer invoices using reportlab."""
import base64
from io import BytesIO
from decimal import Decimal
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors


def format_amount(amount: Decimal) -> str:
    """Format amount with Swedish number format."""
    return f"{amount:,.2f}".replace(",", " ").replace(".", ",")


def generate_invoice_pdf(invoice: dict, company: dict) -> BytesIO:
    """Generate PDF for a customer invoice.

    Args:
        invoice: Invoice dict with keys: invoice_number, invoice_date, due_date,
                 is_credit_note, reference, party (dict), lines (list)
        company: Company dict with keys: name, org_number, address, postal_code,
                 city, email, bankgiro, plusgiro, iban, bic, f_skatt, vat_number, website
    """
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    party = invoice.get("party", {})
    is_credit = invoice.get("is_credit_note", False)

    # --- HEADER ---
    c.setFont("Helvetica-Bold", 24)
    title = "KREDITFAKTURA" if is_credit else "FAKTURA"
    c.drawString(40, height - 50, title)

    c.setFont("Helvetica", 10)
    c.drawString(40, height - 70, f"Fakturanummer: {invoice.get('invoice_number', '')}")
    c.drawString(40, height - 82, f"Fakturadatum: {invoice.get('invoice_date', '')}")
    c.drawString(40, height - 94, f"Förfallodatum: {invoice.get('due_date', '')}")
    payment_terms = party.get("payment_terms", 30)
    c.drawString(40, height - 106, f"Betalningsvillkor: {payment_terms} dagar netto")

    # --- FRÅN (höger sida) ---
    c.setFont("Helvetica-Bold", 11)
    c.drawRightString(width - 40, height - 50, company.get("name", ""))
    c.setFont("Helvetica", 9)
    y_from = height - 62
    if company.get("org_number"):
        c.drawRightString(width - 40, y_from, f"Org.nr: {company['org_number']}")
        y_from -= 12
    if company.get("address"):
        c.drawRightString(width - 40, y_from, company["address"])
        y_from -= 12
    if company.get("postal_code") or company.get("city"):
        c.drawRightString(width - 40, y_from, f"{company.get('postal_code', '')} {company.get('city', '')}".strip())
        y_from -= 12
    if company.get("email"):
        c.drawRightString(width - 40, y_from, company["email"])

    # --- TILL ---
    c.setFont("Helvetica-Bold", 10)
    c.drawString(40, height - 150, "Faktureras till:")
    c.setFont("Helvetica", 10)
    y_to = height - 165
    c.drawString(40, y_to, party.get("name", ""))
    y_to -= 12
    if party.get("org_number"):
        c.drawString(40, y_to, f"Org.nr: {party['org_number']}")
        y_to -= 12
    if party.get("address"):
        for line in str(party["address"]).split("\n"):
            c.drawString(40, y_to, line)
            y_to -= 12
    if party.get("postal_code") or party.get("city"):
        c.drawString(40, y_to, f"{party.get('postal_code', '')} {party.get('city', '')}".strip())
        y_to -= 12

    if invoice.get("reference"):
        y_to -= 8
        c.drawString(40, y_to, f"Er referens: {invoice['reference']}")

    # --- LINJE ---
    c.setStrokeColor(colors.grey)
    c.line(40, height - 255, width - 40, height - 255)

    # --- TABELL HEADER ---
    y = height - 280
    c.setFont("Helvetica-Bold", 9)
    c.drawString(40, y, "Beskrivning")
    c.drawRightString(330, y, "Antal")
    c.drawRightString(400, y, "À-pris")
    c.drawRightString(460, y, "Moms")
    c.drawRightString(width - 40, y, "Belopp")

    c.line(40, y - 5, width - 40, y - 5)

    # --- RADER ---
    c.setFont("Helvetica", 9)
    subtotal = Decimal(0)
    vat_totals = {}

    for line in invoice.get("lines", []):
        y -= 18
        qty = Decimal(str(line.get("quantity", 0)))
        unit_price = Decimal(str(line.get("unit_price", 0)))
        vat_rate = Decimal(str(line.get("vat_rate", 0)))

        line_amount = qty * unit_price
        line_vat = line_amount * vat_rate / 100
        subtotal += line_amount
        vat_totals[vat_rate] = vat_totals.get(vat_rate, Decimal(0)) + line_vat

        desc = line.get("description", "")
        desc = desc[:50] + "..." if len(desc) > 50 else desc
        c.drawString(40, y, desc)
        c.drawRightString(330, y, f"{qty:g}")
        c.drawRightString(400, y, format_amount(unit_price))
        c.drawRightString(460, y, f"{vat_rate}%")
        c.drawRightString(width - 40, y, format_amount(line_amount))

    # --- LINJE ---
    y -= 15
    c.line(40, y, width - 40, y)

    # --- SUMMERING ---
    y -= 25
    c.setFont("Helvetica", 10)
    c.drawString(330, y, "Netto exkl. moms:")
    c.drawRightString(width - 40, y, f"{format_amount(subtotal)} kr")

    total_vat = Decimal(0)
    for vat_rate, vat_amount in sorted(vat_totals.items()):
        if vat_amount > 0:
            y -= 15
            total_vat += vat_amount
            c.drawString(330, y, f"Moms {vat_rate}%:")
            c.drawRightString(width - 40, y, f"{format_amount(vat_amount)} kr")

    total = subtotal + total_vat
    y -= 20
    c.setFont("Helvetica-Bold", 12)
    payment_label = "ATT KREDITERA:" if is_credit else "ATT BETALA:"
    c.drawString(330, y, payment_label)
    c.drawRightString(width - 40, y, f"{format_amount(total)} kr")

    if invoice.get("vat_note"):
        y -= 25
        c.setFont("Helvetica-Oblique", 8)
        c.setFillColor(colors.grey)
        c.drawString(40, y, invoice["vat_note"])
        c.setFillColor(colors.black)

    # --- BETALNINGSINFO ---
    y -= 60
    c.setFillColor(colors.Color(0.95, 0.95, 0.95))
    c.rect(40, y - 60, width - 80, 70, fill=True, stroke=False)

    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, y, "Betalningsinformation")

    c.setFont("Helvetica", 9)
    y -= 15
    if company.get("bankgiro"):
        c.drawString(50, y, f"Bankgiro: {company['bankgiro']}")
    elif company.get("plusgiro"):
        c.drawString(50, y, f"Plusgiro: {company['plusgiro']}")
    elif company.get("iban"):
        c.drawString(50, y, f"IBAN: {company['iban']}")
        if company.get("bic"):
            y -= 12
            c.drawString(50, y, f"BIC: {company['bic']}")

    c.drawString(300, y + 15, f"OCR/Referens: {invoice.get('invoice_number', '')}")
    c.drawString(300, y + 3, f"Förfallodatum: {invoice.get('due_date', '')}")
    amount_label = "Att kreditera" if is_credit else "Att betala"
    c.drawString(300, y - 9, f"{amount_label}: {format_amount(total)} kr")

    # --- FOOTER ---
    footer_parts = [company.get("name", "")]
    if company.get("org_number"):
        footer_parts.append(f"Org.nr: {company['org_number']}")
    if company.get("f_skatt"):
        footer_parts.append("Godkänd för F-skatt")
    if company.get("vat_number"):
        footer_parts.append(f"Moms.nr: {company['vat_number']}")

    c.setFont("Helvetica", 8)
    c.setFillColor(colors.grey)
    c.drawCentredString(width / 2, 40, " | ".join(footer_parts))

    footer2_parts = []
    if company.get("email"):
        footer2_parts.append(company["email"])
    if company.get("website"):
        footer2_parts.append(company["website"])
    if footer2_parts:
        c.drawCentredString(width / 2, 28, " | ".join(footer2_parts))

    c.save()
    buffer.seek(0)
    return buffer
