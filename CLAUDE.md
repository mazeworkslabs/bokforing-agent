# Bokföringssystem API

> Swedish double-entry bookkeeping. Digital shoebox + ledger. No business logic.

## Setup
1. Copy `.claude/settings.local.json.example` → `.claude/settings.local.json`
2. Set `BOKFORING_API_KEY` to your instance's API key
3. Replace the placeholder base URL `bokforing.example.com` with your instance's host
   (in this file and the skill files under `.claude/skills/`)

## API
Base URL: https://bokforing.example.com   # replace with your instance
Auth: X-API-Key header

```
X-API-Key: ${BOKFORING_API_KEY}
```
## Example first request
curl -s -H "X-API-Key: ${BOKFORING_API_KEY}" "https://bokforing.example.com/users/me/companies"

## Rules
- Voucher MUST have document_ids (upload first)
- Transactions MUST sum to 0 (debit +, credit -)
- Use accounts from /companies/{id}/accounts
- Voucher date within unlocked fiscal year
- Do NOT upload documents without immediately linking them to a voucher. Upload + create voucher in the same flow. Use POST /vouchers/{id}/documents/{id} to link if needed.
- Betalningar (payments) får ENDAST registreras om du kan länka dem till ett kontoutdrag (bank/Stripe transaktionslista) som täcker betalningsdatumet. Saknas kontoutdrag — be användaren ladda upp ett färskt innan du bokför betalningen.

## Voucher Series
- **A** = Manual (POST /vouchers)
- **F** = Customer invoice (POST /invoices)
- **L** = Supplier invoice (POST /invoices)

## Endpoints (under /companies/{id})

**Core:**
GET/POST /accounts, /vouchers, /documents, /years, /projects, /parties

**Invoices:**
POST /invoices - Create with total_amount + transactions + document_ids
POST /invoices/{id}/payments - Record payment
POST /invoices/{id}/void - Void invoice
GET /reports/reskontra?type=customer|supplier

**Reports:**
GET /reports/ledger?account_number=N
GET /reports/balance, /reports/profit-loss
GET /reports/account-totals?group_by=account|vat_code

## Create Voucher
```json
POST /companies/1/documents  // Upload first
POST /companies/1/vouchers
{
  "date": "2026-01-15",
  "description": "Office supplies",
  "document_ids": [1],
  "transactions": [
    {"account_number": 6110, "amount": 500},
    {"account_number": 1930, "amount": -500}
  ]
}
```

## Create Invoice
Agent generates PDF → uploads → books with total_amount
```json
POST /companies/1/invoices
{
  "party_id": 1,
  "type": "customer",
  "invoice_number": "202612003",
  "invoice_date": "2026-01-15",
  "due_date": "2026-02-14",
  "total_amount": 6250,
  "document_ids": [101],
  "transactions": [
    {"account_number": 1510, "amount": 6250},
    {"account_number": 3001, "amount": -5000},
    {"account_number": 2610, "amount": -1250}
  ]
}
```

## Record Payment
```json
POST /companies/1/invoices/1/payments
{
  "amount": 6250,
  "payment_date": "2026-02-10",
  "transactions": [
    {"account_number": 1930, "amount": 6250},
    {"account_number": 1510, "amount": -6250}
  ]
}
```

## Temp files
Use `tmp/` for drafts, kladdar, generated PDFs, and other temporary files. The directory is gitignored.

## Python
PDF generation (`invoice_pdf.py`) needs `reportlab`: `pip install reportlab`.
Use whichever interpreter has it installed — `python` or `python3` depending on your system.

## API Key Gotcha
Use `--header "X-API-Key: $BOKFORING_API_KEY"` (not `-H "X-API-Key: ${BOKFORING_API_KEY}"`). Variable expansion is inconsistent with `${}`  syntax.

## IMPORTANT! Context
Always be aware of the current context you are working in
- /users/me/companies - gets current companies
- /companies/{id}/context - JSON with accounts, years, instructions
- /knowledge/{topic} - Swedish bookkeeping guidance (moms, lon, bokslut, etc.) use /knowledge to get a list of available topics