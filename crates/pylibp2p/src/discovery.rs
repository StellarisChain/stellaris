use pyo3::prelude::*;
use libp2p::{PeerId, Multiaddr};
use std::collections::{HashMap, HashSet};
use std::time::{Duration, SystemTime};

#[pyclass]
#[derive(Clone)]
pub struct DiscoveredPeer {
    #[pyo3(get)]
    pub peer_id: String,
    #[pyo3(get)]
    pub addresses: Vec<String>,
    #[pyo3(get)]
    pub discovery_method: String,
    #[pyo3(get)]
    pub discovered_at: u64,
    #[pyo3(get)]
    pub protocols: Vec<String>,
}

#[pyclass]
pub struct MdnsManager {
    enabled: bool,
    discovered_peers: HashMap<String, DiscoveredPeer>,
    query_interval: Duration,
}

#[pymethods]
impl MdnsManager {
    #[new]
    fn new() -> Self {
        Self {
            enabled: true,
            discovered_peers: HashMap::new(),
            query_interval: Duration::from_secs(30),
        }
    }

    fn enable(&mut self) {
        self.enabled = true;
    }

    fn disable(&mut self) {
        self.enabled = false;
    }

    fn is_enabled(&self) -> bool {
        self.enabled
    }

    fn set_query_interval(&mut self, seconds: u64) {
        self.query_interval = Duration::from_secs(seconds);
    }

    fn get_query_interval(&self) -> u64 {
        self.query_interval.as_secs()
    }

    fn add_discovered_peer(&mut self, peer_id: String, addresses: Vec<String>) {
        let peer = DiscoveredPeer {
            peer_id: peer_id.clone(),
            addresses,
            discovery_method: "mdns".to_string(),
            discovered_at: SystemTime::now()
                .duration_since(SystemTime::UNIX_EPOCH)
                .unwrap()
                .as_secs(),
            protocols: vec![],
        };
        self.discovered_peers.insert(peer_id, peer);
    }

    fn get_discovered_peers(&self) -> Vec<DiscoveredPeer> {
        self.discovered_peers.values().cloned().collect()
    }

    fn clear_discovered_peers(&mut self) {
        self.discovered_peers.clear();
    }

    fn remove_peer(&mut self, peer_id: String) -> bool {
        self.discovered_peers.remove(&peer_id).is_some()
    }
}

#[pyclass]
pub struct KademliaManager {
    bootstrap_peers: Vec<String>,
    stored_records: HashMap<String, Vec<u8>>,
    query_timeout: Duration,
    replication_factor: usize,
}

#[pymethods]
impl KademliaManager {
    #[new]
    fn new() -> Self {
        Self {
            bootstrap_peers: Vec::new(),
            stored_records: HashMap::new(),
            query_timeout: Duration::from_secs(10),
            replication_factor: 20,
        }
    }

    fn add_bootstrap_peer(&mut self, peer_addr: String) -> PyResult<()> {
        // Validate the multiaddr
        peer_addr.parse::<Multiaddr>()
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(e.to_string()))?;
        
        if !self.bootstrap_peers.contains(&peer_addr) {
            self.bootstrap_peers.push(peer_addr);
        }
        Ok(())
    }

    fn remove_bootstrap_peer(&mut self, peer_addr: String) {
        self.bootstrap_peers.retain(|addr| addr != &peer_addr);
    }

    fn get_bootstrap_peers(&self) -> Vec<String> {
        self.bootstrap_peers.clone()
    }

    fn set_query_timeout(&mut self, seconds: u64) {
        self.query_timeout = Duration::from_secs(seconds);
    }

    fn get_query_timeout(&self) -> u64 {
        self.query_timeout.as_secs()
    }

    fn set_replication_factor(&mut self, factor: usize) {
        self.replication_factor = factor;
    }

    fn get_replication_factor(&self) -> usize {
        self.replication_factor
    }

    fn cache_record(&mut self, key: String, value: Vec<u8>) {
        self.stored_records.insert(key, value);
    }

    fn get_cached_record(&self, key: String) -> Option<Vec<u8>> {
        self.stored_records.get(&key).cloned()
    }

    fn remove_cached_record(&mut self, key: String) -> bool {
        self.stored_records.remove(&key).is_some()
    }

    fn get_cached_keys(&self) -> Vec<String> {
        self.stored_records.keys().cloned().collect()
    }

    fn clear_cache(&mut self) {
        self.stored_records.clear();
    }

    fn get_cache_size(&self) -> usize {
        self.stored_records.len()
    }
}

#[pyclass]
pub struct AutonatManager {
    enabled: bool,
    confidence_threshold: usize,
    last_probe_result: Option<String>,
    probe_history: Vec<String>,
}

#[pymethods]
impl AutonatManager {
    #[new]
    fn new() -> Self {
        Self {
            enabled: true,
            confidence_threshold: 3,
            last_probe_result: None,
            probe_history: Vec::new(),
        }
    }

    fn enable(&mut self) {
        self.enabled = true;
    }

    fn disable(&mut self) {
        self.enabled = false;
    }

    fn is_enabled(&self) -> bool {
        self.enabled
    }

    fn set_confidence_threshold(&mut self, threshold: usize) {
        self.confidence_threshold = threshold;
    }

    fn get_confidence_threshold(&self) -> usize {
        self.confidence_threshold
    }

    fn record_probe_result(&mut self, result: String) {
        self.last_probe_result = Some(result.clone());
        self.probe_history.push(result);
        
        // Keep only the last 100 results
        if self.probe_history.len() > 100 {
            self.probe_history.remove(0);
        }
    }

    fn get_last_probe_result(&self) -> Option<String> {
        self.last_probe_result.clone()
    }

    fn get_probe_history(&self) -> Vec<String> {
        self.probe_history.clone()
    }

    fn clear_probe_history(&mut self) {
        self.probe_history.clear();
        self.last_probe_result = None;
    }

    fn get_nat_status(&self) -> String {
        // Simplified NAT status determination
        if let Some(ref last_result) = self.last_probe_result {
            if last_result.contains("public") {
                "public".to_string()
            } else if last_result.contains("private") {
                "private".to_string()
            } else {
                "unknown".to_string()
            }
        } else {
            "unknown".to_string()
        }
    }
}

#[pyclass]
pub struct RendezvousManager {
    registration_points: HashMap<String, String>,
    discovered_peers: HashMap<String, DiscoveredPeer>,
    namespaces: HashSet<String>,
}

#[pymethods]
impl RendezvousManager {
    #[new]
    fn new() -> Self {
        Self {
            registration_points: HashMap::new(),
            discovered_peers: HashMap::new(),
            namespaces: HashSet::new(),
        }
    }

    fn add_registration_point(&mut self, peer_id: String, address: String) -> PyResult<()> {
        // Validate peer ID and address
        peer_id.parse::<PeerId>()
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(e.to_string()))?;
        address.parse::<Multiaddr>()
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(e.to_string()))?;
        
        self.registration_points.insert(peer_id, address);
        Ok(())
    }

    fn remove_registration_point(&mut self, peer_id: String) -> bool {
        self.registration_points.remove(&peer_id).is_some()
    }

    fn get_registration_points(&self) -> HashMap<String, String> {
        self.registration_points.clone()
    }

    fn add_namespace(&mut self, namespace: String) {
        self.namespaces.insert(namespace);
    }

    fn remove_namespace(&mut self, namespace: String) -> bool {
        self.namespaces.remove(&namespace)
    }

    fn get_namespaces(&self) -> Vec<String> {
        self.namespaces.iter().cloned().collect()
    }

    fn register_discovered_peer(&mut self, peer_id: String, addresses: Vec<String>, namespace: String) {
        let peer = DiscoveredPeer {
            peer_id: peer_id.clone(),
            addresses,
            discovery_method: format!("rendezvous:{}", namespace),
            discovered_at: SystemTime::now()
                .duration_since(SystemTime::UNIX_EPOCH)
                .unwrap()
                .as_secs(),
            protocols: vec![],
        };
        self.discovered_peers.insert(peer_id, peer);
    }

    fn get_discovered_peers_in_namespace(&self, namespace: String) -> Vec<DiscoveredPeer> {
        self.discovered_peers
            .values()
            .filter(|peer| peer.discovery_method.contains(&namespace))
            .cloned()
            .collect()
    }

    fn get_all_discovered_peers(&self) -> Vec<DiscoveredPeer> {
        self.discovered_peers.values().cloned().collect()
    }

    fn clear_discovered_peers(&mut self) {
        self.discovered_peers.clear();
    }
}

#[pyclass]
pub struct IdentifyManager {
    agent_version: String,
    protocol_version: String,
    supported_protocols: HashSet<String>,
    observed_addresses: HashSet<String>,
    peer_info: HashMap<String, HashMap<String, String>>,
}

#[pymethods]
impl IdentifyManager {
    #[new]
    fn new() -> Self {
        Self {
            agent_version: "voxa-libp2p/1.0.0".to_string(),
            protocol_version: "ipfs/0.1.0".to_string(),
            supported_protocols: HashSet::new(),
            observed_addresses: HashSet::new(),
            peer_info: HashMap::new(),
        }
    }

    fn set_agent_version(&mut self, version: String) {
        self.agent_version = version;
    }

    fn get_agent_version(&self) -> String {
        self.agent_version.clone()
    }

    fn set_protocol_version(&mut self, version: String) {
        self.protocol_version = version;
    }

    fn get_protocol_version(&self) -> String {
        self.protocol_version.clone()
    }

    fn add_supported_protocol(&mut self, protocol: String) {
        self.supported_protocols.insert(protocol);
    }

    fn remove_supported_protocol(&mut self, protocol: String) -> bool {
        self.supported_protocols.remove(&protocol)
    }

    fn get_supported_protocols(&self) -> Vec<String> {
        self.supported_protocols.iter().cloned().collect()
    }

    fn add_observed_address(&mut self, address: String) -> PyResult<()> {
        address.parse::<Multiaddr>()
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(e.to_string()))?;
        
        self.observed_addresses.insert(address);
        Ok(())
    }

    fn get_observed_addresses(&self) -> Vec<String> {
        self.observed_addresses.iter().cloned().collect()
    }

    fn record_peer_info(&mut self, peer_id: String, agent_version: String, protocol_version: String, protocols: Vec<String>) {
        let mut info = HashMap::new();
        info.insert("agent_version".to_string(), agent_version);
        info.insert("protocol_version".to_string(), protocol_version);
        info.insert("protocols".to_string(), protocols.join(","));
        info.insert("discovered_at".to_string(), 
                   SystemTime::now()
                       .duration_since(SystemTime::UNIX_EPOCH)
                       .unwrap()
                       .as_secs()
                       .to_string());
        
        self.peer_info.insert(peer_id, info);
    }

    fn get_peer_info(&self, peer_id: String) -> Option<HashMap<String, String>> {
        self.peer_info.get(&peer_id).cloned()
    }

    fn get_all_peer_info(&self) -> HashMap<String, HashMap<String, String>> {
        self.peer_info.clone()
    }

    fn remove_peer_info(&mut self, peer_id: String) -> bool {
        self.peer_info.remove(&peer_id).is_some()
    }

    fn clear_peer_info(&mut self) {
        self.peer_info.clear();
    }
}