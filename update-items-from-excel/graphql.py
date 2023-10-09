import httpx
from config import settings

def client(url, headers) -> httpx.Client:
    return httpx.Client(base_url=url, headers=headers)

def request(client, operation, arguments):
    payload = forge_payload(operation, arguments)
    response = client.post("", json=payload)
    if response.status_code == 200:
        return response.json().get("data")
    else:
        raise httpx.RequestError(f"{response.status_code=}, {response.json()=}")

def get_operation(request_name=None, request_file=None):
    return settings.graphql[request_name]

def forge_payload(gqlquery, variables):
    return {
        "query": gqlquery,
        "variables": variables,
    }