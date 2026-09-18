# Semantic Model Duplicate Audit Metadata Contract

This contract keeps the duplicate scanner independent from the metadata extraction method. The same comparison logic can consume exports from Power BI REST APIs, Fabric REST APIs, DAX `INFO.VIEW.*`, TOM/XMLA, semantic-link-labs, or a notebook pipeline.

## Inventory shape

```json
{
  "generatedAt": "2026-09-18T18:42:22Z",
  "models": [
    {
      "workspaceId": "workspace-guid",
      "workspaceName": "Finance Analytics",
      "id": "semantic-model-guid",
      "name": "Sales Certified",
      "tables": [
        { "Name": "Sales", "IsHidden": false }
      ],
      "columns": [
        { "Table": "Sales", "Name": "Amount", "DataType": "Decimal", "IsHidden": false }
      ],
      "measures": [
        { "Table": "Sales", "Name": "Total Sales", "Expression": "SUM(Sales[Amount])" }
      ],
      "relationships": [
        {
          "FromTable": "Sales",
          "FromColumn": "CustomerKey",
          "ToTable": "Customer",
          "ToColumn": "CustomerKey",
          "Cardinality": "ManyToOne",
          "IsActive": true
        }
      ],
      "dataSources": [
        {
          "datasourceType": "Sql",
          "connectionDetails": {
            "server": "server.database.windows.net",
            "database": "SalesDW"
          }
        }
      ]
    }
  ],
  "warnings": [
    {
      "workspaceId": "workspace-guid",
      "modelId": "semantic-model-guid",
      "stage": "dax:measures",
      "message": "Execute Queries API is disabled or user lacks permission."
    }
  ]
}
```

## Required model fields

| Field | Required | Notes |
|---|---|---|
| `id` | Yes | Semantic model or dataset ID. |
| `name` | Yes | Semantic model display name. |
| `workspaceId` | Recommended | Needed to build owner follow-up and API links. |
| `workspaceName` | Recommended | Used in reports. |
| `tables` | Recommended | DAX `INFO.VIEW.TABLES()` rows or simple string names. |
| `columns` | Recommended | DAX `INFO.VIEW.COLUMNS()` rows. |
| `measures` | Recommended | DAX `INFO.VIEW.MEASURES()` rows. |
| `relationships` | Recommended | DAX `INFO.VIEW.RELATIONSHIPS()` rows. |
| `dataSources` | Optional | Power BI REST API `datasources` rows. |

## Normalization rules

- Case-fold object names.
- Trim whitespace and collapse repeated spaces.
- Normalize DAX expressions by removing comments, lowercasing, and removing whitespace around common operators.
- Treat relationship endpoints as an unordered pair for similarity so direction differences do not hide overlap.
- Ignore known secret-bearing fields such as passwords, access tokens, credential details, keys, and connection strings.

## Result shape

```json
{
  "left": {
    "workspaceName": "Finance Analytics",
    "modelName": "Sales Certified",
    "modelId": "model-a"
  },
  "right": {
    "workspaceName": "Regional BI",
    "modelName": "Sales Copy",
    "modelId": "model-b"
  },
  "classification": "likely_duplicate",
  "confidence": "high",
  "duplicateScore": 0.98,
  "overlapScore": 0.98,
  "dimensions": {
    "tables": { "jaccard": 1.0, "containment": 1.0, "shared": 8, "left": 8, "right": 8 }
  },
  "commonObjects": {
    "tables": { "items": ["customer", "date", "sales"], "omitted": 0 },
    "columns": { "items": ["sales[amount] (decimal)"], "omitted": 0 },
    "measures": { "items": ["sales[total sales]"], "omitted": 0 }
  },
  "sharedSamples": {
    "tables": ["customer", "date", "sales"]
  }
}
```

## Governance extensions

The first version should focus on structural duplication. Later versions can add:

- Report dependency counts from lineage APIs.
- Usage metrics to identify authoritative models.
- Endorsement/certification state.
- Owner and configured-by metadata.
- Refresh reliability and last refresh status.
- Sensitivity labels and workspace domain metadata.
- Capacity and storage mode.

## Recommended review workflow

1. Validate the top findings with model owners.
2. Choose the authoritative model using certification, usage, lineage, refresh health, and business ownership.
3. Migrate dependent reports from duplicate models.
4. Retire duplicate models only after owner approval and report dependency validation.
5. Repeat the audit on a schedule and track trend over time.
