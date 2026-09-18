# Fabric Duplicate Semantic Model Analyzer

This repository contains a skills-for-fabric style governance skill and CLI scanner that identifies likely duplicate or overlapping Power BI semantic models in Microsoft Fabric.

## Why this is a good IP idea

Semantic model sprawl is a common Fabric and Power BI governance problem. A skill that can inventory models, compare model objects, and produce consolidation candidates is useful because it turns a manual Center of Excellence review into a repeatable audit.

The approach mirrors the governance intent of tools such as Measure Killer model similarity, but keeps the implementation open-ended:

- Discover semantic models through Fabric and Power BI APIs.
- Extract metadata with DAX `INFO.VIEW.*` rowsets.
- Compare normalized tables, columns, measures, relationships, and data sources.
- Score likely duplicates and high-overlap models.
- Produce an auditable JSON, CSV, or Markdown report.

## Contents

| Path | Purpose |
|---|---|
| `.github\workflows\test.yml` | GitHub Actions workflow for unit tests. |
| `skills\powerbi-semantic-model-governance-cli\SKILL.md` | skills-for-fabric compatible skill definition. |
| `skills\powerbi-semantic-model-governance-cli\references\metadata-contract.md` | Metadata and report contract for duplicate detection. |
| `tools\semantic_model_duplicate_finder.py` | Python CLI for exporting metadata and comparing semantic models. |
| `samples\semantic_models.sample.json` | Small sample inventory with duplicate, overlapping, and unrelated models. |
| `samples\dummy_semantic_models.json` | Richer synthetic inventory for testers without Fabric access. |
| `results\dummy-test-results.*` | Expected output generated from the dummy inventory. |
| `results\dummy-test-results.html` | Shareable HTML report generated from dummy inventory. |
| `TEST_RESULTS.md` | Published dummy run results and interpretation. |
| `tests\test_semantic_model_duplicate_finder.py` | Unit tests for the scoring behavior. |

## Clone

```powershell
git clone https://github.com/oahmad1/fabric_duplicate_semanticmodel_analyzer.git
cd fabric_duplicate_semanticmodel_analyzer
```

## Quick start

Run the scanner on the sample metadata:

```powershell
python .\tools\semantic_model_duplicate_finder.py compare --input .\samples\semantic_models.sample.json --format md
```

Run the richer dummy scenario and compare your output with the checked-in expected results:

```powershell
python .\tools\semantic_model_duplicate_finder.py compare --input .\samples\dummy_semantic_models.json --format md
```

Create a shareable HTML report:

```powershell
python .\tools\semantic_model_duplicate_finder.py compare `
  --input .\samples\dummy_semantic_models.json `
  --format html `
  --output .\results\dummy-test-results.html
```

Export metadata from accessible Power BI workspaces, then compare it:

```powershell
az login --allow-no-subscriptions

python .\tools\semantic_model_duplicate_finder.py export `
  --workspace-name "Finance Analytics" `
  --output .\inventory.json

python .\tools\semantic_model_duplicate_finder.py compare `
  --input .\inventory.json `
  --format csv `
  --output .\duplicate-models.csv
```

Comparison output supports `json`, `csv`, `md`, and `html`. All formats include the common tables, columns, and measures for each finding. Use `--common-limit 0` to list every shared object instead of the default first 25 per object type.

The exporter uses the Power BI REST API for workspace and dataset discovery, `executeQueries` for DAX `INFO.VIEW.*` metadata, and the Power BI data sources endpoint for connection overlap. If tenant settings or permissions block a model, the export records a warning for that model.

For a shareable step-by-step validation plan, see [`TESTING_GUIDE.md`](TESTING_GUIDE.md). For the published dummy test run, see [`TEST_RESULTS.md`](TEST_RESULTS.md).

## Installing the skill locally

To test as a personal Copilot CLI skill:

```powershell
New-Item -ItemType SymbolicLink `
  -Path "$env:USERPROFILE\.copilot\skills\powerbi-semantic-model-governance-cli" `
  -Target ".\skills\powerbi-semantic-model-governance-cli"
```

To contribute to `microsoft/skills-for-fabric`, copy the skill folder under `skills\`, copy or adapt the companion tool according to repository guidance, and add a changelog entry.

## Scoring summary

The duplicate score is weighted Jaccard similarity. The overlap score also considers containment, so a departmental model copied from a certified enterprise model can be detected even when one model has extra tables or measures.

| Signal | Default weight |
|---|---:|
| Tables | 0.20 |
| Columns | 0.25 |
| Measure names | 0.10 |
| Measure expressions | 0.15 |
| Relationships | 0.15 |
| Data sources | 0.15 |

Default classifications:

| Classification | Meaning |
|---|---|
| `likely_duplicate` | Models are strong consolidation candidates. |
| `high_overlap` | One model may be copied from or heavily overlap another. |
| `partial_overlap` | Shared objects exist, but manual review is needed. |
