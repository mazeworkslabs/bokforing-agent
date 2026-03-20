---
name: generate-invoice-pdf
description: Generate and book Swedish customer invoices. Use when user wants to create a faktura, bill a customer, or generate an invoice PDF.
---

# Generate Customer Invoice

Create Swedish-compliant invoice PDFs, validate, upload, and book to the accounting system.

## Workflow

### 1. Get company and context
```bash
# Get user's companies
curl -s -H "X-API-Key: $BOKFORING_API_KEY" \
  "https://bokforing.example.com/users/me/companies" | jq '.'

# Get company details (use company_id from above)
curl -s -H "X-API-Key: $BOKFORING_API_KEY" \
  "https://bokforing.example.com/companies/{company_id}" | jq '.'
```

### 2. Get or create customer (party)
```bash
# List existing parties
curl -s -H "X-API-Key: $BOKFORING_API_KEY" \
  "https://bokforing.example.com/companies/{company_id}/parties" | jq '.'

# Create new party if needed
curl -X POST -H "X-API-Key: $BOKFORING_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "Kund AB", "org_number": "556123-4567", "address": "Gatan 1", "postal_code": "123 45", "city": "Stockholm", "email": "faktura@kund.se", "payment_terms": 30}' \
  "https://bokforing.example.com/companies/{company_id}/parties"
```

### 3. Get next invoice number
```bash
# Get latest customer invoice to determine next number
curl -s -H "X-API-Key: $BOKFORING_API_KEY" \
  "https://bokforing.example.com/companies/{company_id}/invoices?type=customer&limit=1" | jq '.[0].invoice_number'
```

**Follow the existing format** from the last invoice unless user specifies otherwise. Parse the pattern and increment accordingly.

Examples:
- Last: `2612003` → Next: `2612004` 


**If no previous invoices exist**, ask user for preferred format or default to `{YYMM}{NNN}`.

### 4. Validate required information

**Swedish invoice requirements (Skatteverket):**
- [ ] Seller name, address, org number
- [ ] Seller VAT number (SE + org number without dash + 01)
- [ ] Buyer name and address
- [ ] Unique invoice number
- [ ] Invoice date
- [ ] Description of goods/services
- [ ] Quantity and unit price per line
- [ ] VAT rate per line
- [ ] Net amount (excl. VAT)
- [ ] VAT amount per rate
- [ ] Total amount (incl. VAT)
- [ ] Due date
- [ ] Payment info (bankgiro/plusgiro/IBAN)

**Validation checks before generating:**
```python
def validate_invoice_data(company, party, lines):
    errors = []
    # Company
    if not company.get("name"): errors.append("Missing company name")
    if not company.get("org_number"): errors.append("Missing company org number")
    if not company.get("vat_number"): errors.append("Missing company VAT number")
    if not (company.get("bankgiro") or company.get("plusgiro") or company.get("iban")):
        errors.append("Missing payment info (bankgiro/plusgiro/IBAN)")
    # Party
    if not party.get("name"): errors.append("Missing customer name")
    # Lines
    if not lines: errors.append("No invoice lines")
    for i, line in enumerate(lines):
        if not line.get("description"): errors.append(f"Line {i+1}: missing description")
        if line.get("quantity", 0) <= 0: errors.append(f"Line {i+1}: invalid quantity")
        if line.get("unit_price", 0) <= 0: errors.append(f"Line {i+1}: invalid unit price")
    return errors
```

### 5. Generate PDF
```python
from invoice_pdf import generate_invoice_pdf
from datetime import date, timedelta
from decimal import Decimal

invoice = {
    "invoice_number": "F2026-02-001",
    "invoice_date": str(date.today()),
    "due_date": str(date.today() + timedelta(days=party["payment_terms"])),
    "party": party,
    "lines": lines,
    "is_credit_note": False
}

pdf_buffer = generate_invoice_pdf(invoice, company)
filename = f"{invoice['invoice_number']}.pdf"
with open(filename, "wb") as f:
    f.write(pdf_buffer.read())
```

### 6. Validate generated PDF
After generating, use the Read tool to examine the PDF and verify:
- All required fields are present and readable
- Amounts calculate correctly
- Company and customer info matches request

### 7. Upload document
```bash
curl -X POST -H "X-API-Key: $BOKFORING_API_KEY" \
  -F "file=@{filename}" \
  "https://bokforing.example.com/companies/{company_id}/documents"
# Returns: {"id": 123, "filename": "...", ...}
```

### 8. Book invoice and cleanup
Calculate totals and create invoice with transactions:
```python
# Calculate from lines
net_total = sum(line["quantity"] * line["unit_price"] for line in lines)
vat_by_rate = {}
for line in lines:
    rate = line["vat_rate"]
    amount = line["quantity"] * line["unit_price"]
    vat_by_rate[rate] = vat_by_rate.get(rate, 0) + (amount * rate / 100)
total_vat = sum(vat_by_rate.values())
total_amount = net_total + total_vat
```

```bash
curl -X POST -H "X-API-Key: $BOKFORING_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "party_id": {party_id},
    "type": "customer",
    "invoice_number": "{invoice_number}",
    "invoice_date": "{invoice_date}",
    "due_date": "{due_date}",
    "total_amount": {total_amount},
    "document_ids": [{document_id}],
    "transactions": [
      {"account_number": 1510, "amount": {total_amount}},
      {"account_number": 3010, "amount": -{net_total}},
      {"account_number": 2610, "amount": -{total_vat}}
    ]
  }' \
  "https://bokforing.example.com/companies/{company_id}/invoices"
```

### 9. Delete local PDF after successful upload
```bash
rm {filename}
```
Only delete after confirming the invoice was created successfully (check for invoice id in response).

## Account mapping
| VAT Rate | Revenue Account | VAT Account |
|----------|-----------------|-------------|
| 25% | 3010 | 2610 |
| 12% | 3011 | 2620 |
| 6% | 3012 | 2630 |
| 0% (export) | 3040 | - |

## Error handling
- If company missing payment info: prompt user to update company settings
- If party not found: offer to create new party
- If validation fails: list specific errors before generating
- If upload fails: retry or save PDF locally
