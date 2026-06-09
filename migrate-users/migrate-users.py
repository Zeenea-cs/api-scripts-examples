import csv
import json
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
import urllib.parse
import urllib.request
import os

# Load configuration from config.json
def load_config(config_file: str = "config.json") -> Dict[str, Any]:
    """
    Load configuration from a JSON file.
    
    Args:
        config_file (str): Path to the configuration file (relative to script directory)
    
    Returns:
        Dict: Configuration dictionary with keys: zeenea_url, api_key, csv_path, responsibilities
    """
    try:
        # Get the directory where this script is located
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(script_dir, config_file)
        
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Configuration file not found at {config_path}")
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # Validate required keys
        required_keys = ['zeenea_url', 'api_key', 'csv_path']
        for key in required_keys:
            if key not in config:
                raise ValueError(f"Missing required configuration key: {key}")

        # Validate Zeenea URL format
        zeenea_url = config['zeenea_url']
        if not zeenea_url.startswith('https://'):
            raise ValueError("Zeenea URL must use HTTPS protocol")
        if not zeenea_url.rstrip('/').endswith('.zeenea.app'):
            raise ValueError("Zeenea URL must end with '.zeenea.app'")

        # Set default responsibilities if not provided
        if 'responsibilities' not in config:
            config['responsibilities'] = []

        return config
    
    except FileNotFoundError as e:
        print(f"x- Error: {e}")
        exit(1)
    except json.JSONDecodeError as e:
        print(f"x- Error: Invalid JSON in configuration file - {e}")
        exit(1)
    except ValueError as e:
        print(f"x- Error: {e}")
        exit(1)
    except Exception as e:
        print(f"x- Error loading configuration: {e}")
        exit(1)


# Load config at module level
CONFIG = load_config()
ZEENEA_URL = CONFIG['zeenea_url']
API_KEY = CONFIG['api_key']
CSV_PATH = CONFIG['csv_path']
RESPONSIBILITIES = CONFIG.get('responsibilities', [])

# Data structures to capture the SCIM API response
@dataclass
class Email:
    """Represents an email entry in SCIM User resource."""
    value: str


@dataclass
class Name:
    """Represents the name object in SCIM User resource."""
    givenName: str
    familyName: str


@dataclass
class Group:
    """Represents a group membership in SCIM User resource."""
    value: str
    display: str


@dataclass
class SCIMUser:
    """Represents a SCIM User resource."""
    id: str
    userName: str
    name: Name
    active: bool
    emails: List[Email]
    groups: List[Group]
    schemas: List[str]


@dataclass
class SCIMListResponse:
    """Represents the SCIM ListResponse for Users query."""
    schemas: List[str]
    totalResults: int
    itemsPerPage: int
    startIndex: int
    Resources: List[SCIMUser]


def query_user_by_email(zeenea_instance: str, api_key: str, scim_api_path: str, user_email: str) -> Optional[SCIMListResponse]:
    """
    Query the Zeenea SCIM API to find a user by email address.
    
    Args:
        zeenea_instance (str): The base URL of the Zeenea instance (e.g., "https://customer-services.preprod.zeenea.app")
        api_key (str): The JWT API key for authentication
        scim_api_path (str): The SCIM API path (e.g., "/api/scim/v2/Users")
        user_email (str): The email address to search for
    
    Returns:
        Optional[SCIMListResponse]: Parsed SCIM response or None if an error occurs
    """
    try:
        # Build the filter parameter with proper URL encoding
        filter_value = f'userName eq "{user_email}"'
        filter_param = urllib.parse.urlencode({'filter': filter_value})
        
        # Construct the full URL
        url = f"{zeenea_instance}{scim_api_path}?{filter_param}"
        
        # Create the request with proper headers
        request = urllib.request.Request(url)
        request.add_header('Authorization', f'Bearer {api_key}')
        request.add_header('Content-Type', 'application/scim+json')
        
        # Execute the request
        with urllib.request.urlopen(request) as response:
            response_data = json.loads(response.read().decode('utf-8'))
        
        # Parse the response into our data structure
        scim_response = _parse_scim_response(response_data)
        return scim_response
        
    except urllib.error.HTTPError as e:
        print(f"Error: HTTP {e.code} - {e.reason}")
        print(f"Details: {e.read().decode('utf-8')}")
        return None
    except urllib.error.URLError as e:
        print(f"Error: Unable to reach the API - {e.reason}")
        return None
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON response - {e}")
        return None
    except Exception as e:
        print(f"Error querying SCIM API: {e}")
        return None


def _parse_scim_response(response_data: Dict[str, Any]) -> SCIMListResponse:
    """
    Parse raw API response data into structured SCIM objects.
    
    Args:
        response_data (Dict): Raw response data from the API
    
    Returns:
        SCIMListResponse: Structured SCIM response object
    """
    resources = []
    
    for resource in response_data.get('Resources', []):
        # Parse name object
        name_data = resource.get('name', {})
        name = Name(
            givenName=name_data.get('givenName', ''),
            familyName=name_data.get('familyName', '')
        )
        
        # Parse emails list
        emails = []
        for email_entry in resource.get('emails', []):
            emails.append(Email(value=email_entry.get('value', '')))
        
        # Parse groups list
        groups = []
        for group_entry in resource.get('groups', []):
            groups.append(Group(
                value=group_entry.get('value', ''),
                display=group_entry.get('display', '')
            ))
        
        # Create SCIMUser object
        user = SCIMUser(
            id=resource.get('id', ''),
            userName=resource.get('userName', ''),
            name=name,
            active=resource.get('active', False),
            emails=emails,
            groups=groups,
            schemas=resource.get('schemas', [])
        )
        resources.append(user)
    
    # Create the list response
    scim_list_response = SCIMListResponse(
        schemas=response_data.get('schemas', []),
        totalResults=response_data.get('totalResults', 0),
        itemsPerPage=response_data.get('itemsPerPage', 0),
        startIndex=response_data.get('startIndex', 1),
        Resources=resources
    )
    
    return scim_list_response


def read_users_from_csv(csv_file_path):
    """
    Read users from a CSV file and iterate over them.

    Expected CSV columns:
    - Vorname(n): First name
    - Nachname(n): Last name
    - E-Mail-Adresse alt: Old email address
    - E-Mail-Adresse neu ab 01.01.2026: New email address (valid from 01.01.2026)

    Args:
        csv_file_path (str): Path to the CSV file
    
    Yields:
        dict: User data with keys: firstName, lastName, currentEmail, newEmail
    """
    try:
        with open(csv_file_path, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
        
            for row in reader:
                user = {
                    'firstName': row['first_name'].strip(),
                    'lastName': row['last_name'].strip(),
                    'currentEmail': row['current_email'].strip(),
                    'newEmail': row['new_email'].strip()
                }
                yield user
            
    except FileNotFoundError:
        print(f"Error: CSV file not found at {csv_file_path}")
    except KeyError as e:
        print(f"Error: Missing expected column {e}")
    except Exception as e:
        print(f"Error reading CSV file: {e}")


def main():
    """
    Main execution function.
    """
    zeenea_instance_url = ZEENEA_URL
    api_key = API_KEY
    csv_path = CSV_PATH
    path_scim_api_users = "/api/scim/v2/Users"
    path_scim_api_groups = "/api/scim/v2/Groups"
    path_catalog_graphql_api = "/api/catalog/graphql"

    # Dictionary to track groups and their users
    # Structure: {group_id: {display_name: str, user_ids: [], users_with_emails: []}}
    groups_and_users = {}

    # Retrieve connection types once for the first user
    available_connection_types = None

    # Filter RESPONSIBILITIES to remove items with '$' and use as available_connection_types if populated
    if RESPONSIBILITIES:
        available_connection_types = [resp for resp in RESPONSIBILITIES if '$' not in resp]
        if available_connection_types:
            print(f"v-  Using {len(available_connection_types)} responsibilities from RESPONSIBILITIES list:")
            for resp_type in sorted(available_connection_types):
                print(f"    - {resp_type}")
        else:
            print("⚠ RESPONSIBILITIES list contains only items with '$', will retrieve from API on first user")
            available_connection_types = None
    else:
        print("i-  RESPONSIBILITIES list is empty, will retrieve all connection types from API on first user")

    for idx, user in enumerate(read_users_from_csv(csv_path)):
        print(f"Name: {user['firstName']} {user['lastName']}")
        print(f"Current Email: {user['currentEmail']}")
        print(f"New Email: {user['newEmail']}")

        # Query the SCIM API to find the existing user
        scim_response = query_user_by_email(zeenea_instance_url, api_key, path_scim_api_users, user['currentEmail'])

        if scim_response and scim_response.totalResults > 0:
            existing_user = scim_response.Resources[0]
            print(f"  Found in Zeenea: ID={existing_user.id}")
            print(f"  Groups: {[g.display for g in existing_user.groups]}")

            # Retrieve available connection types on first user only (if not already set from RESPONSIBILITIES)
            if available_connection_types is None and idx == 0:
                print(f"\n  Retrieving available connection types...")
                available_connection_types = get_available_connection_types(
                    zeenea_instance_url,
                    api_key,
                    path_catalog_graphql_api,
                    user['currentEmail']
                )

            # Track the groups this user belongs to
            for group in existing_user.groups:
                if group.value not in groups_and_users:
                    groups_and_users[group.value] = {
                        'display_name': group.display,
                        'user_ids': [],
                        'users_with_emails': []
                    }

            # Fetch all items the user is a curator for
            print(f"  Fetching curated items for {user['currentEmail']}...")
            curated_items = fetch_user_curated_items(
                zeenea_instance_url,
                api_key,
                path_catalog_graphql_api,
                user['currentEmail']
            )

            connected_items = None
            if curated_items is not None:
                print(f"  Total curated items: {len(curated_items)}")
                for item in curated_items:
                    print(f"    - [{item['type']}] {item['name']} (ID: {item['id']})")

                # Fetch all items connected via any connection type
                if available_connection_types:
                    print(f"  Fetching all connected items across {len(available_connection_types)} connection types...")
                    connected_items = fetch_user_connected_items(
                        zeenea_instance_url,
                        api_key,
                        path_catalog_graphql_api,
                        user['currentEmail'],
                        available_connection_types
                    )

                    if connected_items is not None:
                        total_connected = sum(len(items) for items in connected_items.values())
                        print(f"  Total connected items across all types: {total_connected}")
                        for conn_type, items in connected_items.items():
                            if items:
                                print(f"    {conn_type}: {len(items)} items")

                # Check if the new email address has already been created via SCIM API
                print(f"  Checking if new email already exists in SCIM...")
                new_email_response = query_user_by_email(zeenea_instance_url, api_key, path_scim_api_users,
                                                         user['newEmail'])

                if new_email_response and new_email_response.totalResults > 0:
                    # New email already exists, use that user
                    new_user = new_email_response.Resources[0]
                    print(f"  Found existing user with new email: ID={new_user.id}")
                else:
                    # Create a new user with the new email address
                    new_user = create_user(zeenea_instance_url, api_key, path_scim_api_users, existing_user,
                                           user['newEmail'])

                if new_user:
                    print(f"  Successfully created new user: ID={new_user.id}")
                    print(f"  New Email: {new_user.userName}")

                    # Track the new user in the same groups as the existing user
                    for group in existing_user.groups:
                        groups_and_users[group.value]['user_ids'].append(new_user.id)
                        groups_and_users[group.value]['users_with_emails'].append({
                            'user_id': new_user.id,
                            'email': new_user.userName
                        })

                    # Assign Curated items after User Creation
                    if new_user and curated_items:
                        print(f"  Adding new user as curator to {len(curated_items)} item(s)...")
                        if add_new_user_as_curator_to_items(
                                zeenea_instance_url,
                                api_key,
                                path_catalog_graphql_api,
                                new_user.userName,
                                curated_items
                        ):
                            print(f"  v-  Successfully added new user as curator")
                        else:
                            print(f"  ⚠ Some items failed to update - review logs above")

                    # Assign connected items to the new user after User Creation and curations
                    if new_user and connected_items:
                        print(f"  Assigning contact to {len(connected_items)} connection type(s)...")
                        assigned_contact = assign_contact_with_connections(
                            zeenea_instance_url,
                            api_key,
                            path_catalog_graphql_api,
                            new_user.userName,
                            connected_items
                        )

                        if assigned_contact:
                            print(f"  v-  Successfully assigned contact connections")
                        else:
                            print(f"  x- Failed to assign contact connections")
                else:
                    print(f"  i-  No connected items to assign")
            else:
                print(f"  Failed to fetch curated items for user {user['currentEmail']}")
        else:
            print(f"  User not found in Zeenea")

        print("-" * 50)

    # After all users have been processed, add them to their groups
    print("\n" + "=" * 50)
    print("ADDING USERS TO GROUPS")
    print("=" * 50)

    add_users_to_groups(zeenea_instance_url, api_key, path_scim_api_groups, groups_and_users)

    print("\n" + "=" * 70)
    print("VALIDATION: Comparing new users with existing users")
    print("=" * 70 + "\n")

    validation_results = []

    for idx, user in enumerate(read_users_from_csv(csv_path)):
        print(f"\nValidating user {idx + 1}: {user['firstName']} {user['lastName']}")
        print(f"  Current Email: {user['currentEmail']}")
        print(f"  New Email: {user['newEmail']}")

        # Query the existing user
        existing_scim_response = query_user_by_email(zeenea_instance_url, api_key, path_scim_api_users,
                                                     user['currentEmail'])
        if not existing_scim_response or existing_scim_response.totalResults == 0:
            print(f"  x- Existing user not found")
            continue

        existing_user = existing_scim_response.Resources[0]

        # Query the new user
        new_scim_response = query_user_by_email(zeenea_instance_url, api_key, path_scim_api_users, user['newEmail'])
        if not new_scim_response or new_scim_response.totalResults == 0:
            print(f"  x- New user not found")
            continue

        new_user = new_scim_response.Resources[0]

        # Fetch curated items for both users
        print(f"  Fetching curated items for existing user...")
        existing_curated_items = fetch_user_curated_items(zeenea_instance_url, api_key, path_catalog_graphql_api,
                                                          user['currentEmail'])

        print(f"  Fetching curated items for new user...")
        new_curated_items = fetch_user_curated_items(zeenea_instance_url, api_key, path_catalog_graphql_api,
                                                     user['newEmail'])

        # Fetch connected items for both users
        if available_connection_types:
            print(f"  Fetching connected items for existing user...")
            existing_connected_items = fetch_user_connected_items(zeenea_instance_url, api_key,
                                                                  path_catalog_graphql_api, user['currentEmail'],
                                                                  available_connection_types)

            print(f"  Fetching connected items for new user...")
            new_connected_items = fetch_user_connected_items(zeenea_instance_url, api_key, path_catalog_graphql_api,
                                                             user['newEmail'], available_connection_types)
        else:
            existing_connected_items = {}
            new_connected_items = {}

        # Perform validation
        validation_result = validate_user_migration(
            zeenea_instance_url,
            api_key,
            path_scim_api_users,
            path_catalog_graphql_api,
            existing_user,
            new_user,
            existing_curated_items or [],
            new_curated_items or [],
            existing_connected_items or {},
            new_connected_items or {},
            available_connection_types
        )

        validation_results.append(validation_result)

        # Print validation status
        if validation_result['overall_status'] == 'PASS':
            print(f"  v-  VALIDATION PASSED")
        else:
            print(f"  x- VALIDATION FAILED")

        print("-" * 70)

    # Write validation report to file
    import os
    script_dir = os.path.dirname(os.path.abspath(__file__))
    validation_report_file = os.path.join(script_dir, 'migration_validation_report.json')

    write_validation_report(validation_results, validation_report_file)

    print("\n" + "=" * 70)
    print("MIGRATION COMPLETE")
    print("=" * 70)


def add_new_user_as_curator_to_items(zeenea_instance: str, api_key: str, graphql_api_path: str,
                                     new_user_email: str, curated_items: List[Dict[str, Any]]) -> bool:
    """
    Associate a newly created user with all items they are a curator for by updating each item
    using the GraphQL updateItem mutation to add the user's new email address to the curators connection.

    Args:
        zeenea_instance (str): The base URL of the Zeenea instance
        api_key (str): The X-API-SECRET key for authentication
        graphql_api_path (str): The GraphQL API path (e.g., "/api/catalog/graphql")
        new_user_email (str): The email address of the newly created user
        curated_items (List[Dict]): List of items the user is a curator for
                                     Structure: [{'id': '...', 'key': '...', 'name': '...', 'type': '...'}, ...]

    Returns:
        bool: True if all items were successfully updated, False if any failed
    """
    try:
        if not curated_items:
            print(f"    i-  No curated items to associate with {new_user_email}")
            return True

        success = True
        items_updated = 0

        # GraphQL mutation query
        graphql_query = """
        mutation update_item_conn($input: UpdateItemInput!) {
          updateItem(input: $input) {
            item {
              key,
              name,
              type
            }
          }
        }
        """

        for item in curated_items:
            try:
                item_ref = item.get('id') or item.get('key')
                item_name = item.get('name', 'Unknown')

                if not item_ref:
                    print(f"    x- Skipping item (no id or key): {item_name}")
                    success = False
                    continue

                # Prepare the input payload
                mutation_input = {
                    "ref": item_ref,
                    "updates": {
                        "connections": [
                            {
                                "command": "MERGE",
                                "connectionRef": "curators",
                                "itemRefs": new_user_email
                            }
                        ]
                    }
                }

                # Prepare the variables
                variables = {
                    "input": mutation_input
                }

                # Construct the full URL
                url = f"{zeenea_instance}{graphql_api_path}"

                # Prepare the GraphQL payload
                payload = {
                    "query": graphql_query,
                    "variables": variables
                }

                # Convert payload to JSON
                json_payload = json.dumps(payload).encode('utf-8')

                # Create the request
                request = urllib.request.Request(url, data=json_payload, method='POST')
                request.add_header('X-API-SECRET', api_key)
                request.add_header('Content-Type', 'application/json')

                # Execute the request
                with urllib.request.urlopen(request) as response:
                    response_data = json.loads(response.read().decode('utf-8'))

                # Check for GraphQL errors
                if 'errors' in response_data and len(response_data['errors']) > 0:
                    error_messages = [err.get('message', 'Unknown error') for err in response_data['errors']]
                    print(f"    x- Error updating item '{item_name}': {error_messages[0]}")
                    success = False
                    continue

                # Extract the updated item data
                updated_item = response_data.get('data', {}).get('updateItem', {}).get('item')

                if updated_item:
                    print(f"    v-  Added curator to item [{updated_item.get('type')}] {updated_item.get('name')}")
                    items_updated += 1
                else:
                    print(f"    x- No item data in response for '{item_name}'")
                    success = False

            except urllib.error.HTTPError as e:
                error_body = e.read().decode('utf-8')
                print(f"    x- HTTP Error {e.code} updating item '{item_name}': {e.reason}")
                success = False
            except urllib.error.URLError as e:
                print(f"    x- Unable to reach the API for item '{item_name}': {e.reason}")
                success = False
            except json.JSONDecodeError as e:
                print(f"    x- Invalid JSON response for item '{item_name}': {e}")
                success = False
            except Exception as e:
                print(f"    x- Error updating item '{item_name}': {e}")
                success = False

        if success and items_updated > 0:
            print(f"    v-  Successfully added {new_user_email} as curator to {items_updated}/{len(curated_items)} item(s)")
        elif items_updated > 0:
            print(f"    ⚠ Added curator to {items_updated}/{len(curated_items)} item(s) with some failures")

        return success

    except Exception as e:
        print(f"    x- Error in add_new_user_as_curator_to_items: {e}")
        return False


def create_user(zeenea_instance: str, api_key: str, scim_api_path: str, existing_user: SCIMUser, new_email: str) -> \
Optional[SCIMUser]:
    """
    Create a new user in the SCIM API using details from an existing user.

    The new user will have:
    - firstName and lastName from the existing user
    - New email address as the userName
    - Groups are NOT included at creation time (they will be added separately via PATCH)

    Args:
        zeenea_instance (str): The base URL of the Zeenea instance
        api_key (str): The JWT API key for authentication
        scim_api_path (str): The SCIM API path (e.g., "/api/scim/v2/Users")
        existing_user (SCIMUser): The existing user to copy details from
        new_email (str): The new email address for the created user

    Returns:
        Optional[SCIMUser]: The created user object or None if creation fails
    """
    try:
        # Prepare the user payload for SCIM creation (without groups)
        user_payload = {
            "schemas": [
                "urn:ietf:params:scim:schemas:core:2.0:User"
            ],
            "userName": new_email,
            "name": {
                "givenName": existing_user.name.givenName,
                "familyName": existing_user.name.familyName
            }
        }

        # Construct the full URL
        url = f"{zeenea_instance}{scim_api_path}"

        # Convert payload to JSON
        json_payload = json.dumps(user_payload).encode('utf-8')

        # Create the request
        request = urllib.request.Request(url, data=json_payload, method='POST')
        request.add_header('Authorization', f'Bearer {api_key}')
        request.add_header('Content-Type', 'application/scim+json')

        # Execute the request
        with urllib.request.urlopen(request) as response:
            response_data = json.loads(response.read().decode('utf-8'))

        # Parse the response into a SCIMUser object
        created_user = _parse_single_scim_user(response_data)
        return created_user

    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        print(f"    Error: HTTP {e.code} - {e.reason}")
        print(f"    Details: {error_body}")
        return None
    except urllib.error.URLError as e:
        print(f"    Error: Unable to reach the API - {e.reason}")
        return None
    except json.JSONDecodeError as e:
        print(f"    Error: Invalid JSON response - {e}")
        return None
    except Exception as e:
        print(f"    Error creating SCIM user: {e}")
        return None


def _parse_single_scim_user(resource: Dict[str, Any]) -> SCIMUser:
    """
    Parse a single SCIM user resource into a SCIMUser object.
    
    Args:
        resource (Dict): Raw resource data from the API
    
    Returns:
        SCIMUser: Structured SCIM user object
    """
    # Parse name object
    name_data = resource.get('name', {})
    name = Name(
        givenName=name_data.get('givenName', ''),
        familyName=name_data.get('familyName', '')
    )
    
    # Parse emails list
    emails = []
    for email_entry in resource.get('emails', []):
        emails.append(Email(value=email_entry.get('value', '')))
    
    # Parse groups list
    groups = []
    for group_entry in resource.get('groups', []):
        groups.append(Group(
            value=group_entry.get('value', ''),
            display=group_entry.get('display', '')
        ))
    
    # Create SCIMUser object
    user = SCIMUser(
        id=resource.get('id', ''),
        userName=resource.get('userName', ''),
        name=name,
        active=resource.get('active', False),
        emails=emails,
        groups=groups,
        schemas=resource.get('schemas', [])
    )
    
    return user

def fetch_user_curated_items(zeenea_instance: str, api_key: str, graphql_api_path: str, user_email: str) -> Optional[List[Dict[str, Any]]]:
    """
    Fetch a complete list of items that a user is a curator for, handling pagination.

    Args:
        zeenea_instance (str): The base URL of the Zeenea instance
        api_key (str): The JWT API key for authentication
        graphql_api_path (str): The GraphQL API path (e.g., "/api/catalog/graphql")
        user_email (str): The current email address of the user (used as ItemReference)

    Returns:
        Optional[List[Dict]]: Complete list of curated items or None if an error occurs
    """
    try:
        # GraphQL query for fetching curated items with pagination support
        graphql_query = """
        query ownership($ref: ItemReference!) {
          item(ref: $ref) {
            id
            type
            key
            email: property(ref: "email")
            curator: connection(ref: "curator", first: 20, after: "{{start_from}}") {
              nodes {
                id
                key
                name
                type
              }
              pageInfo {
                startCursor
                hasNextPage
                hasPreviousPage
                endCursor
              }
              totalCount
            }
          }
        }
        """
        
        all_curated_items = []
        start_from = "*"
        has_next_page = True
        page_count = 0
        
        while has_next_page:
            page_count += 1
            
            # Replace the placeholder with the actual cursor value
            query_with_cursor = graphql_query.replace("{{start_from}}", start_from)
            
            # Prepare the variables
            variables = {
                "ref": user_email
            }
            
            # Construct the full URL
            url = f"{zeenea_instance}{graphql_api_path}"
            
            # Prepare the GraphQL payload
            payload = {
                "query": query_with_cursor,
                "variables": variables
            }
            
            # Convert payload to JSON
            json_payload = json.dumps(payload).encode('utf-8')
            
            # Create the request
            request = urllib.request.Request(url, data=json_payload, method='POST')
            request.add_header('X-API-SECRET', api_key)
            request.add_header('Content-Type', 'application/json')
            
            # Execute the request
            with urllib.request.urlopen(request) as response:
                response_data = json.loads(response.read().decode('utf-8'))
            
            # Check for GraphQL errors
            if 'errors' in response_data:
                print(f"    GraphQL Error: {response_data['errors']}")
                return None
            
            # Extract the data
            item_data = response_data.get('data', {}).get('item', {})
            curator_data = item_data.get('curator', {})
            nodes = curator_data.get('nodes', [])
            page_info = curator_data.get('pageInfo', {})
            
            # Add nodes to the complete list
            all_curated_items.extend(nodes)
            
            # Check if there are more pages
            has_next_page = page_info.get('hasNextPage', False)
            
            if has_next_page:
                start_from = page_info.get('endCursor', '')
                print(f"    Page {page_count}: Fetched {len(nodes)} items, moving to next page (cursor: {start_from})")
            else:
                print(f"    Page {page_count}: Fetched {len(nodes)} items. Total items curated: {len(all_curated_items)}")
        
        return all_curated_items
    
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        print(f"    Error: HTTP {e.code} - {e.reason}")
        print(f"    Details: {error_body}")
        return None
    except urllib.error.URLError as e:
        print(f"    Error: Unable to reach the API - {e.reason}")
        return None
    except json.JSONDecodeError as e:
        print(f"    Error: Invalid JSON response - {e}")
        return None
    except Exception as e:
        print(f"    Error fetching curated items: {e}")
        return None


def add_users_to_groups(zeenea_instance: str, api_key: str, scim_groups_api_path: str,
                        groups_and_users: Dict[str, Dict]) -> None:
    """
    Add users to their respective groups via PATCH requests.

    Note: The Super Admin group cannot be updated via the API and will be written to a file instead.

    Args:
        zeenea_instance (str): The base URL of the Zeenea instance
        api_key (str): The JWT API key for authentication
        scim_groups_api_path (str): The SCIM Groups API path (e.g., "/api/scim/v2/Groups")
        groups_and_users (Dict): Dictionary mapping group_id to group data with users
    """
    import os

    # Get the directory where this script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    super_admin_output_file = os.path.join(script_dir, 'super_admin_users.json')

    for group_id, group_data in groups_and_users.items():
        display_name = group_data.get('display_name', 'Unknown Group')
        user_ids = group_data.get('user_ids', [])
        users_with_emails = group_data.get('users_with_emails', [])

        if not user_ids:
            print(f"  Skipping group '{display_name}' (ID: {group_id}) - no users to add")
            continue

        # Check if this is the Super Admin group
        if display_name.lower() == 'super admin' or 'super admin' in display_name.lower():
            print(f"\n  ⚠️  Super Admin group detected (ID: {group_id}) - Cannot be updated via API")
            print(f"    Writing {len(user_ids)} user(s) to file: {super_admin_output_file}")

            try:
                # Prepare the Super Admin users data
                super_admin_data = {
                    "group_id": group_id,
                    "group_name": display_name,
                    "user_count": len(user_ids),
                    "users": users_with_emails,
                    "note": "These users need to be manually added to the Super Admin group in the Zeenea UI"
                }

                # Write to file
                with open(super_admin_output_file, 'w', encoding='utf-8') as f:
                    json.dump(super_admin_data, f, indent=2, ensure_ascii=False)

                print(f"    v-  Super Admin users written to file successfully")
            except Exception as e:
                print(f"    x- Error writing Super Admin users to file: {e}")

            continue

        print(f"\n  Adding {len(user_ids)} user(s) to group '{display_name}' (ID: {group_id})")

        try:
            # Construct the full URL
            url = f"{zeenea_instance}{scim_groups_api_path}/{group_id}"

            # Prepare the PATCH payload with all users
            operations = []
            for user_id in user_ids:
                operations.append({
                    "op": "add",
                    "path": "members",
                    "value": [{
                        "value": user_id
                    }]
                })

            payload = {
                "schemas": [
                    "urn:ietf:params:scim:api:messages:2.0:PatchOp"
                ],
                "Operations": operations
            }

            # Convert payload to JSON
            json_payload = json.dumps(payload).encode('utf-8')

            # Create the request
            request = urllib.request.Request(url, data=json_payload, method='PATCH')
            request.add_header('Authorization', f'Bearer {api_key}')
            request.add_header('Content-Type', 'application/scim+json')

            # Execute the request
            with urllib.request.urlopen(request) as response:
                response_data = json.loads(response.read().decode('utf-8'))

            print(f"    v-  Successfully added {len(user_ids)} user(s) to '{display_name}'")

        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8')
            print(f"    x- Error: HTTP {e.code} - {e.reason}")
            print(f"      Details: {error_body}")
        except urllib.error.URLError as e:
            print(f"    x- Error: Unable to reach the API - {e.reason}")
        except json.JSONDecodeError as e:
            print(f"    x- Error: Invalid JSON response - {e}")
        except Exception as e:
            print(f"    x- Error adding users to group: {e}")


def get_available_connection_types(zeenea_instance: str, api_key: str, graphql_api_path: str, user_email: str) -> Optional[List[str]]:
    """
    Retrieve a list of available connection types for the Zeenea instance.

    This is done by querying a user with a wildcard connection reference ('*'),
    which intentionally fails but returns the list of valid connection types in the error response.
    
    Args:
        zeenea_instance (str): The base URL of the Zeenea instance
        api_key (str): The X-API-SECRET key for authentication
        graphql_api_path (str): The GraphQL API path (e.g., "/api/catalog/graphql")
        user_email (str): The email address of the first user to query
    
    Returns:
        Optional[List[str]]: List of available connection types or None if retrieval fails
    """
    try:
        # GraphQL query to retrieve available connection types
        graphql_query = """
        query responsibilities($ref: ItemReference!) {
          item(ref: $ref) {
            id
            email: property(ref: "email")
            responsibilities: connection(ref: "*", first: 5, after: "") {
              nodes {
                id
              }
            }
          }
        }
        """
        
        # Prepare the variables
        variables = {
            "ref": user_email
        }
        
        # Construct the full URL
        url = f"{zeenea_instance}{graphql_api_path}"
        
        # Prepare the GraphQL payload
        payload = {
            "query": graphql_query,
            "variables": variables
        }
        
        # Convert payload to JSON
        json_payload = json.dumps(payload).encode('utf-8')
        
        # Create the request
        request = urllib.request.Request(url, data=json_payload, method='POST')
        request.add_header('X-API-SECRET', api_key)
        request.add_header('Content-Type', 'application/json')
        
        # Execute the request
        with urllib.request.urlopen(request) as response:
            response_data = json.loads(response.read().decode('utf-8'))
        
        # Extract available connection types from the error response
        if 'errors' in response_data and len(response_data['errors']) > 0:
            error = response_data['errors'][0]
            extensions = error.get('extensions', {})
            
            if extensions.get('code') == 'CONNECTION_REFERENCE_NOT_FOUND':
                available_values = extensions.get('availableValues', [])
                
                if available_values:
                    print(f"\nv-  Retrieved {len(available_values)} available connection types:")
                    for conn_type in sorted(available_values):
                        print(f"    - {conn_type}")
                    
                    return available_values
                else:
                    print("x- No available connection types found in error response")
                    return None
        
        print("x- Unexpected response format - no error with CONNECTION_REFERENCE_NOT_FOUND")
        return None
    
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        print(f"x- Error: HTTP {e.code} - {e.reason}")
        print(f"  Details: {error_body}")
        return None
    except urllib.error.URLError as e:
        print(f"x- Error: Unable to reach the API - {e.reason}")
        return None
    except json.JSONDecodeError as e:
        print(f"x- Error: Invalid JSON response - {e}")
        return None
    except Exception as e:
        print(f"x- Error retrieving connection types: {e}")
        return None

def fetch_user_connected_items(zeenea_instance: str, api_key: str, graphql_api_path: str, user_email: str, connection_types: List[str]) -> Optional[Dict[str, List[Dict[str, Any]]]]:
    """
    Fetch all items connected to a user across all available connection types.
    
    For each connection type, this method queries the user's connections with pagination support.
    Connection type names are normalized by replacing spaces and hyphens with underscores
    to create valid GraphQL property names.
    
    Args:
        zeenea_instance (str): The base URL of the Zeenea instance
        api_key (str): The X-API-SECRET key for authentication
        graphql_api_path (str): The GraphQL API path (e.g., "/api/catalog/graphql")
        user_email (str): The current email address of the user
        connection_types (List[str]): List of available connection type names
    
    Returns:
        Optional[Dict]: Dictionary mapping connection types to lists of connected items, or None if retrieval fails
    """
    try:
        all_connections = {}
        
        for connection_type in connection_types:
            # Normalize connection type name: replace spaces and hyphens with underscores
            normalized_property_name = connection_type.replace(' ', '_').replace('-', '_')
            
            print(f"    Fetching connection type '{connection_type}'...", end='', flush=True)
            
            # GraphQL query template for this connection type
            graphql_query = f"""
            query connections($ref: ItemReference!, $after: String) {{
              item(ref: $ref) {{
                id
                type
                key
                email: property(ref: "email")
                {normalized_property_name}: connection(ref: "{connection_type}", first: 20, after: $after) {{
                  nodes {{
                    id
                    key
                    name
                    type
                  }}
                  pageInfo {{
                    startCursor
                    hasNextPage
                    hasPreviousPage
                    endCursor
                  }}
                  totalCount
                }}
              }}
            }}
            """
            
            connected_items = []
            has_next_page = True
            start_from = "*"
            
            # Pagination loop for this connection type
            while has_next_page:
                try:
                    # Prepare the variables
                    variables = {
                        "ref": user_email,
                        "after": start_from
                    }
                    
                    # Construct the full URL
                    url = f"{zeenea_instance}{graphql_api_path}"
                    
                    # Prepare the GraphQL payload
                    payload = {
                        "query": graphql_query,
                        "variables": variables
                    }
                    
                    # Convert payload to JSON
                    json_payload = json.dumps(payload).encode('utf-8')
                    
                    # Create the request
                    request = urllib.request.Request(url, data=json_payload, method='POST')
                    request.add_header('X-API-SECRET', api_key)
                    request.add_header('Content-Type', 'application/json')
                    
                    # Execute the request
                    with urllib.request.urlopen(request) as response:
                        response_data = json.loads(response.read().decode('utf-8'))
                    
                    # Check for GraphQL errors
                    if 'errors' in response_data:
                        error_messages = [err.get('message', 'Unknown error') for err in response_data['errors']]
                        # Skip this connection type if there's an error (it may not apply to this item)
                        print(f" x- (skipped - {error_messages[0][:40]}...)")
                        break
                    
                    # Extract the data
                    item_data = response_data.get('data', {}).get('item', {})
                    connection_data = item_data.get(normalized_property_name)
                    
                    if connection_data is None:
                        # This connection type doesn't apply to this item
                        break
                    
                    nodes = connection_data.get('nodes', [])
                    page_info = connection_data.get('pageInfo', {})
                    total_count = connection_data.get('totalCount', 0)
                    
                    # Add nodes to the list
                    connected_items.extend(nodes)
                    
                    # Check if there are more pages
                    has_next_page = page_info.get('hasNextPage', False)
                    
                    if has_next_page:
                        start_from = page_info.get('endCursor', '')
                    else:
                        break
                
                except urllib.error.HTTPError as e:
                    error_body = e.read().decode('utf-8')
                    print(f" x- (HTTP {e.code})")
                    break
                except Exception as e:
                    print(f" x- (Error: {str(e)[:40]}...)")
                    break
            
            # Store the connected items for this connection type if any were found
            if connected_items:
                all_connections[connection_type] = connected_items
                print(f" v-  ({len(connected_items)} items)")
            else:
                # Still track the connection type even if no items were found
                all_connections[connection_type] = []
        
        return all_connections
    
    except Exception as e:
        print(f"    x- Error fetching user connected items: {e}")
        return None


def assign_contact_with_connections(zeenea_instance: str, api_key: str, graphql_api_path: str,
                                    contact_email: str, connected_items: Dict[str, List[Dict[str, Any]]]) -> Optional[Dict[str, Any]]:
    """
    Assign a contact with its connected items using the GraphQL UpdateContact mutation.
    
    The connected items are grouped by connection type and merged into the contact's connections.

    Args:
        zeenea_instance (str): The base URL of the Zeenea instance
        api_key (str): The X-API-SECRET key for authentication
        graphql_api_path (str): The GraphQL API path (e.g., "/api/catalog/graphql")
        contact_email (str): The email address of the contact to update
        connected_items (Dict): Dictionary mapping connection types to lists of connected items
                                Structure: {connection_type: [{'id': '...', 'key': '...', ...}, ...]}

    Returns:
        Optional[Dict]: The updated contact object with id, type, key, name, or None if update fails
    """
    try:
        # If no connected items, skip the update
        if not connected_items:
            print(f"    i-  No connected items to assign to contact {contact_email}")
            return None

        # Build the connections array from connected_items, grouped by connection type
        connections = []
        total_items = 0

        for connection_ref, items in connected_items.items():
            if items:  # Only add if there are items for this connection type
                item_refs = [item.get('id') or item.get('key') for item in items if item.get('id') or item.get('key')]
                if item_refs:
                    connections.append({
                        "command": "MERGE",
                        "connectionRef": connection_ref,
                        "itemRefs": item_refs
                    })
                    total_items += len(item_refs)

        if not connections:
            print(f"    i-  No valid item references found in connected items")
            return None

        # GraphQL mutation query
        graphql_query = """
        mutation UpdateContact($input: UpdateContactInput!) {
          updateContact(input: $input) {
            clientMutationId
            item {
              id
              type
              key
              name
            }
          }
        }
        """

        # Prepare the input payload
        mutation_input = {
            "clientMutationId": f"assign-conn-{contact_email.replace('@', '-').replace('.', '-')}",
            "ref": contact_email,
            "connections": connections
        }

        # Prepare the variables
        variables = {
            "input": mutation_input
        }

        # Construct the full URL
        url = f"{zeenea_instance}{graphql_api_path}"

        # Prepare the GraphQL payload
        payload = {
            "query": graphql_query,
            "variables": variables
        }

        # Convert payload to JSON
        json_payload = json.dumps(payload).encode('utf-8')

        # Create the request
        request = urllib.request.Request(url, data=json_payload, method='POST')
        request.add_header('X-API-SECRET', api_key)
        request.add_header('Content-Type', 'application/json')

        # Execute the request
        with urllib.request.urlopen(request) as response:
            response_data = json.loads(response.read().decode('utf-8'))

        # Check for GraphQL errors
        if 'errors' in response_data and len(response_data['errors']) > 0:
            error_messages = [err.get('message', 'Unknown error') for err in response_data['errors']]
            print(f"    x- GraphQL Error: {error_messages[0]}")
            return None

        # Extract the updated contact data
        updated_contact = response_data.get('data', {}).get('updateContact', {}).get('item')

        if updated_contact:
            print(f"    v-  Successfully assigned contact {contact_email}: {len(connections)} connection type(s) with {total_items} item(s)")
            return updated_contact
        else:
            print(f"    x- No contact data in response")
            return None

    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        print(f"    x- Error: HTTP {e.code} - {e.reason}")
        print(f"      Details: {error_body}")
        return None
    except urllib.error.URLError as e:
        print(f"    x- Error: Unable to reach the API - {e.reason}")
        return None
    except json.JSONDecodeError as e:
        print(f"    x- Error: Invalid JSON response - {e}")
        return None
    except Exception as e:
        print(f"    x- Error assigning contact connections: {e}")
        return None

def validate_user_migration(zeenea_instance: str, api_key: str, scim_api_path: str,
                            graphql_api_path: str, existing_user: SCIMUser, new_user: SCIMUser,
                            existing_curated_items: List[Dict[str, Any]],
                            new_curated_items: List[Dict[str, Any]],
                            existing_connected_items: Dict[str, List[Dict[str, Any]]],
                            new_connected_items: Dict[str, List[Dict[str, Any]]],
                            available_connection_types: Optional[List[str]]) -> Dict[str, Any]:
    """
    Validate that a new user has the same groups, curated items, and connected items as the existing user.

    Excludes:
    - Super Admin group from validation (handled separately)
    - Connection types containing '$' from validation (system-generated types)

    Args:
        zeenea_instance (str): The base URL of the Zeenea instance
        api_key (str): The API key for authentication
        scim_api_path (str): The SCIM API path
        graphql_api_path (str): The GraphQL API path
        existing_user (SCIMUser): The original user
        new_user (SCIMUser): The newly created user
        existing_curated_items (List[Dict]): Items curated by the existing user
        new_curated_items (List[Dict]): Items curated by the new user
        existing_connected_items (Dict): Connected items for the existing user
        new_connected_items (Dict): Connected items for the new user
        available_connection_types (Optional[List[str]]): Available connection types

    Returns:
        Dict: Validation results with any discrepancies found
    """
    validation_result = {
        'existing_user_email': existing_user.userName,
        'new_user_email': new_user.userName,
        'groups_match': False,
        'groups_discrepancies': [],
        'curated_items_match': False,
        'curated_items_discrepancies': [],
        'connected_items_match': False,
        'connected_items_discrepancies': [],
        'overall_status': 'PASS'
    }

    # ========================================================================
    # Validate Groups (excluding Super Admin)
    # ========================================================================
    # Filter out Super Admin group from both users
    existing_filtered_groups = [g for g in existing_user.groups if 'super admin' not in g.display.lower()]
    new_filtered_groups = [g for g in new_user.groups if 'super admin' not in g.display.lower()]

    existing_group_ids = set(g.value for g in existing_filtered_groups)
    new_group_ids = set(g.value for g in new_filtered_groups)

    if existing_group_ids == new_group_ids:
        validation_result['groups_match'] = True
        print(f"  v-  Groups match: {len(existing_group_ids)} group(s)")
    else:
        validation_result['overall_status'] = 'FAIL'
        missing_groups = existing_group_ids - new_group_ids
        extra_groups = new_group_ids - existing_group_ids

        if missing_groups:
            for group_id in missing_groups:
                group_display = next((g.display for g in existing_filtered_groups if g.value == group_id), group_id)
                validation_result['groups_discrepancies'].append({
                    'type': 'MISSING',
                    'group_id': group_id,
                    'group_display': group_display
                })
            print(f"  x- Missing {len(missing_groups)} group(s) in new user")

        if extra_groups:
            for group_id in extra_groups:
                group_display = next((g.display for g in new_filtered_groups if g.value == group_id), group_id)
                validation_result['groups_discrepancies'].append({
                    'type': 'EXTRA',
                    'group_id': group_id,
                    'group_display': group_display
                })
            print(f"  x- New user has {len(extra_groups)} extra group(s)")

    # ========================================================================
    # Validate Curated Items
    # ========================================================================
    existing_curated_ids = set(item.get('id') or item.get('key') for item in existing_curated_items)
    new_curated_ids = set(item.get('id') or item.get('key') for item in new_curated_items)

    if existing_curated_ids == new_curated_ids:
        validation_result['curated_items_match'] = True
        print(f"  v-  Curated items match: {len(existing_curated_ids)} item(s)")
    else:
        validation_result['overall_status'] = 'FAIL'
        missing_curated = existing_curated_ids - new_curated_ids
        extra_curated = new_curated_ids - existing_curated_ids

        if missing_curated:
            for item_id in missing_curated:
                item_info = next((item for item in existing_curated_items if item.get('id') == item_id or item.get('key') == item_id), {})
                validation_result['curated_items_discrepancies'].append({
                    'type': 'MISSING',
                    'item_id': item_id,
                    'item_name': item_info.get('name', 'Unknown'),
                    'item_type': item_info.get('type', 'Unknown')
                })
            print(f"  x- Missing {len(missing_curated)} curated item(s) in new user")

        if extra_curated:
            for item_id in extra_curated:
                item_info = next((item for item in new_curated_items if item.get('id') == item_id or item.get('key') == item_id), {})
                validation_result['curated_items_discrepancies'].append({
                    'type': 'EXTRA',
                    'item_id': item_id,
                    'item_name': item_info.get('name', 'Unknown'),
                    'item_type': item_info.get('type', 'Unknown')
                })
            print(f"  x- New user has {len(extra_curated)} extra curated item(s)")

    # ========================================================================
    # Validate Connected Items (excluding connection types with '$')
    # ========================================================================
    existing_conn_summary = {}
    for conn_type, items in existing_connected_items.items():
        # Skip connection types containing '$'
        if '$' not in conn_type:
            existing_conn_summary[conn_type] = set(item.get('id') or item.get('key') for item in items)

    new_conn_summary = {}
    for conn_type, items in new_connected_items.items():
        # Skip connection types containing '$'
        if '$' not in conn_type:
            new_conn_summary[conn_type] = set(item.get('id') or item.get('key') for item in items)

    all_conn_types = set(existing_conn_summary.keys()) | set(new_conn_summary.keys())
    connected_match = True

    for conn_type in all_conn_types:
        existing_items = existing_conn_summary.get(conn_type, set())
        new_items = new_conn_summary.get(conn_type, set())

        if existing_items != new_items:
            connected_match = False
            validation_result['overall_status'] = 'FAIL'
            missing_items = existing_items - new_items
            extra_items = new_items - existing_items

            if missing_items:
                for item_id in missing_items:
                    item_info = next((item for item in existing_connected_items.get(conn_type, []) if item.get('id') == item_id or item.get('key') == item_id), {})
                    validation_result['connected_items_discrepancies'].append({
                        'type': 'MISSING',
                        'connection_type': conn_type,
                        'item_id': item_id,
                        'item_name': item_info.get('name', 'Unknown'),
                        'item_type': item_info.get('type', 'Unknown')
                    })

            if extra_items:
                for item_id in extra_items:
                    item_info = next((item for item in new_connected_items.get(conn_type, []) if item.get('id') == item_id or item.get('key') == item_id), {})
                    validation_result['connected_items_discrepancies'].append({
                        'type': 'EXTRA',
                        'connection_type': conn_type,
                        'item_id': item_id,
                        'item_name': item_info.get('name', 'Unknown'),
                        'item_type': item_info.get('type', 'Unknown')
                    })

            print(f"  x- Connected items mismatch for connection type '{conn_type}'")
        else:
            print(f"  v-  Connected items match for '{conn_type}': {len(existing_items)} item(s)")

    if connected_match:
        validation_result['connected_items_match'] = True

    return validation_result


def write_validation_report(validation_results: List[Dict[str, Any]], output_file_path: str) -> None:
    """
    Write validation results to a JSON file for review.

    Args:
        validation_results (List[Dict]): List of validation results from each user migration
        output_file_path (str): Path where the report file should be written
    """
    try:
        # Summary statistics
        total_users = len(validation_results)
        passed_users = sum(1 for result in validation_results if result['overall_status'] == 'PASS')
        failed_users = total_users - passed_users

        summary = {
            'validation_timestamp': __import__('datetime').datetime.now().isoformat(),
            'total_users_validated': total_users,
            'users_passed': passed_users,
            'users_failed': failed_users,
            'pass_rate': f"{(passed_users / total_users * 100):.1f}%" if total_users > 0 else "0%",
            'validation_details': validation_results
        }

        # Write to file
        with open(output_file_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

        print(f"\nv-  Validation report written to: {output_file_path}")
        print(f"  Total users: {total_users}")
        print(f"  Passed: {passed_users}")
        print(f"  Failed: {failed_users}")
        print(f"  Pass rate: {summary['pass_rate']}")

    except Exception as e:
        print(f"x- Error writing validation report: {e}")

if __name__ == "__main__":
    main()
