import json
import base64
from typing import Dict, Any, Union
from _collections_abc import dict_keys
from pydantic import BaseModel

def base_model_from_keys(model: BaseModel, kwargs: dict) -> tuple[BaseModel, dict]:
    # If model is a class, create a temporary instance to get field names
    if isinstance(model, type) and issubclass(model, BaseModel):
        # Create temporary instance with defaults to get field names
        temp_instance = model()
        base_model_dict: Dict[str, Any] = temp_instance.dict()
        base_model_keys: dict_keys[str, Any] = base_model_dict.keys()
        kwargs = json_from_keys(base_model_keys, kwargs)
        return model(**kwargs), kwargs
    else:
        # If it's already an instance
        base_model_dict: Dict[str, Any] = model.dict()
        base_model_keys: dict_keys[str, Any] = base_model_dict.keys()
        kwargs = json_from_keys(base_model_keys, kwargs)
        return type(model)(**kwargs), kwargs

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

def lists_to_dict(keys: list, values: list) -> dict:
    """
    Convert two lists into a dict, one of keys the other of values
    """
    return dict(zip(keys, values))