import json
import os
import io
from typing import LiteralString

def read_json_file(file_path) -> dict:
    """
    Reads a JSON file and returns its content as a dictionary.
    Lines starting with // are treated as comments and filtered out.
    
    :param file_path: Path to the JSON file.
    :return: Dictionary containing the JSON data.
    :raises FileNotFoundError: If the file does not exist.
    :raises json.JSONDecodeError: If the file is not a valid JSON.
    """
    #if not os.path.exists(file_path):
    #    raise FileNotFoundError(f"File not found: {file_path}")
    
    with io.open(file_path, 'r', encoding='utf-8') as file:
        # Read all lines and filter out comments starting with //
        lines: list[str] = file.readlines()
        filtered_lines: list = []
        for line in lines:
            stripped_line: str = line.strip()
            if not stripped_line.startswith('//'):
                filtered_lines.append(line)
        
        # Join the filtered lines back into a single string
        json_content: LiteralString | str = ''.join(filtered_lines)
        return json.loads(json_content)
    
def read_json_from_namespace(namespace: str) -> dict:
    #ex config.settings is config/settings.json
    namespace = namespace.strip().replace(".", "/") + ".json"
    return read_json_file(namespace)