def json_from_keys(keys: list, jsonData: dict) -> dict:
    """
    Takes a list of keys and a json object and returns a new json object with only the keys in the list
    :param keys: list of keys to include in the new json object
    :param jsonData: json object to filter
    :return: new json object with only the keys in the list
    """
    return {key: jsonData[key] for key in keys if key in jsonData}