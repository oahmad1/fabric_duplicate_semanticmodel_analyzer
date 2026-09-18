# Published Test Results - Dummy Semantic Models

Date: 2026-09-18

These results were generated from synthetic semantic model metadata in `samples\dummy_semantic_models.json`. No Fabric workspace, capacity, tenant setting, or real semantic model access is required for this test.

## Test input

The dummy inventory contains six semantic models:

| Workspace | Semantic model | Scenario |
|---|---|---|
| Dummy Enterprise BI | Contoso Sales Certified | Authoritative enterprise sales model. |
| Dummy Executive Reporting | Contoso Sales Executive Copy | Near-identical copy of the certified sales model. |
| Dummy Regional Sales | Contoso Sales Regional Extended | Copied from the sales model, then extended with regional quota objects. |
| Dummy Operations | Contoso Inventory Operations | Shares only generic Product and Date concepts. |
| Dummy HR | Contoso HR Headcount | Unrelated HR model. |
| Dummy Sales Experiments | Contoso Sales KPI Thin Model | Uses the same SalesDW source but has different model objects. |

## Commands run

```powershell
cd "C:\path\to\fabric_duplicate_semanticmodel_analyzer"

python .\tools\semantic_model_duplicate_finder.py compare `
  --input .\samples\dummy_semantic_models.json `
  --format md `
  --output .\results\dummy-test-results.md

python .\tools\semantic_model_duplicate_finder.py compare `
  --input .\samples\dummy_semantic_models.json `
  --format csv `
  --output .\results\dummy-test-results.csv

python .\tools\semantic_model_duplicate_finder.py compare `
  --input .\samples\dummy_semantic_models.json `
  --format json `
  --output .\results\dummy-test-results.json

python .\tools\semantic_model_duplicate_finder.py compare `
  --input .\samples\dummy_semantic_models.json `
  --format html `
  --output .\results\dummy-test-results.html

python -m unittest discover -s tests
```

## Unit test result

```text
.......
----------------------------------------------------------------------
Ran 7 tests in 0.020s

OK
```

## Scanner result

The scanner evaluated 6 dummy semantic models and returned 3 findings above the default `--min-score 0.60` threshold.

| Classification | Confidence | Duplicate | Overlap | Left model | Right model | Shared tables | Shared columns | Shared measures |
|---|---|---:|---:|---|---|---:|---:|---:|
| likely_duplicate | high | 1.0000 | 1.0000 | Dummy Enterprise BI / Contoso Sales Certified | Dummy Executive Reporting / Contoso Sales Executive Copy | 5 | 16 | 5 |
| high_overlap | high | 0.7722 | 0.8550 | Dummy Enterprise BI / Contoso Sales Certified | Dummy Regional Sales / Contoso Sales Regional Extended | 5 | 16 | 3 |
| high_overlap | high | 0.7722 | 0.8550 | Dummy Executive Reporting / Contoso Sales Executive Copy | Dummy Regional Sales / Contoso Sales Regional Extended | 5 | 16 | 3 |

## Common objects shown in the output

The Markdown report now includes a `Common objects` section for each finding.

### 1. Dummy Enterprise BI / Contoso Sales Certified <-> Dummy Executive Reporting / Contoso Sales Executive Copy

- **Tables:** `customer`, `date`, `geography`, `product`, `sales`
- **Columns:** `customer[customerkey] (int64)`, `customer[customername] (string)`, `customer[segment] (string)`, `date[datekey] (int64)`, `date[fiscalmonth] (string)`, `date[fiscalyear] (int64)`, `geography[country] (string)`, `geography[geographykey] (int64)`, `product[category] (string)`, `product[productkey] (int64)`, `sales[customerkey] (int64)`, `sales[discountamount] (decimal)`, `sales[orderdatekey] (int64)`, `sales[productkey] (int64)`, `sales[revenueamount] (decimal)`, `sales[saleskey] (int64)`
- **Measures:** `sales[average revenue per customer]`, `sales[discount rate]`, `sales[net revenue]`, `sales[revenue ytd]`, `sales[total revenue]`

### 2. Dummy Enterprise BI / Contoso Sales Certified <-> Dummy Regional Sales / Contoso Sales Regional Extended

- **Tables:** `customer`, `date`, `geography`, `product`, `sales`
- **Columns:** `customer[customerkey] (int64)`, `customer[customername] (string)`, `customer[segment] (string)`, `date[datekey] (int64)`, `date[fiscalmonth] (string)`, `date[fiscalyear] (int64)`, `geography[country] (string)`, `geography[geographykey] (int64)`, `product[category] (string)`, `product[productkey] (int64)`, `sales[customerkey] (int64)`, `sales[discountamount] (decimal)`, `sales[orderdatekey] (int64)`, `sales[productkey] (int64)`, `sales[revenueamount] (decimal)`, `sales[saleskey] (int64)`
- **Measures:** `sales[net revenue]`, `sales[revenue ytd]`, `sales[total revenue]`

### 3. Dummy Executive Reporting / Contoso Sales Executive Copy <-> Dummy Regional Sales / Contoso Sales Regional Extended

- **Tables:** `customer`, `date`, `geography`, `product`, `sales`
- **Columns:** `customer[customerkey] (int64)`, `customer[customername] (string)`, `customer[segment] (string)`, `date[datekey] (int64)`, `date[fiscalmonth] (string)`, `date[fiscalyear] (int64)`, `geography[country] (string)`, `geography[geographykey] (int64)`, `product[category] (string)`, `product[productkey] (int64)`, `sales[customerkey] (int64)`, `sales[discountamount] (decimal)`, `sales[orderdatekey] (int64)`, `sales[productkey] (int64)`, `sales[revenueamount] (decimal)`, `sales[saleskey] (int64)`
- **Measures:** `sales[net revenue]`, `sales[revenue ytd]`, `sales[total revenue]`

## Expected interpretation

| Finding | Expected interpretation |
|---|---|
| Contoso Sales Certified vs. Contoso Sales Executive Copy | Correctly identified as a near-identical duplicate. This is the clearest consolidation candidate. |
| Contoso Sales Certified vs. Contoso Sales Regional Extended | Correctly identified as high overlap because the regional model contains the enterprise sales model plus extra regional objects. |
| Contoso Sales Executive Copy vs. Contoso Sales Regional Extended | Correctly identified as high overlap for the same reason. |

## Expected non-findings

These models should not appear in the default report:

| Semantic model | Why it should not appear |
|---|---|
| Contoso Inventory Operations | It shares generic Product and Date concepts, but its facts, measures, relationships, and source database are different. |
| Contoso HR Headcount | It is an unrelated domain model. |
| Contoso Sales KPI Thin Model | It uses the same SalesDW data source, but its model objects are different, so source overlap alone is not enough to flag it. |

## Generated artifacts

| File | Purpose |
|---|---|
| `results\dummy-test-results.md` | Human-readable expected Markdown table plus common object sections. |
| `results\dummy-test-results.csv` | Spreadsheet-friendly output with `commonTables`, `commonColumns`, and `commonMeasures` fields. |
| `results\dummy-test-results.json` | Full scored output with per-dimension detail, `commonObjects`, and legacy `sharedSamples`. |
| `results\dummy-test-results.html` | Shareable browser-friendly report with score table and common object sections. |

## Final outcome

The offline dummy test proves the scanner can distinguish between:

- A true duplicate model.
- A copied-and-extended model.
- Same-source but structurally different models.
- Unrelated semantic models.

This is the expected baseline behavior testers should see before trying real Fabric workspace exports.
