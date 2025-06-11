import io

def file_to_str(filename: str) -> str:
    with io.open(filename, "r") as file:
        return file.read()
    
def read_key_file(key_name: str):
    key_name = f"{key_name}.key"
    key_dir = f"data/local/{key_name}"
    try:
        with io.open(key_dir, "r") as file:
            return file.read()
    except FileNotFoundError:
        raise FileNotFoundError(f"Key file '{key_name}' not found in '{key_dir}'.")
    except Exception as e:
        raise Exception(f"An error occurred while reading the key file: {str(e)}")
    
def save_key_file(key_name: str, key_data: str):
    key_name = f"{key_name}.key"
    key_dir = f"data/local/{key_name}"
    try:
        with io.open(key_dir, "w") as file:
            file.write(key_data)
    except Exception as e:
        raise Exception(f"An error occurred while saving the key file: {str(e)}")