# Pagination Demo — Multi-Level GraphQL Export

A Python script demonstrating how to paginate through multiple levels of lists in a single GraphQL query and export the complete result set to a JSON file.

## Overview

This script fetches items of one or more configured types from the Zeenea Catalog GraphQL API. For each item it retrieves:

- Core metadata (id, key, name, type, completion, description, last update)
- **Custom connections** — any connections listed in `config.json`, each with an explicit output name

All levels are fully paginated:

1. The top-level items list is paged using the `$after` cursor variable.
2. Each connection sub-list is paged individually per item when its first page reports `hasNextPage: true`.

Once all pagination is exhausted, every item with its complete sub-lists is written to a single timestamped JSON file.

## Features

- **Multi-level pagination**: Handles arbitrarily deep result sets at both the items level and each sub-list level
- **Fully configurable connections**: All connection fields are driven by `config.json` — no fields are hardcoded. Add any connection (including `members`, `curators`, etc.) by listing it in `connections`.
- **Explicit output names**: Each connection entry specifies both the internal ref and the key used in the JSON export, so the output structure is always predictable and valid.
- **Single JSON export**: The complete, fully-resolved result set is written to one file at the end of execution
- **Configurable page size**: `pagination_size` controls how many items are fetched per API call (default: 20)
- **Error logging**: Non-fatal errors are collected and written to a timestamped log file
- **Debug mode**: Optionally logs every API request and response to a timestamped debug log file

## Requirements

- Python 3.6+
- `requests` library:

```bash
pip install requests
pip install "urllib3<2"  # Avoids OpenSSL warnings on macOS
```

## Configuration

Create a `config.json` file in the same directory as the script:

```json
{
  "zeenea_url": "https://<tenant>.zeenea.app",
  "api_key": "<your-api-key>",
  "datatypes_to_export": ["dataset"],
  "connections": [
    ["members", "LinkedItems"],
    ["curators", "Curators"],
    ["responsabilite-1", "Responsabilite_1"]
  ],
  "pagination_size": 20,
  "debug_mode": false
}
```

### Configuration Options

| Key | Type | Required | Default | Description |
|-----|------|----------|---------|-------------|
| `zeenea_url` | string | Yes | — | Base URL of your Zeenea instance. Must be HTTPS and end with `.zeenea.app` |
| `api_key` | string | Yes | — | API key for authentication (see below) |
| `datatypes_to_export` | array | Yes | — | One or more item types to export, e.g. `["dataset", "field"]` |
| `connections` | array | No | `[]` | Connections to include. Each entry is a `[ref, output_name]` pair (see below) |
| `pagination_size` | integer | No | `20` | Number of items to request per API call |
| `debug_mode` | boolean | No | `false` | When `true`, logs every API request and full response to a timestamped file |

### Connections Format

Each entry in `connections` is a two-element list:

```json
["<connection-ref>", "<output-name>"]
```

- **`connection-ref`**: The internal connection reference string as configured in Zeenea (e.g. `"members"`, `"curators"`, `"responsabilite-1"`). This is passed as the `ref` argument in the GraphQL query.
- **`output-name`**: The key used for this connection in the GraphQL query alias and in the JSON export. **Must be a valid identifier**: only letters, digits, and underscores; must not start with a digit.

| Connection ref | Output name | Valid? |
|---|---|---|
| `"members"` | `"LinkedItems"` | Yes |
| `"curators"` | `"Curators"` | Yes |
| `"responsabilite-1"` | `"Responsabilite_1"` | Yes |
| `"$z_owner"` | `"Owner"` | Yes |
| `"my connection"` | `"my connection"` | **No** — spaces not allowed |
| `"members"` | `"1stField"` | **No** — cannot start with a digit |

If an output name is invalid, the script exits with a validation error before making any API calls.

### Getting an API Key

1. In the Zeenea UI, navigate to **Administration > API Keys**
2. Click **Create API Key**, give it a name and select the **Admin** scope
3. Click **Create API Key** again, then click **Copy and go back to list**
4. Paste the key into `config.json` as the `api_key` value
5. Remove the `X-API-SECRET: ` prefix from the pasted value if present — only the token itself should be stored

## How It Works

### Level 1 — Top-level items pagination

The initial `after` value is `"*"` (Zeenea's start-of-list sentinel). After each page the `endCursor` from `pageInfo` is used as `after` for the next request, until `hasNextPage` is `false`.

### Level 2 — Sub-list pagination per item

The initial items query fetches the first page of every configured connection with `after: "*"` embedded in the query. If a connection's `pageInfo.hasNextPage` is `true`, the script issues follow-up requests targeting that specific item by key until all nodes are collected.

Cursors are tracked independently for every sub-list of every item — a large connection on one item does not affect pagination of any other sub-list.

### GraphQL Query Structure

The query is built dynamically from `config.json`. Given the example config above, the generated query looks like:

```graphql
query Items($type: ItemType!, $first: Int, $after: String) {
  items(type: $type, first: $first, after: $after) {
    nodes {
      id
      type
      key
      name
      completion
      descriptionV2 { content { content } }
      lastCatalogMetadataUpdate

      # One block per entry in config.connections:
      LinkedItems: connection(ref: "members", after: "*") {
        nodes { id type key }
        pageInfo { startCursor hasNextPage hasPreviousPage endCursor }
        totalCount
      }

      Curators: connection(ref: "curators", after: "*") {
        nodes { name id key }
        pageInfo { startCursor hasNextPage hasPreviousPage endCursor }
        totalCount
      }

      Responsabilite_1: connection(ref: "responsabilite-1", after: "*") {
        nodes { name id key }
        pageInfo { startCursor hasNextPage hasPreviousPage endCursor }
        totalCount
      }
    }
    pageInfo { startCursor hasNextPage endCursor }
    totalCount
  }
}
```

## Output

### JSON Export

**Location:** `exports/export_YYYYMMDD_HHMMSS.json`

**Structure:**

```json
{
  "export_metadata": {
    "timestamp": "2026-03-30T14:22:05.123456",
    "zeenea_url": "https://your-instance.zeenea.app",
    "datatypes_exported": ["dataset"],
    "connections_included": [["members", "LinkedItems"], ["curators", "Curators"]],
    "pagination_size": 20,
    "total_items": 142
  },
  "results": {
    "dataset": [
      {
        "id": "...",
        "key": "connection/schema/table",
        "name": "My Table",
        "type": "dataset",
        "completion": 0.75,
        "descriptionV2": { "content": [{ "content": "Description text" }] },
        "lastCatalogMetadataUpdate": "2026-03-15T10:00:00Z",
        "LinkedItems": {
          "nodes": [{ "id": "...", "type": "field", "key": "..." }],
          "totalCount": 3
        },
        "Curators": {
          "nodes": [{ "name": "Alice", "id": "...", "key": "..." }],
          "totalCount": 1
        },
        "Responsabilite_1": {
          "nodes": [{ "name": "Bob", "id": "...", "key": "..." }],
          "totalCount": 1
        }
      }
    ]
  }
}
```

Each connection in the output contains the **complete** set of nodes with a `totalCount`. The `pageInfo` object is omitted because pagination is already complete.

### Error Log (if errors occurred)

**Location:** `error_YYYYMMDD_HHMMSS.log`

Contains timestamped error messages. Errors are non-fatal — the export continues and a partial result is written.

### Debug Log (if `debug_mode: true`)

**Location:** `debug_YYYYMMDD_HHMMSS.log`

Contains the full request payload and response body for every API call made during the run, with timestamps. Useful for diagnosing unexpected results or API errors.

## Usage

```bash
python pagination-demo.py
```

## Example Output

```
======================================================================
PAGINATION DEMO - MULTI-LEVEL GRAPHQL PAGINATION EXPORT
======================================================================

v- DEBUG MODE ENABLED

v- Zeenea URL       : https://your-instance.zeenea.app
v- Types to export  : ['dataset']
v- Connections      : [('members', 'LinkedItems'), ('curators', 'Curators')]
v- Pagination size  : 20

Processing type: dataset
----------------------------------------------------------------------
  Fetching items of type: dataset
    Page 1: 20 items  (reported total: 42)
    Page 2: 20 items  (reported total: 42)
    Page 3: 2 items  (reported total: 42)
    v- Total items fetched: 42

Export Result:
----------------------------------------------------------------------
v- Exported 42 items to: /path/to/exports/export_20260330_142205.json
```

## Error Handling

### Configuration Errors (Fatal)

| Condition | Behaviour |
|---|---|
| `config.json` not found | Script exits with an error message |
| Invalid JSON | Script exits with a parse error |
| Missing required key | Script exits with a validation error |
| URL does not start with `https://` or end with `.zeenea.app` | Script exits with a validation error |
| A `connections` entry is not a `[ref, output_name]` pair | Script exits with a validation error |
| An output name is not a valid identifier | Script exits with a validation error |

### Runtime Errors (Non-Fatal)

| Condition | Behaviour |
|---|---|
| GraphQL errors in response | Error logged, that item type stops fetching |
| HTTP / network error on main query | Error logged, that item type stops fetching |
| HTTP / network error on sub-list page | Error logged, sub-list uses nodes fetched so far |
| GraphQL errors on sub-list page | Error logged, sub-list uses nodes fetched so far |

In all non-fatal cases the export file is still written with whatever data was successfully retrieved.

## Troubleshooting

**Empty `results` in the JSON file**
- Verify the `datatypes_to_export` values match actual item types in your Zeenea instance
- Check the error log for authentication or API errors

**Missing connections in item output**
- Confirm the connection ref strings (first element of each pair) match the exact refs configured in Zeenea (case-sensitive)
- The output key in the JSON is the second element of each `[ref, output_name]` pair

**Output name validation error on startup**
- Output names must contain only letters, digits, and underscores, and must not start with a digit
- If your connection ref contains `-`, `$`, or spaces, choose a clean output name manually, e.g. `["my-ref", "My_Ref"]`

**Incomplete node lists**
- If a connection's `totalCount` is higher than the number of nodes, check the error log for pagination failures on that connection
