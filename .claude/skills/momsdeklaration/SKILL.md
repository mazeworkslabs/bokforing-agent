---
name: momsdeklaration
description: Prepare and generate Swedish VAT declaration (momsdeklaration). Calculates amounts for all boxes, validates against bookkeeping, and generates XML for Skatteverket.
---

# Momsdeklaration

Prepare Swedish VAT declarations with automatic calculation from bookkeeping data.

## Workflow

### 1. Get context and determine period
```bash
# Get company context
curl -s -H "X-API-Key: ${BOKFORING_API_KEY}" \
  "https://bokforing.example.com/companies/{company_id}/context" | jq '.'
```

**Determine reporting period based on turnover:**
| Omsattning | Period | Deadline |
|------------|--------|----------|
| < 1 MSEK | Arsvis | 26 feb foljande ar |
| 1-40 MSEK | Kvartalsvis | 12:e i 2:a manaden efter kvartal |
| > 40 MSEK | Manadsvis | 26:e i foljande manad |

**Quarterly deadlines:**
- Q1 (jan-mar): 12 maj
- Q2 (apr-jun): 17 aug
- Q3 (jul-sep): 12 nov
- Q4 (okt-dec): 12 feb (foljande ar)

### 2. Get VAT account totals for period
```bash
# Get account totals grouped by VAT-relevant accounts
curl -s -H "X-API-Key: ${BOKFORING_API_KEY}" \
  "https://bokforing.example.com/companies/{company_id}/reports/account-totals?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD" | jq '.'
```

### 3. Calculate VAT declaration boxes

**Section A: Momspliktig forsaljning (excl. moms)**
| Ruta | Kalla | Beskrivning |
|------|-------|-------------|
| 05 | 3000-serien | Momspliktig forsaljning inom Sverige |
| 06 | - | Momspliktiga uttag |
| 07 | - | Vinstmarginalbeskattning |
| 08 | - | Hyresinkomster (frivillig moms) |

**Section B: Utgaende moms pa forsaljning**
| Ruta | Konto | Beskrivning |
|------|-------|-------------|
| 10 | 2610, 2611 | Utgaende moms 25% |
| 11 | 2620, 2621 | Utgaende moms 12% |
| 12 | 2630, 2631 | Utgaende moms 6% |

**Section C: Inkop med omvand skattskyldighet (underlag)**
| Ruta | Konto | Beskrivning |
|------|-------|-------------|
| 20 | 4515 | Inkop varor fran annat EU-land |
| 21 | 4516 | Inkop tjanster fran annat EU-land |
| 22 | 4531, 4535 | Inkop tjanster utanfor EU |
| 23 | - | Varuinkop i Sverige (omvand skattsk.) |
| 24 | - | Ovriga inkop (byggmoms mm) |

**Section D: Utgaende moms pa inkop (omvand skattskyldighet)**
| Ruta | Konto | Beskrivning |
|------|-------|-------------|
| 30 | 2614 | Utgaende moms 25% (pa inkop ruta 20-24) |
| 31 | - | Utgaende moms 12% |
| 32 | - | Utgaende moms 6% |

**Section E: Momsfri forsaljning**
| Ruta | Beskrivning |
|------|-------------|
| 35 | Varuforsaljning till annat EU-land |
| 36 | Varuforsaljning utanfor EU (export) |
| 38 | Tjanster till annat EU-land (huvudregeln) |
| 39 | Ovrig momsfri omsattning |
| 40 | Tjanster utanfor EU |
| 41 | Forsaljning dar koparen ar skattskyldig i Sverige |

**Section F: Ingaende moms**
| Ruta | Konto | Beskrivning |
|------|-------|-------------|
| 48 | 2640, 2641, 2645, 2647 | Ingaende moms att dra av |

**Berakning ruta 49:**
```
Ruta 49 = (10 + 11 + 12 + 30 + 31 + 32) - 48
```
Positivt = moms att betala, Negativt = moms att fa tillbaka.

### 4. Validate calculations

**Kontrollberakningar:**
```
1. Ruta 05 x 0.25 bor = Ruta 10 (+-avrundning)
2. Ruta 20 x 0.25 bor = Ruta 30
3. Ruta 21 x 0.25 bor = del av Ruta 30
4. Ruta 22 x 0.25 bor = del av Ruta 30
```

**Visa sammanstallning:**
```
=== MOMSDEKLARATION Q4 2025 ===
Period: 2025-10-01 - 2025-12-31
Foretag: Exempel AB (556000-0000)

FORSALJNING
  05 Momspliktig forsaljning:      100 000 kr
  10 Utgaende moms 25%:             25 000 kr

INKOP EU/UTLAND
  21 Tjanster fran EU:               5 000 kr
  22 Tjanster utanfor EU:            2 000 kr
  30 Utg. moms pa inkop 25%:         1 750 kr

AVDRAG
  48 Ingaende moms:                 15 000 kr

RESULTAT
  49 Moms att betala:               11 750 kr

=================================
```

### 5. Ask for confirmation
Show complete summary and ask user to verify before generating XML.

### 6. Generate XML for Skatteverket

**IMPORTANT:** No XML declaration, no DOCTYPE, no Kontaktperson. Skatteverket rejects files with these.

```xml
<eSKDUpload Version="6.0">
<OrgNr>556000-0000</OrgNr>
<Moms>
<Period>202512</Period>
<ForsMomsEjAnnan>100000</ForsMomsEjAnnan>
<MomsUtgHog>25000</MomsUtgHog>
<InkopTjanstAnnatEg>5000</InkopTjanstAnnatEg>
<InkopTjanstUtomEg>2000</InkopTjanstUtomEg>
<MomsInkopUtgHog>1750</MomsInkopUtgHog>
<MomsIngAvdr>15000</MomsIngAvdr>
<MomsBetala>11750</MomsBetala>
</Moms>
</eSKDUpload>
```

**XML-element mapping:**
| Ruta | XML-element |
|------|-------------|
| 05 | ForsMomsEjAnnan |
| 06 | UttagMoms |
| 07 | UlagMargbesk |
| 08 | HyrinkomstFriv |
| 10 | MomsUtgHog |
| 11 | MomsUtgMedel |
| 12 | MomsUtgLag |
| 20 | InkopVaruAnnatEg |
| 21 | InkopTjanstAnnatEg |
| 22 | InkopTjanstUtomEg |
| 23 | InkopVaruSverige |
| 24 | InkopTjanstSverige |
| 30 | MomsInkopUtgHog |
| 31 | MomsInkopUtgMedel |
| 32 | MomsInkopUtgLag |
| 35 | ForsVaruAnnatEg |
| 36 | ForsVaruUtomEg |
| 39 | ForsTjSkskAnnatEg |
| 40 | ForsTjOvrUtomEg |
| 41 | ForsKopareSkskSverige |
| 42 | ForsOvrigt |
| 48 | MomsIngAvdr |
| 49 | MomsBetala |

### 7. Book VAT settlement (optional)
After declaration is filed, book the VAT settlement:

```bash
# Close VAT accounts to settlement account
curl -s -X POST -H "X-API-Key: ${BOKFORING_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "date": "2025-12-31",
    "description": "Momsredovisning Q4 2025",
    "document_ids": [{doc_id}],
    "transactions": [
      {"account_number": 2610, "amount": 25000},
      {"account_number": 2614, "amount": 1750},
      {"account_number": 2641, "amount": -15000},
      {"account_number": 2645, "amount": -1750},
      {"account_number": 2650, "amount": -10000}
    ]
  }' \
  "https://bokforing.example.com/companies/{company_id}/vouchers"
```

## Key accounts

| Konto | Namn | Roll |
|-------|------|------|
| 2610 | Utgaende moms 25% | Ruta 10 |
| 2611 | Utgaende moms forsaljning 25% | Ruta 10 |
| 2614 | Utgaende moms utland 25% | Ruta 30 (omvand skattsk.) |
| 2620 | Utgaende moms 12% | Ruta 11 |
| 2630 | Utgaende moms 6% | Ruta 12 |
| 2640 | Ingaende moms | Ruta 48 |
| 2641 | Debiterad ingaende moms | Ruta 48 |
| 2645 | Beraknad ingaende moms utland | Ruta 48 |
| 2650 | Redovisningskonto moms | Skuld till Skatteverket |

## Common issues

- **Avrundningsdifferens:** Accepteras upp till 1 kr per rad.
- **Omvand skattskyldighet:** Kontrollera att 2614 och 2645 ar lika.
- **EU-inkop:** Kontrollera att ruta 21/22 stammer med 4515/4531/4535.
- **Saknade konton:** Om momskonto saknas, undersok om transaktioner bokforts pa fel konto.

## Notes

- Belopp avrundas till hela kronor i XML
- Period anges som YYYYMM med sista manaden i kvartalet (t.ex. 202512 for Q4 2025, 202603 for Q1 2026)
- Ingen XML-deklaration, DOCTYPE eller Kontaktperson — Skatteverket avvisar dessa
- Negativa belopp (aterbetalning): Anvand minustecken direkt (t.ex. -5000)
