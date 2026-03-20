---
name: process-documents
description: Process unbooked documents (digital shoebox). Analyze receipts, invoices, bank statements, and tax documents, then book appropriately.
---

# Process Unbooked Documents

Review and book documents from the "digital shoebox". Each document type requires different handling.

## Workflow

### 1. List unbooked documents
```bash
# Get all documents, filter for unbooked (empty voucher_ids)
curl -s -H "X-API-Key: ${BOKFORING_API_KEY}" \
  "https://bokforing.example.com/companies/{company_id}/documents?limit=100" \
  | jq '[.items[] | select(.voucher_ids == [])]'
```

### 2. For each unbooked document

**Download and analyze:**
```bash
# Download document to analyze
curl -s -H "X-API-Key: ${BOKFORING_API_KEY}" \
  "https://bokforing.example.com/companies/{company_id}/documents/{document_id}" \
  -o temp_document.pdf
```

Use the Read tool to analyze the document content.

### 3. Classify document type

| Type | Indicators | Action |
|------|------------|--------|
| **Customer invoice** | "Faktura" header, your company as seller | → Invoice flow (F-series) |
| **Supplier invoice** | "Faktura" header, your company as buyer, due date | → Invoice flow (L-series, reskontra) |
| **Receipt/Kvitto** | Small amounts, no due date, paid immediately | → Voucher flow (A-series) |
| **Bank statement** | Multiple transactions, account balance | → Multiple vouchers |
| **Skattekonto** | From Skatteverket, 1630 transactions | → Voucher(s) for tax account |
| **Salary slip** | Lönespec, employee details | → Salary voucher |

### 4. Route to correct flow

#### A) Supplier Invoice (Leverantörsfaktura)
**Must use invoice flow for reskontra tracking.**

1. Find or create party (supplier)
2. Extract: invoice number, date, due date, total amount
3. Create invoice with transactions:
```bash
curl -s -X POST -H "X-API-Key: ${BOKFORING_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "party_id": {party_id},
    "type": "supplier",
    "invoice_number": "{supplier_invoice_nr}",
    "invoice_date": "2026-02-01",
    "due_date": "2026-02-28",
    "total_amount": 1250,
    "document_ids": [{document_id}],
    "transactions": [
      {"account_number": 4010, "amount": 1000},
      {"account_number": 2640, "amount": 250},
      {"account_number": 2440, "amount": -1250}
    ]
  }' \
  "https://bokforing.example.com/companies/{company_id}/invoices"
```

**Supplier invoice accounts:**
- Cost account (4xxx-7xxx): debit net amount
- 2640 Ingående moms: debit VAT
- 2440 Leverantörsskulder: credit total

#### B) Customer Invoice (already sent)
Use `/generate-invoice-pdf` skill if creating new.
If booking existing: use invoice endpoint with type "customer".

#### C) Receipt (Kvitto) - Direct expense
**Use voucher flow - no reskontra needed.**

Follow `/create-voucher` skill workflow.

#### D) Bank Statement
**Creates multiple vouchers - one per transaction.**

1. Parse all transactions from statement
2. Match each against existing unbooked items:
   - Payment of supplier invoice → Record payment (manage-invoices)
   - Payment from customer → Record payment (manage-invoices)
   - Bank fees → Voucher
   - Incoming transfers → Voucher
3. For each unmatched transaction, ask user for classification

**Recording invoice payment:**
```bash
# Supplier invoice payment
curl -s -X POST -H "X-API-Key: ${BOKFORING_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "amount": 1250,
    "payment_date": "2026-02-15",
    "transactions": [
      {"account_number": 2440, "amount": 1250},
      {"account_number": 1930, "amount": -1250}
    ]
  }' \
  "https://bokforing.example.com/companies/{company_id}/invoices/{invoice_id}/payments"
```

#### E) Skattekonto (Tax account)
**Book to 1630 Skattekonto.**

Common transactions:
| Description | Debit | Credit |
|-------------|-------|--------|
| Inbetalning till skattekonto | 1630 | 1930 |
| Arbetsgivaravgifter (debit) | 2731 | 1630 |
| Preliminärskatt anställda | 2710 | 1630 |
| F-skatt egen | 2518 | 1630 |
| Momsredovisning | 2650 | 1630 |
| Ränta skattekonto | 1630 | 8314 |

#### F) Salary Slip (Lönespec)
Complex - typically requires:
- 7010 Löner: gross salary
- 2710 Personalskatt: tax withheld
- 2731 Arbetsgivaravgifter: employer fees
- 2920 Nettolön: net to pay

### 5. Matching payments to invoices

**Check outstanding invoices:**
```bash
# Get unpaid supplier invoices
curl -s -H "X-API-Key: ${BOKFORING_API_KEY}" \
  "https://bokforing.example.com/companies/{company_id}/reports/reskontra?type=supplier" \
  | jq '[.[] | select(.outstanding > 0)]'

# Get unpaid customer invoices
curl -s -H "X-API-Key: ${BOKFORING_API_KEY}" \
  "https://bokforing.example.com/companies/{company_id}/reports/reskontra?type=customer" \
  | jq '[.[] | select(.outstanding > 0)]'
```

**Match by:**
- Amount (exact or partial)
- OCR/reference number
- Party name
- Date proximity to due date

### 6. Summary workflow

```
For each unbooked document:
  1. Download & analyze
  2. Classify type
  3. If invoice (supplier/customer):
       → Extract details
       → Find/create party
       → Book via /invoices endpoint
  4. If receipt/direct expense:
       → Use /create-voucher skill
  5. If bank statement:
       → Parse transactions
       → Match to open invoices → record payments
       → Unmatched → ask user, create vouchers
  6. If tax document:
       → Book to 1630 with appropriate contra
  7. Confirm with user before each booking
```

## Common supplier accounts
| Category | Account | Name |
|----------|---------|------|
| Goods | 4010 | Varuinköp |
| Subcontractors | 4050 | Underleverantörer |
| Office supplies | 6110 | Kontorsmaterial |
| IT/Software | 6540 | IT-tjänster |
| Advertising | 5910 | Annonsering |
| Travel | 5800 | Resekostnader |
| Phone | 6212 | Mobiltelefon |
| Hosting | 6230 | Datakommunikation |

## ⚠️ Inter-account transfers (appears twice!)

Transfers between accounts appear on **both** statements:
- Bank → Skattekonto: shows on bank statement AND skattekonto
- Bank A → Bank B: shows on both bank statements
- Bank → Stripe payout: shows on bank AND Stripe report

**Rule: Book only ONCE** (typically from the source/outgoing side)

**Detection:**
1. When processing bank statement, check if transaction is transfer to 1630/other bank
2. When processing skattekonto, check if "inbetalning" already booked from bank statement
3. Search existing vouchers for same date + amount + contra account

```bash
# Check if transfer already booked
curl -s -H "X-API-Key: ${BOKFORING_API_KEY}" \
  "https://bokforing.example.com/companies/{company_id}/vouchers?series=A&limit=50" \
  | jq '[.items[] | select(.date == "2026-02-01") | select(.transactions[] | .amount == 5000 or .amount == -5000)]'
```

**Common inter-account patterns:**
| Transfer | Book from | Skip on |
|----------|-----------|---------|
| Bank → Skattekonto | Bank statement | Skattekonto statement |
| Bank → Bank | Either (pick one) | The other |
| Stripe → Bank | Stripe report | Bank statement |

**When in doubt:** Ask user "Har denna överföring redan bokförts från det andra kontoutdraget?"

## Error handling
- **Unknown document type:** Ask user for classification
- **Missing party:** Suggest creating new party with details from invoice
- **Amount mismatch:** Show discrepancy, ask user to verify
- **Duplicate invoice number:** Warn and ask for confirmation
- **Inter-account transfer:** Check if already booked, warn before creating duplicate
