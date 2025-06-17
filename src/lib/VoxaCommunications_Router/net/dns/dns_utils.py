import os
import io
import json
from typing import Dict, Any, Optional, Tuple, Union
from datetime import datetime
from util.jsonreader import read_json_from_namespace
from util.logging import log
from lib.compression import JSONCompressor
from schema.dns.a_record import ARecord
from schema.dns.dns_record import DNSRecord
from modern_benchmark import BenchmarkCollector, benchmark

logger: log = log()
benchmark_collector: BenchmarkCollector = BenchmarkCollector()


@benchmark("dns_utils.load_file", collector=benchmark_collector)
def load_file(file_name: str, path: Optional[str] = "dns") -> Tuple[dict, datetime]:
    """
    Fetch a JSONCompressor compresssed file, and load it into a dictionary.
    Args:
        file_name (str): The name of the file to load.
        path (Optional[str]): The path to the directory containing the file. Defaults to "dns".
    Returns:
        Tuple[dict, datetime]: A tuple containing the loaded JSON data as a dictionary and the file creation time.
    """
    logger.debug(f"Loading file: {file_name} from path: {path}")

    # Get storage configuration
    storage_config: dict = read_json_from_namespace("config.storage")
    if not storage_config:
        return None, None
    
    # Construct the DNS directory path
    data_dir: str = storage_config.get("data-dir", "data/")
    file_subdir: str = dict(storage_config.get("sub-dirs", {})).get(path, "dns/")
    file_dir: str = os.path.join(data_dir, file_subdir)

    # Check if the path exists
    if not os.path.exists(file_dir):
        logger.warning(f"Directory does not exist: {file_dir}")
        return None, None

    compressor: JSONCompressor = JSONCompressor()
    file_name = file_name.replace(".bin", "") # Remove .bin extension if present
    file_path: str = os.path.join(file_dir, f"{file_name}.bin")

    if not os.path.exists(file_path):
        logger.warning(f"File does not exist: {file_path}")
        return None, None
    
    # Get file creation time
    file_stat = os.stat(file_path)
    creation_time = datetime.fromtimestamp(file_stat.st_ctime)
    
    with io.open(file_path, "rb") as file:
        compressed_data: bytes = file.read()
    
    json_data: str = compressor.decompress(compressed_data)
    dict_data: dict = json.loads(json_data)

    return dict_data, creation_time

@benchmark("dns_utils.save_file", collector=benchmark_collector)
def save_file(file_name: str, data: dict, path: Optional[str] = "dns") -> bool:
    """
    Save a dictionary to a JSONCompressor compressed file.
    Args:
        file_name (str): The name of the file to save.
        data (dict): The data to save.
        path (Optional[str]): The path to the directory where the file will be saved. Defaults to "dns".
    Returns:
        bool: True if the file was saved successfully, False otherwise.
    """
    logger.debug(f"Saving file: {file_name} to path: {path}")

    # Get storage configuration
    storage_config: dict = read_json_from_namespace("config.storage")
    if not storage_config:
        return False
    
    # Construct the DNS directory path
    data_dir: str = storage_config.get("data-dir", "data/")
    file_subdir: str = dict(storage_config.get("sub-dirs", {})).get(path, "dns/")
    file_dir: str = os.path.join(data_dir, file_subdir)

    # Ensure the directory exists
    os.makedirs(file_dir, exist_ok=True)

    compressor: JSONCompressor = JSONCompressor()
    json_data: str = json.dumps(data, indent=4)
    compressed_data: bytes = compressor.compress(json_data)

    file_path: str = os.path.join(file_dir, f"{file_name}.bin")

    with io.open(file_path, "wb") as file:
        file.write(compressed_data)

    return True

def record_and_creation_time_dict(record: Union[DNSRecord, ARecord], creation_time: datetime) -> Dict[str, Any]:
    """
    Convert a DNSRecord (or any subclass like ARecord) and its creation time into a dictionary.
    
    Args:
        record (Union[DNSRecord, ARecord]): The DNS record to convert. Supports DNSRecord and all its subclasses.
        creation_time (datetime): The creation time of the record.
    
    Returns:
        Dict[str, Any]: A dictionary containing the record data, record type, and creation time.
    """
    return {
        "record": record.dict(),
        "record_type": record.record_type,
        "creation_time": creation_time.isoformat() if creation_time else None
    }

def record_and_creation_time_dict_to_class(record_dict: Dict[str, Any]) -> Tuple[Union[DNSRecord, ARecord], datetime]:
    """
    Convert a dictionary containing a DNSRecord and its creation time back to the appropriate DNSRecord class.
    
    Args:
        record_dict (Dict[str, Any]): The dictionary containing the record data, record type, and creation time.
    
    Returns:
        Tuple[Union[DNSRecord, ARecord], datetime]: A tuple containing the appropriate DNSRecord instance and its creation time.
    """
    record_data: dict = record_dict.get("record", {})
    record_type: str = record_dict.get("record_type", "UNSET")
    creation_time: datetime = datetime.fromisoformat(record_dict.get("creation_time", "1970-01-01T00:00:00"))
    
    # Determine which class to instantiate based on record_type
    if record_type == "A":
        return ARecord(**record_data), creation_time
    else:
        # Default to base DNSRecord for unknown types
        return DNSRecord(**record_data), creation_time

def load_all_dns_records(record_class: Optional[DNSRecord] = DNSRecord(), path: Optional[str] = "dns", duplicates: Optional[bool] = False) -> list[dict]:
    """
    Load all DNS records
    Args:
        record_class: The type of DNS record to load (used for filtering by record_type)
        path: The subdirectory path to load records from
        duplicates: If False, removes duplicates and keeps the oldest record based on creation_time
    Returns:
        List of dictionaries in the format of record_and_creation_time_dict output
    """
    logger.debug(f"Loading all DNS records of type: {record_class.record_type}")

    storage_config: dict = read_json_from_namespace("config.storage")
    if not storage_config:
        logger.error("Storage configuration not found")
        return []
    
    # Construct the DNS directory path
    data_dir: str = storage_config.get("data-dir", "data/")
    file_subdir: str = dict(storage_config.get("sub-dirs", {})).get(path, "dns/")
    file_dir: str = os.path.join(data_dir, file_subdir)

    # Check if the path exists
    if not os.path.exists(file_dir):
        logger.warning(f"Directory does not exist: {file_dir}")
        return []
    
    records: list[dict] = []
    duplicate_tracker: Dict[str, dict] = {}  # Track duplicates by domain

    for file_name in os.listdir(file_dir):
        if file_name.endswith(".bin"):
            file_path: str = os.path.join(file_dir, file_name)
            try:
                record_data, creation_time = load_file(file_name.replace(".bin", ""), path)
                if record_data and isinstance(record_data, dict):
                    record_data: dict = dict(record_data)  # Ensure it's a dictionary
                    record_dict = {
                        "record": record_data,
                        "record_type": record_class.record_type,
                        "creation_time": creation_time.isoformat() if creation_time else None
                    }
                    
                    # If duplicates are not allowed, check for duplicates by domain
                    if not duplicates:
                        domain = record_data.get("domain")
                        if domain:
                            if domain not in duplicate_tracker:
                                duplicate_tracker[domain] = record_dict
                            else:
                                # Compare creation times and keep the older record
                                existing_time = duplicate_tracker[domain].get("creation_time")
                                new_time = record_dict.get("creation_time")
                                
                                if existing_time and new_time:
                                    existing_dt: datetime = datetime.fromisoformat(existing_time)
                                    new_dt: datetime = datetime.fromisoformat(new_time)
                                    
                                    # Keep the older record
                                    if new_dt < existing_dt:
                                        duplicate_tracker[domain] = record_dict
                                        logger.debug(f"Replaced duplicate record for domain {domain} with older record")
                                    else:
                                        logger.debug(f"Skipped duplicate record for domain {domain}, existing record is older")
                                else:
                                    # If timestamps are missing, keep the first one encountered
                                    logger.warning(f"Missing timestamp for domain {domain}, keeping first record")
                        else:
                            # If no domain field, add to records list directly
                            records.append(record_dict)
                    else:
                        # If duplicates are allowed, add all records
                        records.append(record_dict)
                        
            except Exception as e:
                logger.error(f"Error loading file {file_name}: {e}")
    
    # Convert duplicate_tracker to records list if duplicates were filtered
    if not duplicates:
        records.extend(duplicate_tracker.values())
    
    logger.debug(f"Loaded {len(records)} records of type: {record_class.record_type}")

    return records