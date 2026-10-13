# Jordan — LawCodex (التشريعات الأردنية)

Jordanian legislation as Markdown, in Arabic. The texts come from the official database of the
**Legislation and Opinion Bureau** (ديوان التشريع والرأي, https://www.lob.gov.jo), part of the
Prime Ministry. Part of [LawCodex](https://github.com/LawCodex): one repository per jurisdiction.

- Retrieved: **2026-10-13**
- Version: **consolidated**. The Bureau's search returns each legislation in its final form
  (التشريع بصورته النهائية), with all amendments merged in. The original "as released"
  versions are separate records in the Bureau's database and are not included. For example,
  the 1952 Constitution here includes the 2022 amendments.

## Coverage

All five legislation types that the Bureau's search exposes are included, with both in-force
and repealed records:

| Directory | Type (نوع التشريع) | Files | `in_force` (ساري) | `repealed` (غير ساري) |
| --- | --- | ---: | ---: | ---: |
| `ar/constitution/` | دستور — the Constitution of 1952 (in force), the 1947 Constitution and the 1928 Organic Law of Transjordan | 3 | 1 | 2 |
| `ar/laws/<year>/` | قانون — laws, including provisional laws (قوانين مؤقتة) and ratification laws | 1,718 | 667 | 1,051 |
| `ar/bylaws/<year>/` | نظام — bylaws (regulations issued by the Council of Ministers) | 4,029 | 1,902 | 2,127 |
| `ar/instructions/<year>/` | تعليمات — instructions | 596 | 572 | 24 |
| `ar/agreements/<year>/` | اتفاقية — agreements (concessions, production-sharing and other agreements ratified by law) | 289 | 288 | 1 |
| **Total** | | **6,635** | **3,430** | **3,205** |

The texts run from the Ottoman period (مجلة الأحكام العدلية and قانون الأراضي العثماني, which the
Bureau dates to the year 1900) to 2026. 110 records have no article text in the Bureau's
database, mostly agreements (100). For those the file holds the metadata and a note
(«لا يتضمن المصدر نص مواد لهذا التشريع»).

### Not covered

- **Judicial decisions and interpretations** (الأحكام القضائية, التفاسير — types 6 and 7 in the
  Bureau's database): these are case law, not legislation.
- **Defence orders and communiqués** (أوامر الدفاع والبلاغات, 2020–2023), which the Bureau
  publishes in a separate section of its site.
- **Draft laws** (مسودات مشروعات القوانين).
- **English.** The Bureau publishes legislation in Arabic only. There are no official English
  texts.

## Structure

```
ar/constitution/<year>-constitution-<id>.md        e.g. ar/constitution/1952-constitution-36.md
ar/<type>/<year>/<year>-<number>-<id>.md           e.g. ar/laws/1960/1960-016-3435.md  قانون العقوبات رقم 16 لسنة 1960
```

- `<number>` is the official number (رقم), zero-padded. `000` means the record has no number.
- `<id>` is the Bureau's database id (`LegislationID`). It keeps file names unique: a law
  number can be used twice in a year, for example a provisional law and the permanent law
  that replaced it.
- The front matter has:
  - `title`, `identifier` (`lob.gov.jo:<type>:<id>`), `number`, `year`, `type`, `type_ar`;
  - `date` (Official Gazette publication date), `in_force_from` where given, `gazette_number`
    and `gazette_page`;
  - `amended_by`, the list of amending legislation the Bureau records, and `last_amended`,
    the year of the latest of them;
  - `status` and `status_ar`, the Bureau's own ساري / غير ساري flag;
  - `source` (link to the record on lob.gov.jo) and `retrieved`.
- The body has one `##### المادة N` heading per article, using the Bureau's article numbering.
  Where an article's text begins with a division heading (الكتاب/الباب → `##`, الفصل → `###`,
  القسم/الفرع → `####`), as in the Constitution, the heading is kept and the article label is
  taken from the text, for example «المادة (1) مكرره». Tables are Markdown tables. Nothing is
  translated or summarised.

## How it was fetched

lob.gov.jo is a single-page web application. Its browser code calls a JSON service
(`/OPSHandler/OPS.ashx`) that wraps requests and responses with RSA/AES. The server sends the
session keys in its own response headers. `scripts/jo_client.py` follows the same protocol as
the site's public JavaScript (`Controller/Master.js`). It identifies itself as
`LawCodex/1.0 (+https://github.com/LawCodex)`, makes at most 4 concurrent requests with 1 s
between calls per worker, and solves no CAPTCHA or bot challenge. The site has no robots.txt
(HTTP 404) and no published terms of use restricting reuse.

Calls used: `GetSearchFormData`, `GetLegislationSearch` (listing, 10 records per page),
`GetLegislationDetails` (text and metadata) and `GetlegislationModified` (amendment list).

## Licence / copyright

These are official texts of the Hashemite Kingdom of Jordan, published by a government body
for public information. Official legislative texts are generally not subject to copyright,
and they are reproduced unchanged.

## Regenerate

```sh
pip install -r scripts/requirements.txt
python3 scripts/jo_fetch.py   ../_raw/jo --workers 4   # cached JSON under _raw/jo
python3 scripts/jo_convert.py ../_raw/jo .
```
