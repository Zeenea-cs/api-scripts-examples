import os


def create_parent(path: str) -> None:
    """Create the parent folder of the given path if it doesn't exist."""
    parent = os.path.dirname(path)
    if parent and not os.path.exists(parent):
        os.makedirs(parent)
