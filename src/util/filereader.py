import io

def file_to_str(filename: str) -> str:
    with io.open(filename, "r") as file:
        return file.read()