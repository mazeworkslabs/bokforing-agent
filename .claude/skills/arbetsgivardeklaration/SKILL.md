---
name: arbetsgivardeklaration
description: Prepare and generate Swedish employer declaration (arbetsgivardeklaration/AGI). Collects salary data from bookkeeping, generates XML for Skatteverket, uploads and books.
---

# Arbetsgivardeklaration (AGI)

Generate monthly employer declarations with XML for Skatteverket upload.

## Workflow

### 1. Get context and salary data
```bash
# Get company context (org number, accounts, recent vouchers)
curl -s -H "X-API-Key: $BOKFORING_API_KEY" \
  "https://bokforing.example.com/companies/{company_id}/context"
```

Determine the reporting period (previous month). Find salary vouchers for that period by searching for "Lön" in the voucher list.

### 2. Extract salary data from vouchers

For each salary voucher, extract:
| Field | Account | Description |
|-------|---------|-------------|
| Bruttolön | 7000/7010/7210 | Gross salary (debit) |
| Arbetsgivaravgifter | 7510/7511 | Employer contributions (debit) |
| Källskatt | 2710 | Withheld tax (credit, negate) |
| Nettolön | 1930 | Net pay (credit) |

### 3. Ask user for employee personnummer

BetalningsmottagarId requires 12-digit format with century: `19YYMMDDNNNN` or `20YYMMDDNNNN`.

### Technical contact (default for all companies)

Use these values for `TekniskKontaktperson` and `Kontaktperson` unless user overrides:
- Namn: Förnamn Efternamn
- Telefon: 070XXXXXXX
- Epostadress: namn@example.com

### 4. Generate XML

**CRITICAL: ID formats**
- Organisationsnummer: 12 digits, no hyphen. Prefix org number with `16`: `556000-0000` → `165560000000`
- Arendeagare: Same 12-digit format
- BetalningsmottagarId: 12-digit personnummer with century digits

**CRITICAL: XML structure**
- All fields in HU/IU require `faltkod` attribute
- AgRegistreradId goes inside GROUP wrapper elements
- BetalningsmottagarId goes inside `BetalningsmottagareIDChoice` inside `BetalningsmottagareIUGROUP`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<Skatteverket xmlns="http://xmls.skatteverket.se/se/skatteverket/da/instans/schema/1.1"
              xmlns:agd="http://xmls.skatteverket.se/se/skatteverket/da/komponent/schema/1.1"
              omrade="Arbetsgivardeklaration">

  <agd:Avsandare>
    <agd:Programnamn>BokforingAgent</agd:Programnamn>
    <agd:Organisationsnummer>{org_12digit}</agd:Organisationsnummer>
    <agd:TekniskKontaktperson>
      <agd:Namn>{contact_name}</agd:Namn>
      <agd:Telefon>{contact_phone}</agd:Telefon>
      <agd:Epostadress>{contact_email}</agd:Epostadress>
    </agd:TekniskKontaktperson>
    <agd:Skapad>{ISO_timestamp}</agd:Skapad>
  </agd:Avsandare>

  <agd:Blankettgemensamt>
    <agd:Arbetsgivare>
      <agd:AgRegistreradId>{org_12digit}</agd:AgRegistreradId>
      <agd:Kontaktperson>
        <agd:Namn>{contact_name}</agd:Namn>
        <agd:Telefon>{contact_phone}</agd:Telefon>
        <agd:Epostadress>{contact_email}</agd:Epostadress>
      </agd:Kontaktperson>
    </agd:Arbetsgivare>
  </agd:Blankettgemensamt>

  <!-- HU: Employer summary -->
  <agd:Blankett>
    <agd:Arendeinformation>
      <agd:Arendeagare>{org_12digit}</agd:Arendeagare>
      <agd:Period>{YYYYMM}</agd:Period>
    </agd:Arendeinformation>
    <agd:Blankettinnehall>
      <agd:HU>
        <agd:ArbetsgivareHUGROUP>
          <agd:AgRegistreradId faltkod="201">{org_12digit}</agd:AgRegistreradId>
        </agd:ArbetsgivareHUGROUP>
        <agd:RedovisningsPeriod faltkod="006">{YYYYMM}</agd:RedovisningsPeriod>
        <agd:SummaArbAvgSlf faltkod="487">{total_employer_contributions}</agd:SummaArbAvgSlf>
        <agd:SummaSkatteavdr faltkod="497">{total_tax_withheld}</agd:SummaSkatteavdr>
      </agd:HU>
    </agd:Blankettinnehall>
  </agd:Blankett>

  <!-- IU: One per employee -->
  <agd:Blankett>
    <agd:Arendeinformation>
      <agd:Arendeagare>{org_12digit}</agd:Arendeagare>
      <agd:Period>{YYYYMM}</agd:Period>
    </agd:Arendeinformation>
    <agd:Blankettinnehall>
      <agd:IU>
        <agd:ArbetsgivareIUGROUP>
          <agd:AgRegistreradId faltkod="201">{org_12digit}</agd:AgRegistreradId>
        </agd:ArbetsgivareIUGROUP>
        <agd:BetalningsmottagareIUGROUP>
          <agd:BetalningsmottagareIDChoice>
            <agd:BetalningsmottagarId faltkod="215">{personnummer_12}</agd:BetalningsmottagarId>
          </agd:BetalningsmottagareIDChoice>
        </agd:BetalningsmottagareIUGROUP>
        <agd:AvdrPrelSkatt faltkod="001">{tax_withheld}</agd:AvdrPrelSkatt>
        <agd:KontantErsattningUlagAG faltkod="011">{gross_salary}</agd:KontantErsattningUlagAG>
        <agd:RedovisningsPeriod faltkod="006">{YYYYMM}</agd:RedovisningsPeriod>
        <agd:Specifikationsnummer faltkod="570">{spec_nr}</agd:Specifikationsnummer>
      </agd:IU>
    </agd:Blankettinnehall>
  </agd:Blankett>

</Skatteverket>
```

### 5. Show summary and confirm

```
=== ARBETSGIVARDEKLARATION {YYYYMM} ===
Foretag: {company_name} ({org_number})

ANSTALLDA
  {name}: Bruttolön {gross} kr, Skatt {tax} kr

SUMMERING
  FK487 Arbetsgivaravgifter:  {contributions} kr
  FK497 Skatteavdrag:         {tax_withheld} kr
  Att betala:                 {total} kr

========================================
```

### 6. Upload XML and book voucher

Upload XML and create voucher in one flow (never leave documents unlinked):

```bash
# Upload
curl -s -H "X-API-Key: $BOKFORING_API_KEY" \
  -F "file=@AGI_{YYYY}_{MM}.xml" \
  "https://bokforing.example.com/companies/{company_id}/documents"

# Book: clear salary liabilities against skattekonto
curl -s -X POST -H "X-API-Key: $BOKFORING_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "date": "{YYYY-MM-12}",
    "description": "Arbetsgivardeklaration {month_name} {year}",
    "document_ids": [{doc_id}],
    "transactions": [
      {"account_number": 2710, "amount": {tax_withheld}},
      {"account_number": 2731, "amount": {contributions}},
      {"account_number": 1630, "amount": -{total}}
    ]
  }' \
  "https://bokforing.example.com/companies/{company_id}/vouchers"
```

Voucher date = 12th of following month (when Skatteverket debits skattekonto).

## Faltkod reference

| Faltkod | Element | Description |
|---------|---------|-------------|
| 001 | AvdrPrelSkatt | Preliminary tax deducted |
| 006 | RedovisningsPeriod | Reporting period YYYYMM |
| 011 | KontantErsattningUlagAG | Cash salary (employer contrib basis) |
| 012 | SkatteplFormanerUlagAG | Taxable benefits |
| 013 | SkatteplBilformanUlagAG | Car benefit |
| 131 | KontantErsattningEjUlagSA | Cash not subject to social contrib |
| 201 | AgRegistreradId | Employer registration ID |
| 215 | BetalningsmottagarId | Employee personnummer |
| 274 | AvdrSkattSINK | SINK tax |
| 487 | SummaArbAvgSlf | Total employer contributions |
| 497 | SummaSkatteavdr | Total tax deductions |
| 570 | Specifikationsnummer | Sequence number per employee |

## Employer contribution rates

| Category | Rate |
|----------|------|
| Full (born 1959+) | 31.42% |
| Reduced (born 1938-1958) | 10.21% |
| None (born ≤1937) | 0% |

## Deadlines 2026

| Salary month | Deadline |
|--------------|----------|
| January | Feb 12 |
| February | Mar 12 |
| March | Apr 13 |
| April | May 13 |
| May | Jun 12 |
| June | Jul 13 |
| July | Aug 17 |
| August | Sep 14 |
| September | Oct 12 |
| October | Nov 12 |
| November | Dec 14 |

Late fee: 625 kr.

## Key accounts

| Konto | Namn | Roll |
|-------|------|------|
| 2710 | Personalens källskatt | Liability cleared on AGI date |
| 2731 | Avräkning sociala avgifter | Liability cleared on AGI date |
| 1630 | Avräkning skatter och avgifter | Skattekonto debit |
| 7000/7210 | Löner | Salary expense |
| 7510/7511 | Arbetsgivaravgifter | Employer contribution expense |
