---
name: powerbi-semantic-model-governance-cli
description: >
  Analyze duplicate and overlapping Power BI semantic models in Microsoft Fabric using Fabric REST APIs, Power BI REST APIs, DAX INFO.VIEW metadata, and CLI similarity scoring. Use when the user wants to: (1) find duplicate semantic models or dataset copies, (2) audit model sprawl across workspaces, (3) compare tables, columns, measures, relationships, and data sources, (4) prioritize consolidation candidates. Triggers: "duplicate semantic model", "semantic model sprawl", "model similarity", "dataset duplication audit", "find overlapping Power BI models", "Measure Killer alternative".
---

> **Update Check - ONCE PER SESSION (mandatory)**
> The first time this skill is used in a session, run the **check-updates** skill before proceeding.
> - **GitHub Copilot CLI / VS Code**: invoke the `check-updates` skill before using this skill.
> - **Claude Code / Cowork / Cursor / Windsurf / Codex**: compare the local package version against the remote version before using this skill.
> - Skip if the check was already performed earlier in this session.

> **CRITICAL NOTES**
> 1. To find workspace details, including workspace ID, list workspaces and use JMESPath filtering.
> 2. To find semantic model details, including item ID, list semantic models in the workspace and use JMESPath filtering.
> 3. Do not infer duplication from model names alone. Always compare model metadata.

# Power BI Semantic Model Governance - Duplicate Model Audit

## Table of Contents

| Task | Reference | Notes |
|---|---|---|
| Finding Workspaces and Items in Fabric | [COMMON-CLI.md - Finding Workspaces and Items in Fabric](../../common/COMMON-CLI.md#finding-workspaces-and-items-in-fabric) | Mandatory for resolving workspace IDs and semantic model IDs. |
| Authentication Recipes | [COMMON-CLI.md - Authentication Recipes](../../common/COMMON-CLI.md#authentication-recipes) | Use Azure CLI login and correct API resources. |
| Fabric Control-Plane API via az rest | [COMMON-CLI.md - Fabric Control-Plane API via az rest](../../common/COMMON-CLI.md#fabric-control-plane-api-via-az-rest) | Use for Fabric workspace and item discovery. |
| Power BI Semantic Model Consumption | [powerbi-consumption-cli](../powerbi-consumption-cli/SKILL.md) | Use DAX `INFO.VIEW.*` metadata rowsets. |
| Semantic Model Authoring Metadata | [semantic-model-properties-guide.md](../powerbi-authoring-cli/references/semantic-model-properties-guide.md) | Use Power BI REST API metadata such as data sources and refresh settings. |
| Metadata Contract | [metadata-contract.md](./references/metadata-contract.md) | Normalized inventory and report schema for duplicate detection. |

## Prerequisites

- Azure CLI authenticated with `az login --allow-no-subscriptions` when the user does not have an Azure subscription.
- User or service principal access to the target Fabric workspaces and semantic models.
- Power BI tenant setting that allows Execute Queries REST API calls when using DAX `INFO.VIEW.*` extraction through `executeQueries`.
- Optional: semantic-link-labs or TOM/XMLA metadata extraction when richer metadata is needed than `INFO.VIEW.*` exposes.

## Must/Prefer/Avoid

### MUST DO

- Keep this workflow read-only. Inventory, compare, and report only.
- Resolve workspace and semantic model identities dynamically; do not hardcode IDs in reusable output.
- Compare normalized metadata from tables, columns, measures, relationships, and data sources.
- Preserve warnings for inaccessible models instead of silently dropping them from the audit.
- Treat connection strings, server names, and metadata as potentially sensitive; do not publish raw exports outside approved locations.
- State that similarity scores are consolidation candidates, not proof that a model is safe to delete.

### PREFER

- Start with a bounded workspace scope, then expand to more workspaces once the scoring behavior is validated.
- Use a two-pass workflow: first inventory all semantic models, then run pairwise comparison offline.
- Use `INFO.VIEW.*` functions first because they are read-oriented and broadly suitable for metadata discovery.
- Include data source similarity when permissions allow; it helps separate true duplicates from unrelated models with similar table names.
- Use containment scoring in addition to Jaccard similarity to catch copies that have been extended with extra departmental objects.
- Export JSON as the system of record and generate CSV or Markdown only as presentation formats.

### AVOID

- Do not delete, rename, move, or overwrite semantic models as part of this skill.
- Do not classify two models as duplicates based only on display name, owner, workspace, or refresh schedule.
- Do not run tenant-wide scans without setting expectations about runtime, permissions, and API throttling.
- Do not expose credential fields, gateway secrets, OAuth tokens, or connection-string secrets in reports.
- Do not treat inaccessible models as non-duplicates; report them as incomplete coverage.

## Recommended Workflow

1. Define scope: workspace names, workspace IDs, capacity, domain, or a tenant-wide accessible-workspace scan.
2. Discover candidate semantic models:

```bash
az rest --method get \
  --resource "https://api.fabric.microsoft.com" \
  --url "https://api.fabric.microsoft.com/v1/workspaces/$WS_ID/semanticModels"
```

3. Collect read-only metadata from each model. Prefer DAX `INFO.VIEW.*` rowsets through the Power BI Execute Queries API or the active `ExecuteQuery` MCP capability.
4. Collect data source metadata through the Power BI REST API when allowed.
5. Normalize object names and DAX expressions before comparing.
6. Compute duplicate and overlap scores for every pair of models in scope.
7. Report likely duplicates first, then high-overlap candidates, including shared object counts and model access warnings.

## Metadata Extraction Queries

Use projected DAX rowsets to avoid pulling unnecessary metadata.

### Tables

```dax
EVALUATE
SELECTCOLUMNS(
    INFO.VIEW.TABLES(),
    "Name", [Name],
    "IsHidden", [IsHidden]
)
ORDER BY [Name]
```

### Columns

```dax
EVALUATE
SELECTCOLUMNS(
    INFO.VIEW.COLUMNS(),
    "Table", [Table],
    "Name", [Name],
    "DataType", [DataType],
    "IsHidden", [IsHidden]
)
ORDER BY [Table], [Name]
```

### Measures

```dax
EVALUATE
SELECTCOLUMNS(
    INFO.VIEW.MEASURES(),
    "Table", [Table],
    "Name", [Name],
    "Expression", [Expression],
    "FormatString", [FormatString],
    "IsHidden", [IsHidden]
)
ORDER BY [Table], [Name]
```

### Relationships

```dax
EVALUATE
SELECTCOLUMNS(
    INFO.VIEW.RELATIONSHIPS(),
    "FromTable", [FromTable],
    "FromColumn", [FromColumn],
    "ToTable", [ToTable],
    "ToColumn", [ToColumn],
    "Cardinality", [Cardinality],
    "CrossFilteringBehavior", [CrossFilteringBehavior],
    "IsActive", [IsActive]
)
```

## Similarity Scoring

Score model pairs on normalized metadata sets.

| Signal | Suggested weight | Why it matters |
|---|---:|---|
| Tables | 0.20 | Catches copied star schemas and marts. |
| Columns | 0.25 | Strong signal for reused table design. |
| Measure names | 0.10 | Finds business metric reuse. |
| Measure expressions | 0.15 | Finds renamed but logically identical measures. |
| Relationships | 0.15 | Confirms model shape and filter paths. |
| Data sources | 0.15 | Separates true duplicates from same-shaped models over different sources. |

Use both:

- **Duplicate score**: weighted Jaccard similarity, best for near-identical models.
- **Overlap score**: weighted containment, best for models where one is a subset or extended copy of another.

Recommended thresholds:

| Threshold | Classification |
|---:|---|
| Duplicate score `>= 0.85` | `likely_duplicate` |
| Duplicate score `>= 0.65` or overlap score `>= 0.80` | `high_overlap` |
| Score below threshold | Do not report unless the user asks for low-confidence results. |

## Report Requirements

Each finding should include:

- Left and right workspace names, model names, and model IDs.
- Duplicate score, overlap score, classification, and confidence.
- Per-signal scores and shared object counts.
- Common tables, columns, and measures for each finding, with a configurable limit for large models.
- Top shared measure expressions, relationships, and data sources when useful for reviewer confidence.
- JSON, CSV, Markdown, or HTML output depending on whether the user needs automation, spreadsheet review, CLI readability, or a browser-friendly report.
- Warnings for models with incomplete metadata extraction.
- Recommended next action: review, certify one model, consolidate reports, retire duplicate only after owner approval.

## Example Prompts

```text
Find duplicate semantic models in the Finance Analytics workspace.
```

```text
Audit semantic model sprawl across these workspace IDs and export the duplicate candidates to CSV.
```

```text
Compare these exported model metadata JSON files and show high-overlap Power BI models.
```

## Example CLI Flow

```powershell
python .\tools\semantic_model_duplicate_finder.py export `
  --workspace-name "Finance Analytics" `
  --output .\inventory.json

python .\tools\semantic_model_duplicate_finder.py compare `
  --input .\inventory.json `
  --min-score 0.65 `
  --format html `
  --output .\duplicate-models.html
```

## Interpretation Guidance

- `likely_duplicate` means the pair is a strong consolidation candidate.
- `high_overlap` means one model may be copied from the other, or both may be derived from a shared pattern.
- Similarity does not identify which model is authoritative. Use endorsement state, lineage, refresh reliability, report dependencies, owner approval, and usage metrics before making consolidation decisions.
- Data source equality can be unavailable because of permissions. If unavailable, the finding should be marked with lower confidence rather than removed.
