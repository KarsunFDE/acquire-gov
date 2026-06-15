# Solicitation section reference — token caps + few-shot anchors

**Source:** research pass 2026-06-15 (cited to acquisition.gov / eCFR / Cornell
LII). Feeds the M1 demo-redesign generators (`DEMO-REDESIGN-spec.md` §5).
Structure per **FAR 15.204-1, Table 15-1**
([acquisition.gov](https://www.acquisition.gov/far/15.204-1)).

`max_tokens ≈ words × 1.4`, rounded and kept tight for cost control. Only C/L/M
get large budgets; boilerplate D/E/F/G fit under ~450 tokens each.

## Per-section length + token cap

| Sec | Title | Typical words | `max_tokens` | Source |
|---|---|---|---|---|
| A | Solicitation/contract form | 150–400 | 400 | [15.204-1](https://www.acquisition.gov/far/15.204-1) |
| B | Supplies/services + prices | 200–800 | 900 | [15.204-1](https://www.acquisition.gov/far/15.204-1) |
| C | Description / SOW / PWS | 2,000–15,000+ | 6000 (chunk long SOWs) | [15.204-1](https://www.acquisition.gov/far/15.204-1) · [AcqNotes SOW](https://acqnotes.com/acqnote/tasks/statement-of-work) |
| D | Packaging and marking | 60–250 | 300 | [GSAR 552.211-75](https://www.acquisition.gov/gsam/552.211-75) |
| E | Inspection and acceptance | 80–300 | 350 | [FAR 52.246-2](https://www.acquisition.gov/far/52.246-2) |
| F | Deliveries or performance | 100–400 | 450 | [FAR 52.247-34](https://www.acquisition.gov/far/52.247-34) |
| G | Contract administration data | 100–400 | 450 | [FAR 52.232-25](https://www.acquisition.gov/far/52.232-25) |
| H | Special contract requirements | 300–1,500 | 1800 | [15.204-1](https://www.acquisition.gov/far/15.204-1) |
| I | Contract clauses | incorporated by ref (52.252-2) | 700 | [15.204-1](https://www.acquisition.gov/far/15.204-1) |
| J | List of attachments | 50–200 (a list) | 250 | [15.204-1](https://www.acquisition.gov/far/15.204-1) |
| K | Reps / certs / statements | 150–500 solicitation-specific | 600 | [FAR 52.204-8](https://www.acquisition.gov/far/52.204-8) · [52.219-1](https://www.acquisition.gov/far/52.219-1) |
| L | Instructions to offerors | 1,000–4,000 | 4000 | [15.204-1](https://www.acquisition.gov/far/15.204-1) |
| M | Evaluation factors | 500–2,000 | 2500 | [15.204-1](https://www.acquisition.gov/far/15.204-1) |

## Generation strategy notes (implementer)

- **D/E/F/G**: near-verbatim FAR/GSAR clause language. Prefer retrieving canonical
  clause text and lightly merging solicitation specifics over free-generating;
  use the snippets below as few-shot anchors. Single bundled Haiku call, tight caps.
- **K = incorporation, not prose.** Bulk of reps/certs lives in SAM.gov via
  FAR 52.204-8; solicitation needs only the pointer + the set-aside notice
  clause(s). Do NOT free-draft cert text — **select clause numbers by set-aside
  type from the table below** (reuse the Part II clause-matrix pattern).
- **52.219-14 (Limitations on Subcontracting)** accompanies ANY small-business
  set-aside regardless of subtype.
- **C is the only section that can blow a budget** — chunk SOW generation if long.

## Few-shot anchors

### D — Packaging and Marking
> "Unless otherwise specified, all items shall be preserved, packaged, and packed
> in accordance with normal commercial practices… Packaging and packing shall
> comply with the requirements of the Uniform Freight Classification and the
> National Motor Freight Classification (issue in effect at time of shipment)."
> — GSAR 552.211-75 ([acquisition.gov](https://www.acquisition.gov/gsam/552.211-75))

> Military items: "Preservation, packaging, and marking shall be in accordance
> with MIL-STD-129 for all CLINs identified in Section B."
> ([AcqNotes — Section D](https://acqnotes.com/acqnote/tasks/section-d-packaging-and-marking) — TLS-failed on direct fetch; re-fetch for verbatim MIL-STD-129 phrasing)

### E — Inspection and Acceptance (FAR 52.246-2)
> "'Supplies,' as used in this clause, includes but is not limited to raw
> materials, components, intermediate assemblies, end products, and lots of
> supplies." — FAR 52.246-2(a) ([acquisition.gov](https://www.acquisition.gov/far/52.246-2))

> "The Contractor shall tender to the Government for acceptance only supplies that
> have been inspected in accordance with the inspection system and have been found
> by the Contractor to be in conformity with contract requirements."
> — FAR 52.246-2(b) ([eCFR](https://www.ecfr.gov/current/title-48/chapter-1/subchapter-H/part-52/subpart-52.2/section-52.246-2))

### F — Deliveries or Performance
> "The Contractor shall… deliver the shipment in good order and condition to the
> point of delivery specified in the contract; [and] be responsible for any loss
> of and/or damage to the goods occurring before receipt of the shipment by the
> consignee at the delivery point specified in the contract."
> — FAR 52.247-34, F.o.b. Destination ([acquisition.gov](https://www.acquisition.gov/far/52.247-34))

> PoP phrasing: "The period of performance of this contract is from [date] through
> [date], unless extended in accordance with the Option to Extend the Term of the
> Contract clause (FAR 52.217-9)."
> (per [FAR 52.242-15](https://www.ecfr.gov/current/title-48/chapter-1/subchapter-H/part-52/subpart-52.2/section-52.242-15))

### G — Contract Administration Data
> "The Contractor shall prepare and submit invoices to the designated billing
> office specified in the contract. A proper invoice must include [the items in
> paragraphs (a)(3)(i) through (x) of this clause]."
> — FAR 52.232-25, Prompt Payment ([acquisition.gov](https://www.acquisition.gov/far/52.232-25))

> "If the invoice does not comply with these requirements, the designated billing
> office will return it within 7 days after receipt… with the reasons why it is
> not a proper invoice." — FAR 52.232-25(a)(5) ([Cornell LII](https://www.law.cornell.edu/cfr/text/48/52.232-25))

### K — Representations and Certifications
Standard for essentially all competitive solicitations:
- **FAR 52.204-8** — Annual Reps and Certs (points offerors to SAM.gov). ([acquisition.gov](https://www.acquisition.gov/far/52.204-8))
- **FAR 52.219-1** — Small Business Program Representations (size self-cert).

> "The offeror represents as part of its offer that—(i) it ☐ is, ☐ is not a small
> business concern." — FAR 52.219-1(c)(1) ([acquisition.gov](https://www.acquisition.gov/far/52.219-1))

**Set-aside → notice clause (include only the matching one):**

| Set-aside | Notice clause | Source |
|---|---|---|
| Total small business | FAR 52.219-6 | [acquisition.gov](https://www.acquisition.gov/far/52.219-6) |
| Partial small business | FAR 52.219-7 | [acquisition.gov](https://www.acquisition.gov/far/52.219-7) |
| HUBZone | FAR 52.219-3 (+ eval pref 52.219-4) | [Part 19 guide](https://www.acquisition.gov/far-overhaul/far-part-deviation-guide/far-overhaul-part-19) |
| SDVOSB | FAR 52.219-27 | [Part 19 guide](https://www.acquisition.gov/far-overhaul/far-part-deviation-guide/far-overhaul-part-19) |
| EDWOSB | FAR 52.219-29 | [Part 19 guide](https://www.acquisition.gov/far-overhaul/far-part-deviation-guide/far-overhaul-part-19) |
| WOSB | FAR 52.219-30 | [Part 19 guide](https://www.acquisition.gov/far-overhaul/far-part-deviation-guide/far-overhaul-part-19) |
| 8(a) | via 52.204-8 / SAM.gov; set-aside under Subpart 19.8 | [FAR Part 19](https://www.acquisition.gov/far/part-19) |
| ANY small-biz set-aside (always pair) | FAR 52.219-14, Limitations on Subcontracting | [USDA deviation](https://www.usda.gov/sites/default/files/documents/far-class-deviation-regarding-limitations-subcontracting-small-business-concerns.pdf) |

> "Offers are solicited only from small business concerns. Offers received from
> concerns that are not small business concerns shall be considered nonresponsive
> and will be rejected." — FAR 52.219-6(c) ([acquisition.gov](https://www.acquisition.gov/far/52.219-6))
