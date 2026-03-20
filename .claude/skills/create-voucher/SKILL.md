---
name: create-voucher
description: Create a manual voucher (verifikation) with duplicate detection and validation. Use for booking expenses, bank transactions, or corrections.
---

# Create Voucher

Create manual vouchers (A-series) with safety checks. **Vouchers cannot be deleted** - only corrected via reversal entries - so validation is critical.

## Workflow

### 1. Get context and validate date
```bash
# Get company context (accounts, fiscal years)
curl -s -H "X-API-Key: ${BOKFORING_API_KEY}" \
  "https://bokforing.example.com/companies/{company_id}/context" | jq '.'

# Check fiscal years - date must be in unlocked year
curl -s -H "X-API-Key: ${BOKFORING_API_KEY}" \
  "https://bokforing.example.com/companies/{company_id}/years" | jq '.'
```

### 2. Upload document FIRST
**Every voucher MUST have a document.** Upload before creating voucher.
```bash
curl -s -X POST -H "X-API-Key: ${BOKFORING_API_KEY}" \
  -F "file=@{filename}" \
  "https://bokforing.example.com/companies/{company_id}/documents"
# Returns: {"id": 123, ...}
```

### 3. Check for potential duplicates
**CRITICAL:** Before creating, search for similar vouchers to prevent duplicates.

```bash
# Get recent vouchers (last 30 days around target date)
curl -s -H "X-API-Key: ${BOKFORING_API_KEY}" \
  "https://bokforing.example.com/companies/{company_id}/vouchers?series=A&limit=50" | jq '.'
```

**Duplicate detection rules:**
- Same date + total amount within ±5% → **WARNING: Potential duplicate**
- Same date + identical accounts used → **WARNING: Similar booking exists**
- Same description (fuzzy match) → **WARNING: Check if already booked**

If potential duplicate found:
1. Show the existing voucher(s) to user
2. Ask for explicit confirmation to proceed
3. Only create if user confirms it's not a duplicate

### 4. Validate before creating

**Pre-flight checks:**
```
[ ] Document uploaded (document_ids not empty)
[ ] Transactions sum to 0 (debit = credit)
[ ] All account numbers exist in company's chart of accounts
[ ] Date is within an unlocked fiscal year
[ ] Description is not empty
[ ] No potential duplicates (or user confirmed)
```

**Show validation summary:**
```
=== VOUCHER PREVIEW ===
Date: 2026-02-04
Description: Office supplies - Dustin

Transactions:
  6110 Kontorsmaterial     +500.00
  2640 Ingående moms       +125.00
  1930 Företagskonto       -625.00
  ─────────────────────────────────
  Balance:                    0.00 ✓

Document: receipt-dustin.pdf (id: 123)

⚠️  No duplicates found.
```

### 5. Ask for confirmation
**Always ask user to confirm before creating:**
- Show the complete voucher preview
- Highlight any warnings (duplicates, unusual amounts)
- Wait for explicit "yes" / "ja" / "confirm"

### 6. Create voucher
```bash
curl -s -X POST -H "X-API-Key: ${BOKFORING_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "date": "2026-02-04",
    "description": "Office supplies - Dustin",
    "document_ids": [123],
    "transactions": [
      {"account_number": 6110, "amount": 500},
      {"account_number": 2640, "amount": 125},
      {"account_number": 1930, "amount": -625}
    ]
  }' \
  "https://bokforing.example.com/companies/{company_id}/vouchers"
```

### 7. Confirm success
Show the created voucher number and summary.

## Common account patterns

| Type | Debit | Credit |
|------|-------|--------|
| Expense paid by bank | Cost account, 2640 (VAT) | 1930 (Bank) |
| Expense paid privately | Cost account, 2640 (VAT) | 2893 (Personal debt) |
| Bank fee | 6570 | 1930 |
| Interest income | 1930 | 8410 |
| Transfer between accounts | Target account | Source account |

## VAT accounts
| Rate | Outgoing (sales) | Incoming (purchases) |
|------|------------------|----------------------|
| 25% | 2610 | 2640 |
| 12% | 2620 | 2645 |
| 6% | 2630 | 2646 |
| Reverse charge | 2614 | 2645 |

## Adding missing accounts

If a needed account doesn't exist, suggest creating it:

```bash
curl -s -X POST -H "X-API-Key: ${BOKFORING_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"number": 5930, "name": "Reklamtrycksaker", "type": "EXPENSE"}' \
  "https://bokforing.example.com/companies/{company_id}/accounts"
```

**Account types by number range:**
| Range | Type | Description |
|-------|------|-------------|
| 1000-1999 | ASSET | Tillgångar |
| 2000-2999 | LIABILITY | Skulder |
| 3000-3999 | REVENUE | Intäkter |
| 4000-7999 | EXPENSE | Kostnader |
| 8000-8999 | REVENUE/EXPENSE | Finansiella poster |

**Common accounts to suggest:**
- 5930 Reklamtrycksaker (EXPENSE)
- 5910 Annonsering (EXPENSE)
- 6212 Mobiltelefon (EXPENSE)
- 6230 Datakommunikation (EXPENSE)
- 6530 Redovisningstjänster (EXPENSE)
- 6540 IT-tjänster (EXPENSE)

## Error handling
- **Missing document:** Refuse to create. Ask user to upload first.
- **Unbalanced:** Show the imbalance amount. Ask user to correct.
- **Invalid account:** List similar accounts or suggest creating new one.
- **Locked year:** Inform user and suggest correct date range.
- **Duplicate found:** Show existing voucher, require explicit confirmation.
