use pyo3::prelude::*;
use libp2p::{Multiaddr, PeerId};
use libp2p_tcp as tcp;
use libp2p_quic as quic;
use std::collections::HashMap;
use std::net::{Ipv4Addr, Ipv6Addr};

#[pyclass]
pub struct TransportManager {
    tcp_config: tcp::Config,
    quic_config: Option<quic::Config>,
    websocket_enabled: bool,
    dns_enabled: bool,
    transport_stats: HashMap<String, u64>,
    connection_limits: HashMap<String, u32>,
    bandwidth_stats: HashMap<String, (u64, u64)>, // (bytes_sent, bytes_received)
}

#[pymethods]
impl TransportManager {
    #[new]
    fn new() -> Self {
        Self {
            tcp_config: tcp::Config::default(),
            quic_config: None,
            websocket_enabled: false,
            dns_enabled: false,
            transport_stats: HashMap::new(),
            connection_limits: HashMap::new(),
            bandwidth_stats: HashMap::new(),
        }
    }

    fn enable_tcp(&mut self, nodelay: bool) -> PyResult<()> {
        self.tcp_config = tcp::Config::default().nodelay(nodelay);
        self.transport_stats.insert("tcp_enabled".to_string(), 1);
        Ok(())
    }

    fn enable_quic(&mut self, _keypair_bytes: Vec<u8>) -> PyResult<()> {
        // In a real implementation, you'd deserialize the keypair properly
        // This is a simplified version for demonstration
        let keypair = libp2p::identity::Keypair::generate_ed25519();
        self.quic_config = Some(quic::Config::new(&keypair));
        self.transport_stats.insert("quic_enabled".to_string(), 1);
        Ok(())
    }

    fn enable_websocket(&mut self) {
        self.websocket_enabled = true;
        self.transport_stats.insert("websocket_enabled".to_string(), 1);
    }

    fn enable_dns(&mut self) {
        self.dns_enabled = true;
        self.transport_stats.insert("dns_enabled".to_string(), 1);
    }

    fn disable_tcp(&mut self) {
        self.tcp_config = tcp::Config::default();
        self.transport_stats.remove("tcp_enabled");
    }

    fn disable_quic(&mut self) {
        self.quic_config = None;
        self.transport_stats.remove("quic_enabled");
    }

    fn disable_websocket(&mut self) {
        self.websocket_enabled = false;
        self.transport_stats.remove("websocket_enabled");
    }

    fn disable_dns(&mut self) {
        self.dns_enabled = false;
        self.transport_stats.remove("dns_enabled");
    }

    fn get_transport_info(&self) -> PyResult<HashMap<String, String>> {
        let mut info = HashMap::new();
        info.insert("tcp_enabled".to_string(), "true".to_string());
        info.insert("quic_enabled".to_string(), self.quic_config.is_some().to_string());
        info.insert("websocket_enabled".to_string(), self.websocket_enabled.to_string());
        info.insert("dns_enabled".to_string(), self.dns_enabled.to_string());
        
        if let Some(_config) = &self.quic_config {
            info.insert("quic_configured".to_string(), "true".to_string());
        }
        
        Ok(info)
    }

    #[pyo3(signature = (nodelay, keepalive=None))]
    fn set_tcp_config(&mut self, nodelay: bool, keepalive: Option<u64>) -> PyResult<()> {
        let config = tcp::Config::default().nodelay(nodelay);
        
        // Note: keepalive configuration is not directly available in the current libp2p-tcp version
        // This is stored for reference but not directly applied
        if let Some(keepalive_secs) = keepalive {
            self.transport_stats.insert("tcp_keepalive_secs".to_string(), keepalive_secs);
        }
        
        self.tcp_config = config;
        Ok(())
    }

    fn get_supported_protocols(&self) -> Vec<String> {
        let mut protocols = vec!["tcp".to_string()];
        
        if self.quic_config.is_some() {
            protocols.push("quic".to_string());
            protocols.push("quic-v1".to_string());
        }
        if self.websocket_enabled {
            protocols.push("websocket".to_string());
            protocols.push("ws".to_string());
            protocols.push("wss".to_string());
        }
        if self.dns_enabled {
            protocols.push("dns".to_string());
            protocols.push("dns4".to_string());
            protocols.push("dns6".to_string());
            protocols.push("dnsaddr".to_string());
        }
        
        protocols
    }

    fn update_stats(&mut self, transport_type: String, bytes_transferred: u64) {
        *self.transport_stats.entry(transport_type.clone()).or_insert(0) += bytes_transferred;
        
        // Update bandwidth stats
        let (sent, _) = self.bandwidth_stats.entry(transport_type).or_insert((0, 0));
        *sent += bytes_transferred;
    }

    fn update_bandwidth_stats(&mut self, transport_type: String, bytes_sent: u64, bytes_received: u64) {
        let (sent, received) = self.bandwidth_stats.entry(transport_type).or_insert((0, 0));
        *sent += bytes_sent;
        *received += bytes_received;
    }

    fn get_stats(&self) -> HashMap<String, u64> {
        self.transport_stats.clone()
    }

    fn get_bandwidth_stats(&self) -> HashMap<String, (u64, u64)> {
        self.bandwidth_stats.clone()
    }

    fn reset_stats(&mut self) {
        self.transport_stats.clear();
        self.bandwidth_stats.clear();
    }

    fn set_connection_limit(&mut self, transport_type: String, limit: u32) {
        self.connection_limits.insert(transport_type, limit);
    }

    fn get_connection_limit(&self, transport_type: String) -> Option<u32> {
        self.connection_limits.get(&transport_type).copied()
    }

    fn get_connection_limits(&self) -> HashMap<String, u32> {
        self.connection_limits.clone()
    }

    fn remove_connection_limit(&mut self, transport_type: String) -> bool {
        self.connection_limits.remove(&transport_type).is_some()
    }

    fn is_transport_enabled(&self, transport_type: String) -> bool {
        match transport_type.as_str() {
            "tcp" => true, // TCP is always enabled
            "quic" | "quic-v1" => self.quic_config.is_some(),
            "websocket" | "ws" | "wss" => self.websocket_enabled,
            "dns" | "dns4" | "dns6" | "dnsaddr" => self.dns_enabled,
            _ => false,
        }
    }

    fn get_transport_summary(&self) -> HashMap<String, String> {
        let mut summary = HashMap::new();
        let supported = self.get_supported_protocols();
        summary.insert("supported_protocols".to_string(), supported.join(", "));
        summary.insert("protocol_count".to_string(), supported.len().to_string());
        summary.insert("has_quic".to_string(), self.quic_config.is_some().to_string());
        summary.insert("has_websocket".to_string(), self.websocket_enabled.to_string());
        summary.insert("has_dns".to_string(), self.dns_enabled.to_string());
        
        let total_bandwidth: u64 = self.bandwidth_stats.values().map(|(s, r)| s + r).sum();
        summary.insert("total_bandwidth_bytes".to_string(), total_bandwidth.to_string());
        
        summary
    }
}

#[pyclass]
pub struct MultiaddrBuilder {
    components: Vec<String>,
    validation_enabled: bool,
}

#[pymethods]
impl MultiaddrBuilder {
    #[new]
    fn new() -> Self {
        Self {
            components: Vec::new(),
            validation_enabled: true,
        }
    }

    fn enable_validation(&mut self, enabled: bool) {
        self.validation_enabled = enabled;
    }

    fn ip4(&mut self, ip: String) -> PyResult<()> {
        if self.validation_enabled {
            ip.parse::<Ipv4Addr>()
                .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("Invalid IPv4 address: {}", e)))?;
        }
        self.components.push(format!("/ip4/{}", ip));
        Ok(())
    }

    fn ip6(&mut self, ip: String) -> PyResult<()> {
        if self.validation_enabled {
            ip.parse::<Ipv6Addr>()
                .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("Invalid IPv6 address: {}", e)))?;
        }
        self.components.push(format!("/ip6/{}", ip));
        Ok(())
    }

    fn dns(&mut self, hostname: String) -> PyResult<()> {
        if self.validation_enabled && hostname.is_empty() {
            return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>("Hostname cannot be empty"));
        }
        self.components.push(format!("/dns/{}", hostname));
        Ok(())
    }

    fn dns4(&mut self, hostname: String) -> PyResult<()> {
        if self.validation_enabled && hostname.is_empty() {
            return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>("Hostname cannot be empty"));
        }
        self.components.push(format!("/dns4/{}", hostname));
        Ok(())
    }

    fn dns6(&mut self, hostname: String) -> PyResult<()> {
        if self.validation_enabled && hostname.is_empty() {
            return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>("Hostname cannot be empty"));
        }
        self.components.push(format!("/dns6/{}", hostname));
        Ok(())
    }

    fn dnsaddr(&mut self, hostname: String) -> PyResult<()> {
        if self.validation_enabled && hostname.is_empty() {
            return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>("Hostname cannot be empty"));
        }
        self.components.push(format!("/dnsaddr/{}", hostname));
        Ok(())
    }

    fn tcp(&mut self, port: u16) -> PyResult<()> {
        if self.validation_enabled && port == 0 {
            return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>("Port cannot be 0"));
        }
        self.components.push(format!("/tcp/{}", port));
        Ok(())
    }

    fn udp(&mut self, port: u16) -> PyResult<()> {
        if self.validation_enabled && port == 0 {
            return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>("Port cannot be 0"));
        }
        self.components.push(format!("/udp/{}", port));
        Ok(())
    }

    fn quic(&mut self) -> PyResult<()> {
        self.components.push("/quic".to_string());
        Ok(())
    }

    fn quic_v1(&mut self) -> PyResult<()> {
        self.components.push("/quic-v1".to_string());
        Ok(())
    }

    #[pyo3(signature = (path=None))]
    fn ws(&mut self, path: Option<String>) -> PyResult<()> {
        if let Some(path) = path {
            if self.validation_enabled && !path.starts_with('/') {
                return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>("WebSocket path must start with '/'"));
            }
            self.components.push(format!("/ws{}", path));
        } else {
            self.components.push("/ws".to_string());
        }
        Ok(())
    }

    #[pyo3(signature = (path=None))]
    fn wss(&mut self, path: Option<String>) -> PyResult<()> {
        if let Some(path) = path {
            if self.validation_enabled && !path.starts_with('/') {
                return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>("WebSocket Secure path must start with '/'"));
            }
            self.components.push(format!("/wss{}", path));
        } else {
            self.components.push("/wss".to_string());
        }
        Ok(())
    }

    fn p2p(&mut self, peer_id: String) -> PyResult<()> {
        if self.validation_enabled {
            peer_id.parse::<PeerId>()
                .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("Invalid peer ID: {}", e)))?;
        }
        self.components.push(format!("/p2p/{}", peer_id));
        Ok(())
    }

    fn memory(&mut self, port: u64) -> PyResult<()> {
        self.components.push(format!("/memory/{}", port));
        Ok(())
    }

    fn build(&self) -> PyResult<String> {
        if self.components.is_empty() {
            return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>("No components added"));
        }
        
        let addr_str = self.components.join("");
        
        // Validate the multiaddr by trying to parse it if validation is enabled
        if self.validation_enabled {
            addr_str.parse::<Multiaddr>()
                .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(e.to_string()))?;
        }
        
        Ok(addr_str)
    }

    fn build_without_validation(&self) -> String {
        self.components.join("")
    }

    fn clear(&mut self) {
        self.components.clear();
    }

    fn get_components(&self) -> Vec<String> {
        self.components.clone()
    }

    fn remove_last_component(&mut self) -> Option<String> {
        self.components.pop()
    }

    fn component_count(&self) -> usize {
        self.components.len()
    }

    fn has_component(&self, component_type: String) -> bool {
        self.components.iter().any(|c| c.contains(&format!("/{}/", component_type)) || c.starts_with(&format!("/{}", component_type)))
    }

    fn get_component_value(&self, component_type: String) -> Option<String> {
        for component in &self.components {
            if let Some(index) = component.find(&format!("/{}/", component_type)) {
                let start = index + component_type.len() + 2;
                return component.get(start..).map(|s| s.to_string());
            } else if component == &format!("/{}", component_type) {
                return Some(String::new()); // Component with no value
            }
        }
        None
    }

    fn replace_component(&mut self, component_type: String, new_value: String) -> bool {
        for component in &mut self.components {
            if component.contains(&format!("/{}/", component_type)) {
                *component = format!("/{}/{}", component_type, new_value);
                return true;
            } else if component == &format!("/{}", component_type) {
                *component = if new_value.is_empty() {
                    format!("/{}", component_type)
                } else {
                    format!("/{}/{}", component_type, new_value)
                };
                return true;
            }
        }
        false
    }

    fn validate(&self) -> PyResult<bool> {
        let addr_str = self.build_without_validation();
        match addr_str.parse::<Multiaddr>() {
            Ok(_) => Ok(true),
            Err(e) => Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(e.to_string())),
        }
    }
}