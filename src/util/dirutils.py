def create_dir_if_not_exists(path: str) -> bool:
    """
    Create a directory if it does not already exist.

    Args:
        path (str): The path to the directory to create.
    """
    import os

    exists: bool = os.path.exists(path)
    if not exists:
        os.makedirs(path)
    return exists