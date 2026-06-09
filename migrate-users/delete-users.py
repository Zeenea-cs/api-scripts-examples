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
RESPONSIBILITIES = CONFIG.get('responsibilities', [])
CSV_PATH = CONFIG['csv_path']


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
        zeenea_instance (str): The base URL of the Zeenea instance
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
        print(f"  x- Error: HTTP {e.code} - {e.reason}")
        return None
    except urllib.error.URLError as e:
        print(f"  x- Error: Unable to reach the API - {e.reason}")
        return None
    except json.JSONDecodeError as e:
        print(f"  x- Error: Invalid JSON response - {e}")
        return None
    except Exception as e:
        print(f"  x- Error querying SCIM API: {e}")
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


def read_users_from_csv(csv_file_path: str) -> Optional[List[str]]:
    """
    Read user email addresses from a CSV file.

    Expected CSV columns:
    - email: Email address of the user to delete

    Args:
        csv_file_path (str): Path to the CSV file

    Returns:
        Optional[List[str]]: List of email addresses or None if an error occurs
    """
    try:
        user_emails = []
        with open(csv_file_path, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)

            for row in reader:
                email = row['email'].strip()
                if email:
                    user_emails.append(email)

        return user_emails

    except FileNotFoundError:
        print(f"x- Error: CSV file not found at {csv_file_path}")
        return None
    except KeyError as e:
        print(f"x- Error: Missing expected column {e}")
        return None
    except Exception as e:
        print(f"x- Error reading CSV file: {e}")
        return None


def get_available_connection_types(zeenea_instance: str, api_key: str, graphql_api_path: str, user_email: str) -> Optional[List[str]]:
    """
    Retrieve a list of available connection types for the Zeenea instance.

    This is done by querying a user with a wildcard connection reference ('*'),
    which intentionally fails but returns the list of valid connection types in the error response.

    Args:
        zeenea_instance (str): The base URL of the Zeenea instance
        api_key (str): The X-API-SECRET key for authentication
        graphql_api_path (str): The GraphQL API path
        user_email (str): The email address of a user to query

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
                    print(f"\nv- Retrieved {len(available_values)} available connection types:")
                    for conn_type in sorted(available_values):
                        print(f"    - {conn_type}")

                    return available_values
                else:
                    print("x- No available connection types found in error response")
                    return None

        print("x- Unexpected response format - no error with CONNECTION_REFERENCE_NOT_FOUND")
        return None

    except urllib.error.HTTPError as e:
        print(f"x- Error: HTTP {e.code} - {e.reason}")
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

    Args:
        zeenea_instance (str): The base URL of the Zeenea instance
        api_key (str): The X-API-SECRET key for authentication
        graphql_api_path (str): The GraphQL API path
        user_email (str): The current email address of the user
        connection_types (List[str]): List of available connection type names

    Returns:
        Optional[Dict]: Dictionary mapping connection types to lists of connected items
    """
    try:
        all_connections = {}

        for connection_type in connection_types:
            # Normalize connection type name
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
                        print(f" x- (skipped - {error_messages[0][:40]}...)")
                        break

                    # Extract the data
                    item_data = response_data.get('data', {}).get('item', {})
                    connection_data = item_data.get(normalized_property_name)

                    if connection_data is None:
                        break

                    nodes = connection_data.get('nodes', [])
                    page_info = connection_data.get('pageInfo', {})

                    # Add nodes to the list
                    connected_items.extend(nodes)

                    # Check if there are more pages
                    has_next_page = page_info.get('hasNextPage', False)

                    if has_next_page:
                        start_from = page_info.get('endCursor', '')
                    else:
                        break

                except urllib.error.HTTPError as e:
                    print(f" x- (HTTP {e.code})")
                    break
                except Exception as e:
                    print(f" x- (Error: {str(e)[:40]}...)")
                    break

            # Store the connected items for this connection type
            if connected_items:
                all_connections[connection_type] = connected_items
                print(f" v- ({len(connected_items)} items)")
            else:
                all_connections[connection_type] = []

        return all_connections

    except Exception as e:
        print(f"    x- Error fetching user connected items: {e}")
        return None


def fetch_user_curated_items(zeenea_instance: str, api_key: str, graphql_api_path: str, user_email: str) -> Optional[List[Dict[str, Any]]]:
    """
    Fetch a complete list of items that a user is a curator for, handling pagination.

    Args:
        zeenea_instance (str): The base URL of the Zeenea instance
        api_key (str): The X-API-SECRET key for authentication
        graphql_api_path (str): The GraphQL API path
        user_email (str): The email address of the user

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
                print(f"    x- GraphQL Error: {response_data['errors']}")
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
                print(f"    Page {page_count}: Fetched {len(nodes)} items, moving to next page")
            else:
                print(f"    Page {page_count}: Fetched {len(nodes)} items. Total curated: {len(all_curated_items)}")

        return all_curated_items

    except urllib.error.HTTPError as e:
        print(f"    x- Error: HTTP {e.code} - {e.reason}")
        return None
    except urllib.error.URLError as e:
        print(f"    x- Error: Unable to reach the API - {e.reason}")
        return None
    except json.JSONDecodeError as e:
        print(f"    x- Error: Invalid JSON response - {e}")
        return None
    except Exception as e:
        print(f"    x- Error fetching curated items: {e}")
        return None


def remove_user_from_connected_items(zeenea_instance: str, api_key: str, graphql_api_path: str,
                                     user_email: str, connected_items: Dict[str, List[Dict[str, Any]]]) -> bool:
    """
    Remove a user contact from all their connected items using the GraphQL UpdateContact mutation.

    Args:
        zeenea_instance (str): The base URL of the Zeenea instance
        api_key (str): The X-API-SECRET key for authentication
        graphql_api_path (str): The GraphQL API path
        user_email (str): The email address of the user to remove
        connected_items (Dict): Dictionary mapping connection types to lists of connected items

    Returns:
        bool: True if all items were successfully updated, False if any failed
    """
    try:
        if not connected_items:
            print(f"    ℹ No connected items to remove from {user_email}")
            return True

        success = True

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

        # Build the connections array from connected_items, grouped by connection type
        connections = []
        total_items = 0

        for connection_ref, items in connected_items.items():
            if items:
                item_refs = [item.get('id') or item.get('key') for item in items if item.get('id') or item.get('key')]
                if item_refs:
                    connections.append({
                        "command": "REMOVE",
                        "connectionRef": connection_ref,
                        "itemRefs": item_refs
                    })
                    total_items += len(item_refs)

        if not connections:
            print(f"    ℹ No valid item references found in connected items")
            return True

        try:
            # Prepare the input payload
            mutation_input = {
                "clientMutationId": f"remove-conn-{user_email.replace('@', '-').replace('.', '-')}",
                "ref": user_email,
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
                print(f"    x- Error removing from connected items: {error_messages[0]}")
                return False

            # Extract the updated contact data
            updated_contact = response_data.get('data', {}).get('updateContact', {}).get('item')

            if updated_contact:
                print(f"    v- Removed from {len(connections)} connection type(s) with {total_items} item(s)")
                return True
            else:
                print(f"    x- No contact data in response")
                return False

        except urllib.error.HTTPError as e:
            print(f"    x- HTTP Error {e.code}: {e.reason}")
            return False
        except urllib.error.URLError as e:
            print(f"    x- Unable to reach the API: {e.reason}")
            return False
        except json.JSONDecodeError as e:
            print(f"    x- Invalid JSON response: {e}")
            return False
        except Exception as e:
            print(f"    x- Error removing from connected items: {e}")
            return False

    except Exception as e:
        print(f"    x- Error in remove_user_from_connected_items: {e}")
        return False


def remove_user_from_curated_items(zeenea_instance: str, api_key: str, graphql_api_path: str,
                                   user_email: str, curated_items: List[Dict[str, Any]]) -> bool:
    """
    Remove a user from the curator list of all their curated items.

    Args:
        zeenea_instance (str): The base URL of the Zeenea instance
        api_key (str): The X-API-SECRET key for authentication
        graphql_api_path (str): The GraphQL API path
        user_email (str): The email address of the user to remove
        curated_items (List[Dict]): List of items the user curates

    Returns:
        bool: True if all items were successfully updated, False if any failed
    """
    try:
        if not curated_items:
            print(f"    ℹ No curated items to remove from {user_email}")
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
                                "command": "REMOVE",
                                "connectionRef": "curators",
                                "itemRefs": user_email
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
                    print(f"    x- Error removing from item '{item_name}': {error_messages[0]}")
                    success = False
                    continue

                # Extract the updated item data
                updated_item = response_data.get('data', {}).get('updateItem', {}).get('item')

                if updated_item:
                    print(f"    v- Removed curator from [{updated_item.get('type')}] {updated_item.get('name')}")
                    items_updated += 1
                else:
                    print(f"    x- No item data in response for '{item_name}'")
                    success = False

            except urllib.error.HTTPError as e:
                print(f"    x- HTTP Error {e.code} removing from item '{item_name}': {e.reason}")
                success = False
            except urllib.error.URLError as e:
                print(f"    x- Unable to reach the API for item '{item_name}': {e.reason}")
                success = False
            except json.JSONDecodeError as e:
                print(f"    x- Invalid JSON response for item '{item_name}': {e}")
                success = False
            except Exception as e:
                print(f"    x- Error removing from item '{item_name}': {e}")
                success = False

        if success and items_updated > 0:
            print(f"    v- Removed from {items_updated}/{len(curated_items)} curated item(s)")
        elif items_updated > 0:
            print(f"    !- Removed from {items_updated}/{len(curated_items)} item(s) with some failures")

        return success

    except Exception as e:
        print(f"    x- Error in remove_user_from_curated_items: {e}")
        return False


def delete_user_from_scim(zeenea_instance: str, api_key: str, scim_api_path: str, user_id: str, user_email: str) -> bool:
    """
    Delete a user from the SCIM API.

    Args:
        zeenea_instance (str): The base URL of the Zeenea instance
        api_key (str): The JWT API key for authentication
        scim_api_path (str): The SCIM API path
        user_id (str): The ID of the user to delete
        user_email (str): The email address of the user (for logging)

    Returns:
        bool: True if deletion was successful, False otherwise
    """
    try:
        # Construct the full URL
        url = f"{zeenea_instance}{scim_api_path}/{user_id}"

        # Create the request
        request = urllib.request.Request(url, method='DELETE')
        request.add_header('Authorization', f'Bearer {api_key}')
        request.add_header('Content-Type', 'application/scim+json')

        # Execute the request
        with urllib.request.urlopen(request) as response:
            status_code = response.status

        if status_code in [204, 200]:
            print(f"    v- Successfully deleted user from SCIM: {user_email}")
            return True
        else:
            print(f"    x- Unexpected status code {status_code}")
            return False

    except urllib.error.HTTPError as e:
        if e.code == 404:
            print(f"    x- User not found: {user_email}")
        else:
            print(f"    x- HTTP Error {e.code}: {e.reason}")
        return False
    except urllib.error.URLError as e:
        print(f"    x- Unable to reach the API: {e.reason}")
        return False
    except Exception as e:
        print(f"    x- Error deleting user: {e}")
        return False


def delete_contact(zeenea_instance: str, api_key: str, graphql_api_path: str, user_email: str) -> bool:
    """
    Delete a contact from the system using the GraphQL deleteItem mutation.

    Args:
        zeenea_instance (str): The base URL of the Zeenea instance
        api_key (str): The X-API-SECRET key for authentication
        graphql_api_path (str): The GraphQL API path
        user_email (str): The email address of the contact to delete

    Returns:
        bool: True if deletion was successful, False otherwise
    """
    try:
        # GraphQL mutation query
        graphql_query = """
        mutation DeleteContact($input: DeleteContactInput) {
          deleteContact(input: $input) {
            clientMutationId
          }
        }
        """

        # Prepare the input payload
        mutation_input = {
            "clientMutationId": f"delete-contact-{user_email.replace('@', '-').replace('.', '-')}",
            "ref": user_email
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
            print(f"    x- Error deleting contact: {error_messages[0]}")
            return False

        # Check if the delete was successful
        # The response structure is: {"data": {"deleteContact": {"clientMutationId": "..."}}}
        client_mutation_id = response_data.get('data', {}).get('deleteContact', {}).get('clientMutationId')
        if client_mutation_id:
            print(f"    v- Successfully deleted contact: {user_email}")
            return True
        else:
            print(f"    x- Contact deletion failed: No confirmation received")
            return False

    except urllib.error.HTTPError as e:
        print(f"    x- HTTP Error {e.code}: {e.reason}")
        return False
    except urllib.error.URLError as e:
        print(f"    x- Unable to reach the API: {e.reason}")
        return False
    except json.JSONDecodeError as e:
        print(f"    x- Invalid JSON response: {e}")
        return False
    except Exception as e:
        print(f"    x- Error deleting contact: {e}")
        return False


def main():
    """
    Main execution function.
    """
    zeenea_instance_url = ZEENEA_URL
    api_key = API_KEY
    csv_path = CSV_PATH
    path_scim_api_users = "/api/scim/v2/Users"
    path_catalog_graphql_api = "/api/catalog/graphql"

    print("=" * 70)
    print("USER DELETION SCRIPT")
    print("=" * 70 + "\n")

    # Read users from CSV
    user_emails = read_users_from_csv(csv_path)
    if not user_emails:
        print("x- No users to delete")
        return

    print(f"v- Loaded {len(user_emails)} user(s) to delete\n")

    # Retrieve connection types once before processing
    available_connection_types = None

    # Filter RESPONSIBILITIES to remove items with '$' and use as available_connection_types if populated
    if RESPONSIBILITIES:
        available_connection_types = [resp for resp in RESPONSIBILITIES if '$' not in resp]
        if available_connection_types:
            print(f"v- Using {len(available_connection_types)} responsibilities from RESPONSIBILITIES list:")
            for resp_type in sorted(available_connection_types):
                print(f"    - {resp_type}")
        else:
            print("!- RESPONSIBILITIES list contains only items with '$', will retrieve from API")
            available_connection_types = None
    else:
        print("ℹ RESPONSIBILITIES list is empty, will retrieve all connection types from API on first user")

    deletion_summary = {
        'total_users': len(user_emails),
        'successfully_deleted': 0,
        'failed_deletions': 0,
        'errors': []
    }

    for idx, user_email in enumerate(user_emails):
        print(f"\n{'='*70}")
        print(f"Processing user {idx + 1}/{len(user_emails)}: {user_email}")
        print(f"{'='*70}")

        # Query the SCIM API to find the user
        scim_response = query_user_by_email(zeenea_instance_url, api_key, path_scim_api_users, user_email)

        if not scim_response or scim_response.totalResults == 0:
            print(f"x- User not found in Zeenea")
            deletion_summary['failed_deletions'] += 1
            deletion_summary['errors'].append({
                'email': user_email,
                'error': 'User not found in SCIM'
            })
            user = None
        else:
            user = scim_response.Resources[0]
            print(f"v- Found user: ID={user.id}")

        # Retrieve available connection types on first user if needed
        if available_connection_types is None and idx == 0:
            print(f"\nRetrieving available connection types...")
            available_connection_types = get_available_connection_types(
                zeenea_instance_url,
                api_key,
                path_catalog_graphql_api,
                user_email
            )

        # Fetch curated items
        print(f"\nFetching curated items...")
        curated_items = fetch_user_curated_items(zeenea_instance_url, api_key, path_catalog_graphql_api, user_email)

        if curated_items is not None:
            print(f"v- Found {len(curated_items)} curated item(s)")

            # Remove user from curated items
            if curated_items:
                print(f"\nRemoving user from curated items...")
                if not remove_user_from_curated_items(zeenea_instance_url, api_key, path_catalog_graphql_api, user_email, curated_items):
                    print(f"!- Some curated items failed to update")

        # Fetch connected items
        if user is not None:
            if available_connection_types:
                print(f"\nFetching connected items...")
                connected_items = fetch_user_connected_items(zeenea_instance_url, api_key, path_catalog_graphql_api, user_email, available_connection_types)

                if connected_items is not None:
                    total_connected = sum(len(items) for items in connected_items.values())
                    print(f"v- Found {total_connected} connected item(s)")

                    # Remove user from connected items
                    if total_connected > 0:
                        print(f"\nRemoving user from connected items...")
                        if not remove_user_from_connected_items(zeenea_instance_url, api_key, path_catalog_graphql_api, user_email, connected_items):
                            print(f"!- Some connected items failed to update")

        # Delete user from SCIM
        if user is not None:
            print(f"\nDeleting user from SCIM...")
            if delete_user_from_scim(zeenea_instance_url, api_key, path_scim_api_users, user.id, user_email):
                deletion_summary['successfully_deleted'] += 1
                print(f"\nv- Successfully deleted user: {user_email}")
            else:
                deletion_summary['failed_deletions'] += 1
                deletion_summary['errors'].append({
                    'email': user_email,
                    'error': 'Failed to delete from SCIM'
                })

        # Delete contact
        print(f"\nDeleting contact...")
        if not delete_contact(zeenea_instance_url, api_key, path_catalog_graphql_api, user_email):
            print(f"!- Contact deletion failed - continuing with user deletion")

    # Summary
    print(f"\n{'='*70}")
    print("DELETION SUMMARY")
    print(f"{'='*70}")
    print(f"Total users: {deletion_summary['total_users']}")
    print(f"Successfully deleted: {deletion_summary['successfully_deleted']}")
    print(f"Failed deletions: {deletion_summary['failed_deletions']}")
    print(f"Success rate: {(deletion_summary['successfully_deleted'] / deletion_summary['total_users'] * 100):.1f}%")

    if deletion_summary['errors']:
        print(f"\nErrors:")
        for error in deletion_summary['errors']:
            print(f"  - {error['email']}: {error['error']}")


if __name__ == "__main__":
    main()