# Security

## Supported use

This repository contains a read-only scanner for semantic model metadata. It should not delete, modify, rename, or publish Power BI semantic models.

## Data handling

Exports can contain internal metadata such as model names, table names, column names, measure definitions, relationship shapes, and data source identifiers. Treat real `inventory.json` exports as internal data.

Do not commit real tenant exports, customer metadata, credentials, secrets, tokens, gateway credentials, or connection strings.

## Reporting issues

If you find a security issue, do not open a public issue with sensitive details. Report it privately through your organization's approved vulnerability disclosure process.

