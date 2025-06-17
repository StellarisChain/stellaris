from util.logging import log
import uuid
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from schema.dns.dns_record import DNSRecord
from schema.dns.a_record import ARecord
from lib.VoxaCommunications_Router.net.dns import dns_utils

class DNSManager:
    def __init__(self):
        self.logger = log()
        self.logger.info("DNSManager initialized")
        self._records_cache: Dict[str, Dict[str, Any]] = {}
        self._last_cache_update: Optional[datetime] = None
        self._cache_ttl: int = 300  # 5 minutes cache TTL
    
    def create_a_record(self, domain: str, ip_address: Optional[str] = None, 
                       node_id: Optional[str] = None, 
                       allowed_protocols: List[str] = None,
                       ttl: int = 3600) -> ARecord:
        """
        Create a new A record
        
        Args:
            domain: The domain name for the record
            ip_address: Optional IP address (if not provided, will be resolved)
            node_id: Optional node ID for the request
            allowed_protocols: List of allowed protocols (defaults to ["ssu", "i2p"])
            ttl: Time to live in seconds (default 3600)
            
        Returns:
            ARecord: The created A record
        """
        if allowed_protocols is None:
            allowed_protocols = ["ssu", "i2p"]
            
        try:
            record = ARecord(
                domain=domain,
                ip_address=ip_address,
                node_id=node_id,
                allowed_protocols=allowed_protocols,
                creation_date=datetime.now().isoformat(),
                ttl=ttl
            )
            
            self.logger.info(f"Created A record for domain: {domain}")
            return record
            
        except Exception as e:
            self.logger.error(f"Failed to create A record for domain {domain}: {e}")
            raise
    
    def create_dns_record(self, record_type: str, **kwargs) -> DNSRecord:
        """
        Create a generic DNS record
        
        Args:
            record_type: The type of DNS record to create
            **kwargs: Additional arguments for the record
            
        Returns:
            DNSRecord: The created DNS record
        """
        try:
            record = DNSRecord(record_type=record_type, **kwargs)
            self.logger.info(f"Created DNS record of type: {record_type}")
            return record
            
        except Exception as e:
            self.logger.error(f"Failed to create DNS record of type {record_type}: {e}")
            raise
    
    def save_record(self, record: Union[DNSRecord, ARecord], 
                   file_name: Optional[str] = None,
                   path: str = "dns") -> bool:
        """
        Save a DNS record to storage
        
        Args:
            record: The DNS record to save
            file_name: Optional custom filename (if not provided, generates UUID)
            path: Storage path (default "dns")
            
        Returns:
            bool: True if saved successfully, False otherwise
        """
        try:
            if file_name is None:
                file_name = str(uuid.uuid4())
            
            record_data = record.dict() if hasattr(record, 'dict') else record.__dict__
            
            success = dns_utils.save_file(file_name, record_data, path)
            
            if success:
                self.logger.info(f"Saved DNS record to file: {file_name}")
                # Invalidate cache
                self._last_cache_update = None
            else:
                self.logger.error(f"Failed to save DNS record to file: {file_name}")
                
            return success
            
        except Exception as e:
            self.logger.error(f"Error saving DNS record: {e}")
            return False
    
    def load_record(self, file_name: str, path: str = "dns") -> Optional[Dict[str, Any]]:
        """
        Load a DNS record from storage
        
        Args:
            file_name: The filename to load
            path: Storage path (default "dns")
            
        Returns:
            Optional[Dict]: The loaded record data or None if not found
        """
        try:
            record_data, creation_time = dns_utils.load_file(file_name, path)
            
            if record_data:
                self.logger.info(f"Loaded DNS record from file: {file_name}")
                return {
                    "record": record_data,
                    "creation_time": creation_time.isoformat() if creation_time else None
                }
            else:
                self.logger.warning(f"DNS record not found: {file_name}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error loading DNS record {file_name}: {e}")
            return None
    
    def load_all_records(self, record_type: Optional[str] = None,
                        path: str = "dns",
                        remove_duplicates: bool = True) -> List[Dict[str, Any]]:
        """
        Load all DNS records of a specific type
        
        Args:
            record_type: Optional record type filter (e.g., "A")
            path: Storage path (default "dns")
            remove_duplicates: Whether to remove duplicate records
            
        Returns:
            List[Dict]: List of loaded records
        """
        try:
            if record_type:
                if record_type == "A":
                    record_class = ARecord()
                else:
                    record_class = DNSRecord(record_type=record_type)
            else:
                record_class = DNSRecord()
            
            records = dns_utils.load_all_dns_records(
                record_class=record_class,
                path=path,
                duplicates=not remove_duplicates
            )
            
            self.logger.info(f"Loaded {len(records)} DNS records of type: {record_type or 'ALL'}")
            return records
            
        except Exception as e:
            self.logger.error(f"Error loading DNS records: {e}")
            return []
    
    def get_records_by_domain(self, domain: str, path: str = "dns") -> List[Dict[str, Any]]:
        """
        Get all records for a specific domain
        
        Args:
            domain: The domain to search for
            path: Storage path (default "dns")
            
        Returns:
            List[Dict]: List of records matching the domain
        """
        try:
            all_records = self.load_all_records(path=path)
            matching_records = []
            
            for record_dict in all_records:
                record_data = record_dict.get("record", {})
                if record_data.get("domain") == domain:
                    matching_records.append(record_dict)
            
            self.logger.info(f"Found {len(matching_records)} records for domain: {domain}")
            return matching_records
            
        except Exception as e:
            self.logger.error(f"Error searching for domain {domain}: {e}")
            return []
    
    def delete_record(self, file_name: str, path: str = "dns") -> bool:
        """
        Delete a DNS record file
        
        Args:
            file_name: The filename to delete
            path: Storage path (default "dns")
            
        Returns:
            bool: True if deleted successfully, False otherwise
        """
        try:
            import os
            from util.jsonreader import read_json_from_namespace
            
            storage_config = read_json_from_namespace("config.storage")
            if not storage_config:
                self.logger.error("Storage configuration not found")
                return False
            
            data_dir = storage_config.get("data-dir", "data/")
            file_subdir = dict(storage_config.get("sub-dirs", {})).get(path, "dns/")
            file_dir = os.path.join(data_dir, file_subdir)
            
            file_name = file_name.replace(".bin", "")
            file_path = os.path.join(file_dir, f"{file_name}.bin")
            
            if os.path.exists(file_path):
                os.remove(file_path)
                self.logger.info(f"Deleted DNS record file: {file_name}")
                # Invalidate cache
                self._last_cache_update = None
                return True
            else:
                self.logger.warning(f"DNS record file not found for deletion: {file_name}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error deleting DNS record {file_name}: {e}")
            return False
    
    def update_cache(self, force: bool = False) -> None:
        """
        Update the internal records cache
        
        Args:
            force: Force cache update even if TTL hasn't expired
        """
        try:
            now = datetime.now()
            
            if (force or 
                self._last_cache_update is None or 
                (now - self._last_cache_update).total_seconds() > self._cache_ttl):
                
                self.logger.debug("Updating DNS records cache")
                
                all_records = self.load_all_records()
                self._records_cache.clear()
                
                for record_dict in all_records:
                    record_data = record_dict.get("record", {})
                    domain = record_data.get("domain")
                    if domain:
                        if domain not in self._records_cache:
                            self._records_cache[domain] = []
                        self._records_cache[domain].append(record_dict)
                
                self._last_cache_update = now
                self.logger.info(f"Cache updated with {len(self._records_cache)} unique domains")
                
        except Exception as e:
            self.logger.error(f"Error updating cache: {e}")
    
    def get_cached_records(self, domain: str) -> List[Dict[str, Any]]:
        """
        Get records for a domain from cache
        
        Args:
            domain: The domain to search for
            
        Returns:
            List[Dict]: List of cached records for the domain
        """
        self.update_cache()
        return self._records_cache.get(domain, [])
    
    def propagate_records(self, records: Optional[List[Union[DNSRecord, ARecord]]] = None,
                         target_nodes: Optional[List[str]] = None,
                         propagation_method: str = "broadcast") -> Dict[str, Any]:
        """
        Propagate DNS records to other nodes in the network
        
        This is a placeholder function that will be implemented based on the 
        network topology and propagation requirements.
        
        Args:
            records: Optional list of specific records to propagate (if None, propagates all)
            target_nodes: Optional list of specific nodes to propagate to
            propagation_method: Method of propagation ("broadcast", "selective", "cascade")
            
        Returns:
            Dict: Propagation result with success/failure information
        """
        self.logger.info(f"Propagating DNS records using method: {propagation_method}")
        
        # TODO: Implement actual propagation logic
        # This should integrate with the network layer to:
        # 1. Identify target nodes (if not specified)
        # 2. Serialize records for transmission
        # 3. Send records to target nodes
        # 4. Handle acknowledgments and retries
        # 5. Update propagation status
        
        result = {
            "status": "placeholder",
            "method": propagation_method,
            "records_count": len(records) if records else 0,
            "target_nodes": target_nodes or [],
            "timestamp": datetime.now().isoformat(),
            "success": False,
            "message": "Propagation function is a placeholder - implementation pending"
        }
        
        self.logger.warning("DNS propagation called but not yet implemented")
        return result
    
    def validate_record(self, record: Union[DNSRecord, ARecord]) -> bool:
        """
        Validate a DNS record
        
        Args:
            record: The record to validate
            
        Returns:
            bool: True if valid, False otherwise
        """
        try:
            # Use Pydantic validation
            if hasattr(record, 'dict'):
                record.dict()  # This will trigger validation
            return True
        except Exception as e:
            self.logger.error(f"Record validation failed: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the DNS manager
        
        Returns:
            Dict: Statistics including record counts, cache status, etc.
        """
        try:
            self.update_cache()
            
            total_records = sum(len(records) for records in self._records_cache.values())
            unique_domains = len(self._records_cache)
            
            stats = {
                "total_records": total_records,
                "unique_domains": unique_domains,
                "cache_last_updated": self._last_cache_update.isoformat() if self._last_cache_update else None,
                "cache_ttl_seconds": self._cache_ttl,
                "timestamp": datetime.now().isoformat()
            }
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Error getting DNS manager stats: {e}")
            return {"error": str(e)}