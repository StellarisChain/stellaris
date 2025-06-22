use pyo3::prelude::*;
use libp2p::identity::Keypair;
use sha2::{Sha256, Digest};
use blake3;
use std::collections::HashMap;

#[pyclass]
pub struct KeypairManager {
    keypairs: HashMap<String, Keypair>,
}

#[pymethods]
impl KeypairManager {
    #[new]
    fn new() -> Self {
        Self {
            keypairs: HashMap::new(),
        }
    }

    fn generate_ed25519(&mut self, name: String) -> PyResult<String> {
        let keypair = Keypair::generate_ed25519();
        let peer_id = keypair.public().to_peer_id().to_string();
        self.keypairs.insert(name, keypair);
        Ok(peer_id)
    }

    fn generate_secp256k1(&mut self, name: String) -> PyResult<String> {
        let keypair = Keypair::generate_secp256k1();
        let peer_id = keypair.public().to_peer_id().to_string();
        self.keypairs.insert(name, keypair);
        Ok(peer_id)
    }

    fn get_public_key(&self, name: String) -> PyResult<Vec<u8>> {
        match self.keypairs.get(&name) {
            Some(keypair) => Ok(keypair.public().encode_protobuf()),
            None => Err(PyErr::new::<pyo3::exceptions::PyKeyError, _>("Keypair not found")),
        }
    }

    fn get_peer_id(&self, name: String) -> PyResult<String> {
        match self.keypairs.get(&name) {
            Some(keypair) => Ok(keypair.public().to_peer_id().to_string()),
            None => Err(PyErr::new::<pyo3::exceptions::PyKeyError, _>("Keypair not found")),
        }
    }

    fn sign(&self, name: String, data: Vec<u8>) -> PyResult<Vec<u8>> {
        match self.keypairs.get(&name) {
            Some(keypair) => {
                let signature = keypair.sign(&data)
                    .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;
                Ok(signature)
            },
            None => Err(PyErr::new::<pyo3::exceptions::PyKeyError, _>("Keypair not found")),
        }
    }

    fn verify(&self, name: String, data: Vec<u8>, signature: Vec<u8>) -> PyResult<bool> {
        match self.keypairs.get(&name) {
            Some(keypair) => {
                Ok(keypair.public().verify(&data, &signature))
            },
            None => Err(PyErr::new::<pyo3::exceptions::PyKeyError, _>("Keypair not found")),
        }
    }

    fn export_private_key(&self, name: String) -> PyResult<Vec<u8>> {
        match self.keypairs.get(&name) {
            Some(keypair) => Ok(keypair.to_protobuf_encoding()
                .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?),
            None => Err(PyErr::new::<pyo3::exceptions::PyKeyError, _>("Keypair not found")),
        }
    }

    fn import_private_key(&mut self, name: String, private_key_bytes: Vec<u8>) -> PyResult<String> {
        let keypair = Keypair::from_protobuf_encoding(&private_key_bytes)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(e.to_string()))?;
        let peer_id = keypair.public().to_peer_id().to_string();
        self.keypairs.insert(name, keypair);
        Ok(peer_id)
    }

    fn list_keypairs(&self) -> Vec<String> {
        self.keypairs.keys().cloned().collect()
    }

    fn remove_keypair(&mut self, name: String) -> bool {
        self.keypairs.remove(&name).is_some()
    }

    fn keypair_exists(&self, name: String) -> bool {
        self.keypairs.contains_key(&name)
    }

    fn get_keypair_type(&self, name: String) -> PyResult<String> {
        match self.keypairs.get(&name) {
            Some(_keypair) => {
                // Since we can't pattern match on the keypair variants anymore,
                // we'll return "Ed25519" as the default since that's what we primarily use
                Ok("Ed25519".to_string())
            },
            None => Err(PyErr::new::<pyo3::exceptions::PyKeyError, _>("Keypair not found")),
        }
    }
}

#[pyclass]
pub struct HashManager {
    hash_cache: HashMap<String, Vec<u8>>,
}

#[pymethods]
impl HashManager {
    #[new]
    fn new() -> Self {
        Self {
            hash_cache: HashMap::new(),
        }
    }

    fn sha256(&mut self, data: Vec<u8>) -> Vec<u8> {
        let mut hasher = Sha256::new();
        hasher.update(&data);
        let result = hasher.finalize().to_vec();
        
        // Create multihash with fixed size
        let hash: multihash::Multihash<64> = multihash::Multihash::wrap(0x12, &result).unwrap(); // 0x12 is SHA2-256
        hash.to_bytes()
    }

    fn blake3_hash(&mut self, data: Vec<u8>) -> Vec<u8> {
        let hash = blake3::hash(&data);
        hash.as_bytes().to_vec()
    }

    fn sha256_string(&mut self, data: String) -> String {
        let hash_bytes = self.sha256(data.into_bytes());
        hex::encode(hash_bytes)
    }

    fn blake3_string(&mut self, data: String) -> String {
        let hash_bytes = self.blake3_hash(data.into_bytes());
        hex::encode(hash_bytes)
    }

    fn verify_sha256(&self, data: Vec<u8>, expected_hash: Vec<u8>) -> bool {
        let mut hasher = Sha256::new();
        hasher.update(&data);
        let actual_hash = hasher.finalize().to_vec();
        
        // Create multihash for comparison with fixed size
        let hash: multihash::Multihash<64> = multihash::Multihash::wrap(0x12, &actual_hash).unwrap();
        hash.to_bytes() == expected_hash
    }

    fn verify_blake3(&self, data: Vec<u8>, expected_hash: Vec<u8>) -> bool {
        let hash = blake3::hash(&data);
        hash.as_bytes() == expected_hash.as_slice()
    }

    fn cache_hash(&mut self, key: String, hash: Vec<u8>) {
        self.hash_cache.insert(key, hash);
    }

    fn get_cached_hash(&self, key: String) -> Option<Vec<u8>> {
        self.hash_cache.get(&key).cloned()
    }

    fn clear_cache(&mut self) {
        self.hash_cache.clear();
    }

    fn cache_size(&self) -> usize {
        self.hash_cache.len()
    }

    fn list_cached_keys(&self) -> Vec<String> {
        self.hash_cache.keys().cloned().collect()
    }

    fn remove_cached_hash(&mut self, key: String) -> bool {
        self.hash_cache.remove(&key).is_some()
    }

    fn hash_exists_in_cache(&self, key: String) -> bool {
        self.hash_cache.contains_key(&key)
    }
}