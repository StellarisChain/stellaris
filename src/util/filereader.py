import io
from typing import Optional

def file_to_str(filename: str, raise_error: Optional[bool]) -> str:
    try:
        with io.open(filename, "r") as file:
            return file.read()
    except FileNotFoundError:
        if raise_error:
            raise FileNotFoundError(f"File '{filename}' not found.")
    except Exception as e:
        if raise_error:
            raise Exception(f"An error occurred while reading the file: {str(e)}")
    return ""
    
def read_key_file(key_name: str, datapath: Optional[str] = "local", raise_error: Optional[bool] = True) -> str:
    key_name = f"{key_name}.key"
    key_dir = f"data/{datapath}/{key_name}"
    try:
        with io.open(key_dir, "r") as file:
            return file.read()
    except FileNotFoundError:
        if raise_error:
            raise FileNotFoundError(f"Key file '{key_name}' not found in '{key_dir}'.")
    except Exception as e:
        if raise_error:
            raise Exception(f"An error occurred while reading the key file: {str(e)}")
    return ""
    
def save_key_file(key_name: str, key_data: str, datapath: Optional[str] = "local"):
    key_name = f"{key_name}.key"
    key_dir = f"data/{datapath}/{key_name}"
    try:
        with io.open(key_dir, "w") as file:
            file.write(key_data)
    except Exception as e:
        raise Exception(f"An error occurred while saving the key file: {str(e)}")