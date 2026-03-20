---
name: manage-invoices
description: Manage customer and supplier invoices - view reskontra, record payments, void invoices. Use for AR/AP management.
---

# Invoice Management (Reskontra)

Manage accounts receivable (customer invoices) and accounts payable (supplier invoices).

## Quick commands

| Action | Description |
|--------|-------------|
| "visa reskontra" | Show outstanding invoices |
| "registrera betalning" | Record payment against invoice |
| "makulera faktura" | Void an invoice |
| "förfallna fakturor" | Show overdue invoices |

## 1. View Reskontra (Outstanding Invoices)

### Customer invoices (Kundfordringar)
```bash
curl -s -H "X-API-Key: ${BOKFORING_API_KEY}" \
  "https://bokforing.example.com/companies/{company_id}/reports/reskontra?type=customer" | jq '.'
```

### Supplier invoices (Leverantörsskulder)
```bash
curl -s -H "X-API-Key: ${BOKFORING_API_KEY}" \
  "https://bokforing.example.com/companies/{company_id}/reports/reskontra?type=supplier" | jq '.'
```

### Filter unpaid only
```bash
curl -s -H "X-API-Key: ${BOKFORING_API_KEY}" \
  "https://bokforing.example.com/companies/{company_id}/reports/reskontra?type=customer" \
  | jq '[.items[] | select(.outstanding != "0.00")]'
```

### Filter overdue
```bash
curl -s -H "X-API-Key: ${BOKFORING_API_KEY}" \
  "https://bokforing.example.com/companies/{company_id}/reports/reskontra?type=customer" \
  | jq '[.items[] | select(.days_overdue > 0)]'
```

**Response includes:**
- `items[]` - Each invoice with: invoice_id, invoice_number, party_name, due_date, total, paid, outstanding, days_overdue
- `aging[]` - Buckets: Current, 1-30 days, 31-60 days, 61-90 days, >90 days
- `total_outstanding` - Sum of all unpaid

## 2. Record Payment (Registrera betalning)

### Customer payment (inbetalning)
Customer pays their invoice → money to bank, reduce receivable.
```bash
curl -s -X POST -H "X-API-Key: ${BOKFORING_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "amount": 12500,
    "payment_date": "2026-02-04",
    "transactions": [
      {"account_number": 1930, "amount": 12500},
      {"account_number": 1510, "amount": -12500}
    ]
  }' \
  "https://bokforing.example.com/companies/{company_id}/invoices/{invoice_id}/payments"
```

### Supplier payment (utbetalning)
Pay supplier invoice → reduce debt, money from bank.
```bash
curl -s -X POST -H "X-API-Key: ${BOKFORING_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "amount": 6250,
    "payment_date": "2026-02-04",
    "transactions": [
      {"account_number": 2440, "amount": 6250},
      {"account_number": 1930, "amount": -6250}
    ]
  }' \
  "https://bokforing.example.com/companies/{company_id}/invoices/{invoice_id}/payments"
```

### Partial payment
Same structure, just use the partial amount. System tracks remaining balance.

### Payment accounts
| Type | Debit | Credit |
|------|-------|--------|
| Customer pays (bank) | 1930 Bank | 1510 Kundfordringar |
| Customer pays (Stripe) | 1580 Stripe | 1510 Kundfordringar |
| Pay supplier (bank) | 2440 Leverantörsskulder | 1930 Bank |

## 3. Void Invoice (Makulera)

**Warning:** This creates a reversal voucher. Use only for incorrect invoices.

```bash
curl -s -X POST -H "X-API-Key: ${BOKFORING_API_KEY}" \
  "https://bokforing.example.com/companies/{company_id}/invoices/{invoice_id}/void"
```

**When to void:**
- Invoice sent to wrong customer
- Incorrect amounts that can't be corrected with credit note
- Duplicate invoice created by mistake

**When NOT to void (use credit note instead):**
- Customer returns goods
- Price adjustment after delivery
- Discount given after invoicing

## 4. Get Invoice Details

```bash
curl -s -H "X-API-Key: ${BOKFORING_API_KEY}" \
  "https://bokforing.example.com/companies/{company_id}/invoices/{invoice_id}" | jq '.'
```

## 5. List All Invoices

```bash
# Customer invoices
curl -s -H "X-API-Key: ${BOKFORING_API_KEY}" \
  "https://bokforing.example.com/companies/{company_id}/invoices?type=customer&limit=20" | jq '.items'

# Supplier invoices
curl -s -H "X-API-Key: ${BOKFORING_API_KEY}" \
  "https://bokforing.example.com/companies/{company_id}/invoices?type=supplier&limit=20" | jq '.items'
```

## 6. Find Invoice by Number

```bash
curl -s -H "X-API-Key: ${BOKFORING_API_KEY}" \
  "https://bokforing.example.com/companies/{company_id}/invoices?type=customer&limit=100" \
  | jq '.items[] | select(.invoice_number == "F2026-02-001")'
```

## Common workflows

### "Kunden har betalat faktura X"
1. Find invoice: search by number or list reskontra
2. Verify amount and customer
3. Record payment with date from bank statement
4. Confirm payment registered

### "Betala leverantörsfaktura X"
1. Find supplier invoice in reskontra
2. Verify amount and due date
3. Record payment (usually same day as bank transaction)
4. Confirm debt reduced

### "Visa förfallna kundfakturor"
1. Get customer reskontra
2. Filter where days_overdue > 0
3. Show summary with aging buckets

### "Makulera felaktig faktura"
1. Find invoice by number
2. Verify it should be voided (not credit note case)
3. Confirm with user - this is irreversible
4. Void invoice
5. Confirm reversal voucher created

## Reskontra accounts
| Type | Account | Name |
|------|---------|------|
| Customer receivables | 1510 | Kundfordringar |
| Supplier payables | 2440 | Leverantörsskulder |
| Bank | 1930 | Företagskonto |
| Stripe | 1580 | Kortinlösen (Stripe) |

## Error handling
- **Invoice not found:** List recent invoices, help user identify correct one
- **Already paid:** Show payment history, warn if overpayment
- **Already voided:** Inform user, no action needed
- **Partial payment remaining:** Show outstanding balance after payment
