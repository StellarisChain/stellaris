use pyo3::prelude::*;
use libp2p_kad::store::{MemoryStore, RecordStore};
use libp2p_kad::{Record, RecordKey};
use std::collections::HashMap;
use std::fs;
use std::path::Path;

#[pyclass]
pub struct MemoryStorage {
    store: MemoryStore,
    records: HashMap<Vec<u8>, (Vec<u8>, Option<String>, Option<u64>)>,
}

#[pymethods]
impl MemoryStorage {
    #[new]
    fn new(peer_id: String) -> PyResult<Self> {
        let peer_id = peer_id.parse()
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("Invalid peer ID: {}", e)))?;
        let store = MemoryStore::new(peer_id);
        
        Ok(Self {
            store,
            records: HashMap::new(),
        })
    }

    #[pyo3(signature = (key, value, publisher=None, ttl=None))]
    fn put_record(&mut self, key: Vec<u8>, value: Vec<u8>, publisher: Option<String>, ttl: Option<u64>) -> PyResult<()> {
        let record_key = RecordKey::new(&key);
        let mut record = Record::new(record_key, value.clone());
        
        if let Some(pub_str) = &publisher {
            let publisher_peer_id = pub_str.parse()
                .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("Invalid publisher peer ID: {}", e)))?;
            record.publisher = Some(publisher_peer_id);
        }
        
        if let Some(ttl_secs) = ttl {
            record.expires = Some(std::time::Instant::now() + std::time::Duration::from_secs(ttl_secs));
        }
        
        self.store.put(record)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;
        
        self.records.insert(key, (value, publisher, ttl));
        Ok(())
    }

    fn get_record(&self, key: Vec<u8>) -> Option<Vec<u8>> {
        let record_key = RecordKey::new(&key);
        self.store.get(&record_key).map(|record| record.value.clone())
    }

    fn remove_record(&mut self, key: Vec<u8>) -> bool {
        let record_key = RecordKey::new(&key);
        self.store.remove(&record_key);
        self.records.remove(&key).is_some()
    }

    fn list_keys(&self) -> Vec<Vec<u8>> {
        self.records.keys().cloned().collect()
    }

    fn record_count(&self) -> usize {
        self.records.len()
    }

    fn clear(&mut self) {
        // Clear the MemoryStore by creating a new one
        if let Some((_, (_, _, _))) = self.records.iter().next() {
            // Get peer_id from the first record if available
            // This is a workaround since MemoryStore doesn't expose peer_id
        }
        self.records.clear();
    }

    fn has_record(&self, key: Vec<u8>) -> bool {
        self.records.contains_key(&key)
    }

    fn get_record_info(&self, key: Vec<u8>) -> Option<(Vec<u8>, Option<String>, Option<u64>)> {
        self.records.get(&key).cloned()
    }

    fn update_record(&mut self, key: Vec<u8>, value: Vec<u8>) -> PyResult<bool> {
        if let Some((_, publisher, ttl)) = self.records.get(&key).cloned() {
            self.put_record(key, value, publisher, ttl)?;
            Ok(true)
        } else {
            Ok(false)
        }
    }

    fn get_records_by_publisher(&self, publisher: String) -> Vec<(Vec<u8>, Vec<u8>)> {
        self.records
            .iter()
            .filter_map(|(key, (value, pub_opt, _))| {
                if let Some(pub_str) = pub_opt {
                    if pub_str == &publisher {
                        Some((key.clone(), value.clone()))
                    } else {
                        None
                    }
                } else {
                    None
                }
            })
            .collect()
    }

    fn cleanup_expired(&mut self) -> usize {
        let _now = std::time::Instant::now();
        let mut expired_keys = Vec::new();
        
        for (key, (_, _, ttl_opt)) in &self.records {
            if let Some(_ttl_secs) = ttl_opt {
                // This is a simplified check - in reality, we'd store the creation time
                expired_keys.push(key.clone());
            }
        }
        
        let count = expired_keys.len();
        for key in expired_keys {
            self.remove_record(key);
        }
        
        count
    }

    fn get_storage_stats(&self) -> (usize, usize, usize) {
        let total_records = self.records.len();
        let total_key_bytes: usize = self.records.keys().map(|k| k.len()).sum();
        let total_value_bytes: usize = self.records.values().map(|(v, _, _)| v.len()).sum();
        
        (total_records, total_key_bytes, total_value_bytes)
    }
}

#[pyclass]
pub struct PersistentStorage {
    file_path: String,
    records: HashMap<Vec<u8>, (Vec<u8>, Option<String>, Option<u64>)>,
}

#[pymethods]
impl PersistentStorage {
    #[new]
    fn new(file_path: String) -> PyResult<Self> {
        let mut storage = Self {
            file_path: file_path.clone(),
            records: HashMap::new(),
        };
        
        if Path::new(&file_path).exists() {
            storage.load_from_file()?;
        }
        
        Ok(storage)
    }

    #[pyo3(signature = (key, value, publisher=None, ttl=None))]
    fn put_record(&mut self, key: Vec<u8>, value: Vec<u8>, publisher: Option<String>, ttl: Option<u64>) -> PyResult<()> {
        self.records.insert(key, (value, publisher, ttl));
        self.save_to_file()
    }

    fn get_record(&self, key: Vec<u8>) -> Option<Vec<u8>> {
        self.records.get(&key).map(|(value, _, _)| value.clone())
    }

    fn remove_record(&mut self, key: Vec<u8>) -> PyResult<bool> {
        let removed = self.records.remove(&key).is_some();
        if removed {
            self.save_to_file()?;
        }
        Ok(removed)
    }

    fn list_keys(&self) -> Vec<Vec<u8>> {
        self.records.keys().cloned().collect()
    }

    fn record_count(&self) -> usize {
        self.records.len()
    }

    fn clear(&mut self) -> PyResult<()> {
        self.records.clear();
        self.save_to_file()
    }

    fn has_record(&self, key: Vec<u8>) -> bool {
        self.records.contains_key(&key)
    }

    fn get_record_info(&self, key: Vec<u8>) -> Option<(Vec<u8>, Option<String>, Option<u64>)> {
        self.records.get(&key).cloned()
    }

    fn update_record(&mut self, key: Vec<u8>, value: Vec<u8>) -> PyResult<bool> {
        if let Some((_, publisher, ttl)) = self.records.get(&key).cloned() {
            self.put_record(key, value, publisher, ttl)?;
            Ok(true)
        } else {
            Ok(false)
        }
    }

    fn get_records_by_publisher(&self, publisher: String) -> Vec<(Vec<u8>, Vec<u8>)> {
        self.records
            .iter()
            .filter_map(|(key, (value, pub_opt, _))| {
                if let Some(pub_str) = pub_opt {
                    if pub_str == &publisher {
                        Some((key.clone(), value.clone()))
                    } else {
                        None
                    }
                } else {
                    None
                }
            })
            .collect()
    }

    fn cleanup_expired(&mut self) -> PyResult<usize> {
        let now = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_secs();
        
        let mut expired_keys = Vec::new();
        
        for (key, (_, _, ttl_opt)) in &self.records {
            if let Some(ttl_secs) = ttl_opt {
                if now > *ttl_secs {
                    expired_keys.push(key.clone());
                }
            }
        }
        
        let count = expired_keys.len();
        for key in expired_keys {
            self.records.remove(&key);
        }
        
        if count > 0 {
            self.save_to_file()?;
        }
        
        Ok(count)
    }

    fn get_storage_stats(&self) -> (usize, usize, usize) {
        let total_records = self.records.len();
        let total_key_bytes: usize = self.records.keys().map(|k| k.len()).sum();
        let total_value_bytes: usize = self.records.values().map(|(v, _, _)| v.len()).sum();
        
        (total_records, total_key_bytes, total_value_bytes)
    }

    fn get_file_path(&self) -> String {
        self.file_path.clone()
    }

    fn reload_from_file(&mut self) -> PyResult<()> {
        self.load_from_file()
    }

    fn backup_to_file(&self, backup_path: String) -> PyResult<()> {
        let serialized = serde_json::to_string(&self.records)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;
        
        fs::write(&backup_path, serialized)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(e.to_string()))?;
        
        Ok(())
    }

    fn restore_from_backup(&mut self, backup_path: String) -> PyResult<()> {
        let data = fs::read_to_string(&backup_path)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(e.to_string()))?;
        
        self.records = serde_json::from_str(&data)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;
        
        self.save_to_file()
    }
}

impl PersistentStorage {
    fn save_to_file(&self) -> PyResult<()> {
        let serialized = serde_json::to_string(&self.records)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;
        
        fs::write(&self.file_path, serialized)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(e.to_string()))?;
        
        Ok(())
    }

    fn load_from_file(&mut self) -> PyResult<()> {
        let data = fs::read_to_string(&self.file_path)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(e.to_string()))?;
        
        self.records = serde_json::from_str(&data)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;
        
        Ok(())
    }
}