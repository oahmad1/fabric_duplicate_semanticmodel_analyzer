# Semantic Model Duplicate Finder - Testing Guide

Use this guide to test the Fabric Semantic Model Duplicate Finder skill and scanner.

## What this does

This package helps identify likely duplicate or overlapping Power BI semantic models in Microsoft Fabric. It compares model metadata across:

- Tables
- Columns
- Measure names
- Measure expressions
- Relationships
- Data sources

The output is a ranked list of consolidation candidates. A finding is not a delete recommendation; model owners should validate usage, lineage, certification, and report dependencies before retiring anything.

## Tester prerequisites

For offline sample testing:

- Python 3.10 or later

For real Fabric testing:

- Python 3.10 or later
- Azure CLI
- Access to one or more Fabric or Power BI workspaces
- Permission to read semantic models in those workspaces
- Power BI tenant setting enabled for Execute Queries REST API, if using metadata export

## Folder layout

```text
fabric-semantic-model-duplicates
|-- README.md
|-- TESTING_GUIDE.md
|-- TEST_RESULTS.md
|-- results
|   |-- dummy-test-results.csv
|   |-- dummy-test-results.html
|   |-- dummy-test-results.json
|   `-- dummy-test-results.md
|-- samples
|   |-- dummy_semantic_models.json
|   `-- semantic_models.sample.json
|-- skills
|   `-- powerbi-semantic-model-governance-cli
|       |-- SKILL.md
|       `-- references
|           `-- metadata-contract.md
|-- tests
|   `-- test_semantic_model_duplicate_finder.py
`-- tools
    `-- semantic_model_duplicate_finder.py
```

## Test 1: Offline sample comparison

This test does not require Fabric access.

```powershell
cd "C:\path\to\fabric-semantic-model-duplicates"

python .\tools\semantic_model_duplicate_finder.py compare `
  --input .\samples\semantic_models.sample.json `
  --format md
```

Expected result:

- `Sales Certified` and `Sales Certified Copy` should classify as `likely_duplicate`.
- `Sales Department Mart` should classify as `high_overlap` with the certified sales model.
- `HR Headcount` should not appear because it is unrelated.

## Test 1b: Rich dummy model comparison

This is the best test for users who do not have any semantic models yet.

```powershell
cd "C:\path\to\fabric-semantic-model-duplicates"

python .\tools\semantic_model_duplicate_finder.py compare `
  --input .\samples\dummy_semantic_models.json `
  --format md
```

Expected result:

- `Contoso Sales Certified` and `Contoso Sales Executive Copy` should classify as `likely_duplicate`.
- `Contoso Sales Regional Extended` should classify as `high_overlap` with both sales models.
- The Markdown report should include a `Common objects` section listing the shared tables, columns, and measures for each finding.
- `Contoso Inventory Operations`, `Contoso HR Headcount`, and `Contoso Sales KPI Thin Model` should not appear with the default `--min-score 0.60` threshold.
- The generated expected files are in `results\dummy-test-results.md`, `results\dummy-test-results.csv`, `results\dummy-test-results.json`, and `results\dummy-test-results.html`.
- The published result summary is in `TEST_RESULTS.md`.

## Test 2: Unit tests

```powershell
cd "C:\path\to\fabric-semantic-model-duplicates"
python -m unittest discover -s tests
```

Expected result:

```text
Ran 7 tests
OK
```

## Test 3: Export real workspace metadata

Sign in first:

```powershell
az login --allow-no-subscriptions
```

Export one workspace:

```powershell
python .\tools\semantic_model_duplicate_finder.py export `
  --workspace-name "Your Workspace Name" `
  --output .\inventory.json `
  --delay 0.25
```

Export multiple workspaces:

```powershell
python .\tools\semantic_model_duplicate_finder.py export `
  --workspace-name "Workspace One" `
  --workspace-name "Workspace Two" `
  --output .\inventory.json `
  --delay 0.25
```

If you know workspace IDs:

```powershell
python .\tools\semantic_model_duplicate_finder.py export `
  --workspace-id "00000000-0000-0000-0000-000000000000" `
  --workspace-id "11111111-1111-1111-1111-111111111111" `
  --output .\inventory.json `
  --delay 0.25
```

The export writes warnings into `inventory.json` when a model or metadata endpoint is inaccessible. To fail immediately on the first access issue, add `--strict`.

## Test 4: Compare real exported metadata

Markdown output:

```powershell
python .\tools\semantic_model_duplicate_finder.py compare `
  --input .\inventory.json `
  --format md
```

CSV output:

```powershell
python .\tools\semantic_model_duplicate_finder.py compare `
  --input .\inventory.json `
  --format csv `
  --output .\duplicate-models.csv
```

JSON output:

```powershell
python .\tools\semantic_model_duplicate_finder.py compare `
  --input .\inventory.json `
  --format json `
  --output .\duplicate-models.json
```

HTML output:

```powershell
python .\tools\semantic_model_duplicate_finder.py compare `
  --input .\inventory.json `
  --format html `
  --output .\duplicate-models.html
```

By default, each finding lists up to 25 common tables, columns, and measures. To list all common objects:

```powershell
python .\tools\semantic_model_duplicate_finder.py compare `
  --input .\inventory.json `
  --format md `
  --common-limit 0
```

## Suggested test scenarios

Ask testers to try at least two scenarios:

| Scenario | What to test | Expected behavior |
|---|---|---|
| Known copy | Compare a model and a copied version of it | Classified as `likely_duplicate`. |
| Extended copy | Compare an enterprise model and a departmental model built from it | Classified as `high_overlap`. |
| Same source, different model | Compare models using the same warehouse but different objects | Lower score or no finding. |
| Unrelated domains | Compare HR and Sales models | No finding above default threshold. |
| Limited permissions | Include a workspace with restricted model access | Export completes with warnings unless `--strict` is used. |

## How to read the scores

| Field | Meaning |
|---|---|
| `duplicateScore` | Weighted Jaccard similarity. Best for near-identical models. |
| `overlapScore` | Weighted containment-aware score. Best for copied-and-extended models. |
| `commonObjects` | JSON block containing common tables, columns, measures, measure expressions, relationships, and data sources. |
| `likely_duplicate` | Strong consolidation candidate. |
| `high_overlap` | Manual review recommended; one model may be derived from another. |
| `partial_overlap` | Shared structure exists but confidence is lower. |

Default thresholds:

| Threshold | Classification |
|---:|---|
| `duplicateScore >= 0.85` | `likely_duplicate` |
| `duplicateScore >= 0.65` or `overlapScore >= 0.65` | `high_overlap` |
| Below `0.60` | Hidden by default |

To make the report more sensitive:

```powershell
python .\tools\semantic_model_duplicate_finder.py compare `
  --input .\inventory.json `
  --min-score 0.45 `
  --format md
```

To report only stronger candidates:

```powershell
python .\tools\semantic_model_duplicate_finder.py compare `
  --input .\inventory.json `
  --min-score 0.75 `
  --format md
```

## Privacy and data handling

The exported inventory contains semantic model metadata and data source identifiers. Treat it as internal information.

Do not share raw `inventory.json` outside approved company locations. If you need to share findings broadly, prefer the CSV or Markdown comparison output and remove model IDs or data source details if they are sensitive.

## Common issues

| Issue | Likely cause | What to try |
|---|---|---|
| `az` not found | Azure CLI is not installed or not on PATH | Install Azure CLI and restart the terminal. |
| Login succeeds but no workspaces are found | Account lacks workspace access or workspace name does not exactly match | Try `--workspace-id` or verify workspace access in Fabric. |
| DAX metadata warnings | Execute Queries API disabled or user lacks semantic model permission | Ask a Power BI admin to confirm tenant setting and model access. |
| Data source warnings | User cannot read dataset data source metadata | Continue testing; confidence may be lower without this signal. |
| Few or no findings | Models may not be duplicates, or threshold is too high | Retry with `--min-score 0.45` for exploratory review. |

## Feedback template

Please capture this information for each test run:

```text
Tester:
Date:
Python version:
Azure CLI version:
Workspace scope:
Number of semantic models exported:
Number of findings:
Did known duplicates appear? Yes/No
Were any false positives found?
Were any expected duplicates missed?
Warnings from inventory.json:
Suggested changes:
```

## Skill testing

To test the skill as a local Copilot CLI skill, create a symlink:

```powershell
New-Item -ItemType SymbolicLink `
  -Path "$env:USERPROFILE\.copilot\skills\powerbi-semantic-model-governance-cli" `
  -Target ".\skills\powerbi-semantic-model-governance-cli"
```

Start a new Copilot CLI session and try prompts such as:

```text
Find duplicate semantic models in the Finance Analytics workspace.
```

```text
Audit semantic model sprawl across these workspace IDs and export high-overlap candidates to CSV.
```

```text
Compare this semantic model inventory JSON and summarize consolidation candidates.
```
