import json
import base64

def json_from_keys(keys: list, jsonData: dict) -> dict:
    """
    Takes a list of keys and a json object and returns a new json object with only the keys in the list
    :param keys: list of keys to include in the new json object
    :param jsonData: json object to filter
    :return: new json object with only the keys in the list
    """
    return {key: jsonData[key] for key in keys if key in jsonData}

def serialize_for_json(obj):
    """Helper function to handle bytes data in JSON serialization."""
    if isinstance(obj, dict):
        return {key: serialize_for_json(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [serialize_for_json(item) for item in obj]
    elif isinstance(obj, bytes):
        return base64.b64encode(obj).decode('utf-8')
    else:
        return obj
    
def serialize_dict_for_json(data: dict) -> dict:
    """Serialize a dictionary for JSON serialization, handling bytes and other types."""
    return {key: serialize_for_json(value) for key, value in data.items()} if isinstance(data, dict) else data