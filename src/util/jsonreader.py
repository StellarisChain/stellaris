import json
import os
import io

def read_json_file(file_path):
    """
    Reads a JSON file and returns its content as a dictionary.
    
    :param file_path: Path to the JSON file.
    :return: Dictionary containing the JSON data.
    :raises FileNotFoundError: If the file does not exist.
    :raises json.JSONDecodeError: If the file is not a valid JSON.
    """
    #if not os.path.exists(file_path):
    #    raise FileNotFoundError(f"File not found: {file_path}")
    
    with io.open(file_path, 'r', encoding='utf-8') as file:
        return json.load(file)
    
def read_json_from_namespace(namespace: str) -> dict:
    #ex config.settings is config/settings.json
    namespace = namespace.strip().replace(".", "/") + ".json"
    return read_json_file(namespace)