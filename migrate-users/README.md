# migrate-users

Migrates Zeenea users from old email addresses to new ones. For each user in a CSV file, the script:

1. Looks up the existing user via the SCIM API
2. Creates a new user account with the new email address (if it doesn't already exist)
3. Replicates the existing user's group memberships, curated items, and contact connections to the new user
4. Validates the migration by comparing old and new users
5. Writes a validation report to `migration_validation_report.json`

## Requirements

- Python 3.7+ (standard library only — no third-party packages required)
- A Zeenea API key with read/write access
- A CSV file listing users to migrate

## Configuration

Copy or edit `config.json` in the same directory as the script:

```json
{
  "zeenea_url": "https://your-tenant.zeenea.app",
  "api_key": "<your-api-key>",
  "csv_path": "/path/to/users.csv",
  "responsibilities": []
}
```

| Key | Required | Description |
|---|---|---|
| `zeenea_url` | Yes | Tenant root URL. Must start with `https://` and end with `.zeenea.app`. |
| `api_key` | Yes | JWT API token used for both SCIM (`Authorization: Bearer`) and catalog (`X-API-SECRET`) calls. |
| `csv_path` | Yes | Absolute path to the CSV file of users to migrate. |
| `responsibilities` | No | List of responsibility/connection-type names to migrate. If omitted or empty, all connection types are retrieved from the API on the first user. Items containing `$` are treated as system-generated and excluded from migration and validation. |

### Getting an API Key

1. In the Zeenea UI, navigate to **Administration > API Keys**
2. Click **Create API Key**, give it a name and select the **Admin** scope
3. Click **Create API Key** again, then click **Copy and go back to list**
4. Paste the key into `config.json` as the `api_key` value
5. Remove the `X-API-SECRET: ` prefix from the pasted value if present — only the token itself should be stored

## CSV Format

The CSV file must have the following columns (with a header row):

| Column | Description |
|---|---|
| `first_name` | User's first name |
| `last_name` | User's last name |
| `current_email` | The user's existing email address in Zeenea |
| `new_email` | The new email address to migrate the user to |

Example:

```csv
first_name,last_name,current_email,new_email
Jane,Smith,jane.smith@old-domain.com,jane.smith@new-domain.com
John,Doe,j.doe@old-domain.com,j.doe@new-domain.com
```

## Usage

```bash
python migrate-users.py
```

The script reads `config.json` from its own directory. No CLI arguments are needed.

## What the script does

### Migration phase (per user)

1. Queries the SCIM API (`/api/scim/v2/Users`) to find the existing user by `current_email`.
2. If not found, skips the user.
3. Fetches all items the existing user is a **curator** of (with pagination).
4. Fetches all items the existing user is a **contact** on, across every applicable connection/responsibility type (with pagination).
5. Checks whether a user with `new_email` already exists in Zeenea.
6. If the new user does not exist, creates them via SCIM (name copied from the existing user).
7. Adds the new user as **curator** to all the same items.
8. Assigns the new user as **contact** to all the same connected items, grouped by connection type.
9. Tracks the new user's group memberships for batch group assignment.

### After all users

- Sends PATCH requests to `/api/scim/v2/Groups` to add new users to their groups.
- **Super Admin group**: cannot be updated via the API. Users needing Super Admin access are written to `super_admin_users.json` for manual action.

### Validation phase (per user)

Re-queries both old and new users and compares:
- Group memberships (excluding Super Admin)
- Curated items
- Connected items per connection type (excluding types containing `$`)

Results are written to `migration_validation_report.json`.

## Output files

| File | Description |
|---|---|
| `migration_validation_report.json` | Pass/fail validation results for every migrated user, with details of any discrepancies. |
| `super_admin_users.json` | New users that need to be **manually added** to the Super Admin group in the Zeenea UI. |

## APIs used

| API | Endpoint | Purpose |
|---|---|---|
| SCIM | `GET /api/scim/v2/Users?filter=userName eq "..."` | Look up users by email |
| SCIM | `POST /api/scim/v2/Users` | Create new user |
| SCIM | `PATCH /api/scim/v2/Groups/{id}` | Add user to a group |
| GraphQL | `POST /api/catalog/graphql` | Fetch curated items, connected items; update curators and contacts |

## Notes

- Connection types containing `$` (e.g. `$z_owner`) are system-generated and are **not** migrated or validated.
- The script uses only the Python standard library (`csv`, `json`, `urllib`).
- Pagination is handled automatically for curated items and connected items.
- Running the script is safe to retry: if the new user already exists, it skips creation and proceeds with assignment.