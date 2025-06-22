use pyo3::prelude::*;
use libp2p_gossipsub as gossipsub;
use libp2p_relay as relay;
use std::collections::HashMap;
use std::time::{Duration, SystemTime};

#[pyclass]
pub struct GossipsubManager {
    topics: HashMap<String, gossipsub::IdentTopic>,
    config: gossipsub::Config,
    subscribed_peers: HashMap<String, Vec<String>>,
    message_cache: Vec<(String, Vec<u8>, u64)>, // topic, data, timestamp
}

#[pymethods]
impl GossipsubManager {
    #[new]
    fn new() -> PyResult<Self> {
        let config = gossipsub::ConfigBuilder::default()
            .heartbeat_interval(Duration::from_secs(10))
            .validation_mode(gossipsub::ValidationMode::Strict)
            .message_id_fn(|message: &gossipsub::Message| {
                use sha2::{Sha256, Digest};
                let mut hasher = Sha256::new();
                hasher.update(&message.data);
                hasher.update(&message.source.map(|p| p.to_bytes()).unwrap_or_default());
                gossipsub::MessageId::from(hasher.finalize().to_vec())
            })
            .duplicate_cache_time(Duration::from_secs(60))
            .mesh_n_high(12)
            .mesh_n_low(4)
            .mesh_outbound_min(2)
            .build()
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;

        Ok(Self {
            topics: HashMap::new(),
            config,
            subscribed_peers: HashMap::new(),
            message_cache: Vec::new(),
        })
    }

    fn create_topic(&mut self, topic_name: String) -> PyResult<()> {
        let topic = gossipsub::IdentTopic::new(topic_name.clone());
        self.topics.insert(topic_name.clone(), topic);
        self.subscribed_peers.insert(topic_name, Vec::new());
        Ok(())
    }

    fn get_topics(&self) -> Vec<String> {
        self.topics.keys().cloned().collect()
    }

    fn remove_topic(&mut self, topic_name: String) -> bool {
        let removed = self.topics.remove(&topic_name).is_some();
        if removed {
            self.subscribed_peers.remove(&topic_name);
        }
        removed
    }

    fn topic_exists(&self, topic_name: String) -> bool {
        self.topics.contains_key(&topic_name)
    }

    fn get_config_info(&self) -> HashMap<String, String> {
        let mut info = HashMap::new();
        info.insert("heartbeat_interval".to_string(), format!("{:?}", self.config.heartbeat_interval()));
        info.insert("validation_mode".to_string(), format!("{:?}", self.config.validation_mode()));
        info.insert("mesh_n_high".to_string(), self.config.mesh_n_high().to_string());
        info.insert("mesh_n_low".to_string(), self.config.mesh_n_low().to_string());
        info.insert("duplicate_cache_time".to_string(), format!("{:?}", self.config.duplicate_cache_time()));
        info
    }

    fn add_peer_to_topic(&mut self, topic_name: String, peer_id: String) -> PyResult<()> {
        if let Some(peers) = self.subscribed_peers.get_mut(&topic_name) {
            if !peers.contains(&peer_id) {
                peers.push(peer_id);
            }
            Ok(())
        } else {
            Err(PyErr::new::<pyo3::exceptions::PyKeyError, _>("Topic not found"))
        }
    }

    fn remove_peer_from_topic(&mut self, topic_name: String, peer_id: String) -> bool {
        if let Some(peers) = self.subscribed_peers.get_mut(&topic_name) {
            if let Some(pos) = peers.iter().position(|p| p == &peer_id) {
                peers.remove(pos);
                return true;
            }
        }
        false
    }

    fn get_topic_peers(&self, topic_name: String) -> Vec<String> {
        self.subscribed_peers.get(&topic_name).cloned().unwrap_or_default()
    }

    fn cache_message(&mut self, topic: String, data: Vec<u8>) {
        let timestamp = SystemTime::now()
            .duration_since(SystemTime::UNIX_EPOCH)
            .unwrap()
            .as_secs();
        
        self.message_cache.push((topic, data, timestamp));
        
        // Keep only last 1000 messages
        if self.message_cache.len() > 1000 {
            self.message_cache.remove(0);
        }
    }

    #[pyo3(signature = (topic=None))]
    fn get_cached_messages(&self, topic: Option<String>) -> Vec<(String, Vec<u8>, u64)> {
        if let Some(topic_filter) = topic {
            self.message_cache
                .iter()
                .filter(|(t, _, _)| t == &topic_filter)
                .cloned()
                .collect()
        } else {
            self.message_cache.clone()
        }
    }

    fn clear_message_cache(&mut self) {
        self.message_cache.clear();
    }

    fn get_topic_count(&self) -> usize {
        self.topics.len()
    }

    fn clear_topics(&mut self) {
        self.topics.clear();
        self.subscribed_peers.clear();
    }

    fn get_message_stats(&self) -> HashMap<String, u64> {
        let mut stats = HashMap::new();
        let total_messages = self.message_cache.len() as u64;
        stats.insert("total_cached_messages".to_string(), total_messages);
        
        for (topic, _, _) in &self.message_cache {
            *stats.entry(format!("topic_{}_messages", topic)).or_insert(0) += 1;
        }
        
        stats
    }
}

#[pyclass]
pub struct FloodsubManager {
    subscribed_topics: Vec<String>,
}

#[pymethods]
impl FloodsubManager {
    #[new]
    fn new() -> Self {
        Self {
            subscribed_topics: Vec::new(),
        }
    }

    fn add_topic(&mut self, topic: String) {
        if !self.subscribed_topics.contains(&topic) {
            self.subscribed_topics.push(topic);
        }
    }

    fn remove_topic(&mut self, topic: String) {
        self.subscribed_topics.retain(|t| t != &topic);
    }

    fn get_topics(&self) -> Vec<String> {
        self.subscribed_topics.clone()
    }
}

#[pyclass]
pub struct RequestResponseManager {
    protocol_configs: HashMap<String, String>,
    pending_requests: HashMap<String, Vec<u8>>,
}

#[pymethods]
impl RequestResponseManager {
    #[new]
    fn new() -> Self {
        Self {
            protocol_configs: HashMap::new(),
            pending_requests: HashMap::new(),
        }
    }

    fn add_protocol(&mut self, name: String, version: String) {
        self.protocol_configs.insert(name, version);
    }

    fn get_protocols(&self) -> Vec<String> {
        self.protocol_configs.keys().cloned().collect()
    }

    fn track_request(&mut self, request_id: String, data: Vec<u8>) {
        self.pending_requests.insert(request_id, data);
    }

    fn complete_request(&mut self, request_id: String) -> Option<Vec<u8>> {
        self.pending_requests.remove(&request_id)
    }

    fn get_pending_requests(&self) -> Vec<String> {
        self.pending_requests.keys().cloned().collect()
    }
}

#[pyclass]
pub struct RelayManager {
    relay_config: Option<relay::Config>,
    circuit_limits: HashMap<String, u32>,
    active_circuits: Vec<String>,
    reservation_requests: HashMap<String, u64>,
}

#[pymethods]
impl RelayManager {
    #[new]
    fn new() -> Self {
        Self {
            relay_config: None,
            circuit_limits: HashMap::new(),
            active_circuits: Vec::new(),
            reservation_requests: HashMap::new(),
        }
    }

    fn enable_relay(&mut self, max_circuits: u32, max_circuits_per_peer: u32) -> PyResult<()> {
        let config = relay::Config {
            max_reservations: max_circuits as usize,
            max_reservations_per_peer: max_circuits_per_peer as usize,
            reservation_duration: Duration::from_secs(3600), // 1 hour
            max_circuits: max_circuits as usize,
            max_circuits_per_peer: max_circuits_per_peer as usize,
            max_circuit_duration: Duration::from_secs(7200), // 2 hours
            max_circuit_bytes: 1024 * 1024 * 10, // 10MB
            circuit_src_rate_limiters: Default::default(),
            reservation_rate_limiters: Default::default(),
        };
        
        self.relay_config = Some(config);
        Ok(())
    }

    fn disable_relay(&mut self) {
        self.relay_config = None;
        self.circuit_limits.clear();
        self.active_circuits.clear();
    }

    fn is_relay_enabled(&self) -> bool {
        self.relay_config.is_some()
    }

    fn set_circuit_limit(&mut self, peer_id: String, limit: u32) {
        self.circuit_limits.insert(peer_id, limit);
    }

    fn get_circuit_limit(&self, peer_id: String) -> Option<u32> {
        self.circuit_limits.get(&peer_id).copied()
    }

    fn add_active_circuit(&mut self, circuit_id: String) {
        if !self.active_circuits.contains(&circuit_id) {
            self.active_circuits.push(circuit_id);
        }
    }

    fn remove_active_circuit(&mut self, circuit_id: String) -> bool {
        if let Some(pos) = self.active_circuits.iter().position(|c| c == &circuit_id) {
            self.active_circuits.remove(pos);
            true
        } else {
            false
        }
    }

    fn get_active_circuits(&self) -> Vec<String> {
        self.active_circuits.clone()
    }

    fn get_active_circuit_count(&self) -> usize {
        self.active_circuits.len()
    }

    fn record_reservation_request(&mut self, peer_id: String) {
        let timestamp = SystemTime::now()
            .duration_since(SystemTime::UNIX_EPOCH)
            .unwrap()
            .as_secs();
        self.reservation_requests.insert(peer_id, timestamp);
    }

    fn get_reservation_requests(&self) -> HashMap<String, u64> {
        self.reservation_requests.clone()
    }

    fn clear_old_reservations(&mut self, max_age_secs: u64) -> usize {
        let now = SystemTime::now()
            .duration_since(SystemTime::UNIX_EPOCH)
            .unwrap()
            .as_secs();
        
        let initial_count = self.reservation_requests.len();
        self.reservation_requests.retain(|_, timestamp| now - *timestamp <= max_age_secs);
        initial_count - self.reservation_requests.len()
    }

    fn get_relay_stats(&self) -> HashMap<String, u64> {
        let mut stats = HashMap::new();
        stats.insert("active_circuits".to_string(), self.active_circuits.len() as u64);
        stats.insert("circuit_limits".to_string(), self.circuit_limits.len() as u64);
        stats.insert("reservation_requests".to_string(), self.reservation_requests.len() as u64);
        stats.insert("relay_enabled".to_string(), if self.relay_config.is_some() { 1 } else { 0 });
        stats
    }
}

#[pyclass]
pub struct StreamManager {
    active_streams: HashMap<String, Vec<String>>, // protocol -> stream_ids
    stream_stats: HashMap<String, (u64, u64)>, // stream_id -> (bytes_sent, bytes_received)
    protocol_handlers: HashMap<String, String>, // protocol -> handler_name
}

#[pymethods]
impl StreamManager {
    #[new]
    fn new() -> Self {
        Self {
            active_streams: HashMap::new(),
            stream_stats: HashMap::new(),
            protocol_handlers: HashMap::new(),
        }
    }

    fn register_protocol_handler(&mut self, protocol: String, handler_name: String) {
        self.protocol_handlers.insert(protocol.clone(), handler_name);
        self.active_streams.entry(protocol).or_insert_with(Vec::new);
    }

    fn unregister_protocol_handler(&mut self, protocol: String) -> bool {
        let removed = self.protocol_handlers.remove(&protocol).is_some();
        if removed {
            self.active_streams.remove(&protocol);
        }
        removed
    }

    fn add_stream(&mut self, protocol: String, stream_id: String) -> PyResult<()> {
        if let Some(streams) = self.active_streams.get_mut(&protocol) {
            if !streams.contains(&stream_id) {
                streams.push(stream_id.clone());
                self.stream_stats.insert(stream_id, (0, 0));
            }
            Ok(())
        } else {
            Err(PyErr::new::<pyo3::exceptions::PyKeyError, _>("Protocol not registered"))
        }
    }

    fn remove_stream(&mut self, protocol: String, stream_id: String) -> bool {
        if let Some(streams) = self.active_streams.get_mut(&protocol) {
            if let Some(pos) = streams.iter().position(|s| s == &stream_id) {
                streams.remove(pos);
                self.stream_stats.remove(&stream_id);
                return true;
            }
        }
        false
    }

    fn get_streams_for_protocol(&self, protocol: String) -> Vec<String> {
        self.active_streams.get(&protocol).cloned().unwrap_or_default()
    }

    fn get_all_streams(&self) -> HashMap<String, Vec<String>> {
        self.active_streams.clone()
    }

    fn update_stream_stats(&mut self, stream_id: String, bytes_sent: u64, bytes_received: u64) {
        if let Some((sent, received)) = self.stream_stats.get_mut(&stream_id) {
            *sent += bytes_sent;
            *received += bytes_received;
        }
    }

    fn get_stream_stats(&self, stream_id: String) -> Option<(u64, u64)> {
        self.stream_stats.get(&stream_id).copied()
    }

    fn get_all_stream_stats(&self) -> HashMap<String, (u64, u64)> {
        self.stream_stats.clone()
    }

    fn get_protocol_handlers(&self) -> HashMap<String, String> {
        self.protocol_handlers.clone()
    }

    fn get_total_stats(&self) -> (u64, u64, usize) {
        let total_sent: u64 = self.stream_stats.values().map(|(sent, _)| sent).sum();
        let total_received: u64 = self.stream_stats.values().map(|(_, received)| received).sum();
        let total_streams = self.stream_stats.len();
        (total_sent, total_received, total_streams)
    }

    fn clear_all_streams(&mut self) {
        self.active_streams.clear();
        self.stream_stats.clear();
    }

    fn get_protocol_count(&self) -> usize {
        self.protocol_handlers.len()
    }
}