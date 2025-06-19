pub mod protocols;
pub mod transport;
pub mod crypto;
pub mod discovery;
pub mod storage;

use pyo3::prelude::*;
use libp2p::{
    swarm::{Swarm, NetworkBehaviour, SwarmEvent as LibP2PSwarmEvent},
    PeerId, Multiaddr, Transport,
    core::upgrade::Version,
    identity::Keypair,
    StreamProtocol,
};
use libp2p_noise as noise;
use libp2p_yamux as yamux;
use libp2p_ping as ping;
use libp2p_identify as identify;
use libp2p_kad::{self as kad, store::MemoryStore};
use libp2p_gossipsub as gossipsub;
use libp2p_request_response as request_response;
use libp2p_mdns as mdns;
use libp2p_tcp as tcp;
use libp2p_websocket as websocket;
use libp2p_dcutr as dcutr;
use libp2p_autonat as autonat;
use std::sync::{Arc, Mutex};
use std::collections::HashMap;
use futures::prelude::*;
use tokio::runtime::Runtime;
use std::time::Duration;
use serde::{Serialize, Deserialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GenericProtocol(String);

impl AsRef<[u8]> for GenericProtocol {
    fn as_ref(&self) -> &[u8] {
        self.0.as_bytes()
    }
}

impl From<String> for GenericProtocol {
    fn from(s: String) -> Self {
        GenericProtocol(s)
    }
}

#[derive(Clone, Default)]
pub struct GenericCodec;

impl request_response::Codec for GenericCodec {
    type Protocol = StreamProtocol;
    type Request = Vec<u8>;
    type Response = Vec<u8>;

    async fn read_request<T>(
        &mut self,
        _protocol: &Self::Protocol,
        io: &mut T,
    ) -> std::io::Result<Self::Request>
    where
        T: AsyncRead + Unpin + Send,
    {
        use futures::io::AsyncReadExt;
        let mut length_bytes = [0u8; 4];
        io.read_exact(&mut length_bytes).await?;
        let length = u32::from_be_bytes(length_bytes) as usize;
        
        if length > 1024 * 1024 { // 1MB limit
            return Err(std::io::Error::new(
                std::io::ErrorKind::InvalidData,
                "Message too large"
            ));
        }
        
        let mut buffer = vec![0u8; length];
        io.read_exact(&mut buffer).await?;
        Ok(buffer)
    }

    async fn read_response<T>(
        &mut self,
        protocol: &Self::Protocol,
        io: &mut T,
    ) -> std::io::Result<Self::Response>
    where
        T: AsyncRead + Unpin + Send,
    {
        self.read_request(protocol, io).await
    }

    async fn write_request<T>(
        &mut self,
        _protocol: &Self::Protocol,
        io: &mut T,
        req: Self::Request,
    ) -> std::io::Result<()>
    where
        T: AsyncWrite + Unpin + Send,
    {
        use futures::io::AsyncWriteExt;
        let length = req.len() as u32;
        io.write_all(&length.to_be_bytes()).await?;
        io.write_all(&req).await?;
        io.flush().await?;
        Ok(())
    }

    async fn write_response<T>(
        &mut self,
        protocol: &Self::Protocol,
        io: &mut T,
        res: Self::Response,
    ) -> std::io::Result<()>
    where
        T: AsyncWrite + Unpin + Send,
    {
        self.write_request(protocol, io, res).await
    }
}

#[pyclass]
#[derive(Debug, Clone)]
pub struct CustomSwarmEvent {
    #[pyo3(get)]
    pub event_type: String,
    #[pyo3(get)]
    pub peer_id: Option<String>,
    #[pyo3(get)]
    pub data: Option<Vec<u8>>,
    #[pyo3(get)]
    pub address: Option<String>,
    #[pyo3(get)]
    pub topic: Option<String>,
}

#[derive(NetworkBehaviour)]
struct ComprehensiveBehaviour {
    ping: ping::Behaviour,
    identify: identify::Behaviour,
    kademlia: kad::Behaviour<MemoryStore>,
    gossipsub: gossipsub::Behaviour,
    request_response: request_response::Behaviour<GenericCodec>,
    mdns: mdns::async_io::Behaviour,
    dcutr: dcutr::Behaviour,
    autonat: autonat::Behaviour,
}

#[pyclass]
pub struct Libp2pNode {
    swarm: Arc<Mutex<Option<Swarm<ComprehensiveBehaviour>>>>,
    local_peer_id: PeerId,
    runtime: Arc<Runtime>,
    event_queue: Arc<Mutex<Vec<CustomSwarmEvent>>>,
    connection_stats: Arc<Mutex<HashMap<String, u64>>>,
    running: Arc<Mutex<bool>>,
}

#[pymethods]
impl Libp2pNode {
    #[new]
    fn new() -> PyResult<Self> {
        let local_key = Keypair::generate_ed25519();
        let local_peer_id = PeerId::from(local_key.public());

        // Create runtime
        let runtime = Runtime::new()
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;

        // Create transport with multiple options
        let tcp_transport = tcp::async_io::Transport::new(tcp::Config::default().nodelay(true));
        
        // Add WebSocket transport
        let ws_tcp_transport = websocket::WsConfig::new(tcp::async_io::Transport::new(tcp::Config::default()));
        
        // Combine transports
        let transport = tcp_transport
            .or_transport(ws_tcp_transport)
            .upgrade(Version::V1)
            .authenticate(noise::Config::new(&local_key).unwrap())
            .multiplex(yamux::Config::default())
            .timeout(Duration::from_secs(20))
            .boxed();

        // Create gossipsub config with proper message ID function
        let gossipsub_config = gossipsub::ConfigBuilder::default()
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
            .build()
            .expect("Valid config");

        // Create Kademlia config
        let mut kad_config = kad::Config::default();
        kad_config.set_query_timeout(Duration::from_secs(60));
        kad_config.set_replication_factor(20.try_into().unwrap());

        // Create behaviours
        let behaviour = ComprehensiveBehaviour {
            ping: ping::Behaviour::new(ping::Config::new().with_interval(Duration::from_secs(30))),
            identify: identify::Behaviour::new(identify::Config::new("/voxa/1.0.0".to_string(), local_key.public())),
            kademlia: kad::Behaviour::with_config(local_peer_id, MemoryStore::new(local_peer_id), kad_config),
            gossipsub: gossipsub::Behaviour::new(
                gossipsub::MessageAuthenticity::Signed(local_key.clone()),
                gossipsub_config
            ).unwrap(),
            mdns: mdns::async_io::Behaviour::new(mdns::Config::default(), local_peer_id)
                .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?,
            dcutr: dcutr::Behaviour::new(local_peer_id),
            autonat: autonat::Behaviour::new(local_peer_id, autonat::Config::default()),
            request_response: request_response::Behaviour::new(
                [(StreamProtocol::new("/voxa/req-resp/1.0.0"), request_response::ProtocolSupport::Full)],
                request_response::Config::default()
            ),
        };

        let swarm_config = libp2p::swarm::Config::with_tokio_executor()
            .with_idle_connection_timeout(Duration::from_secs(60));

        let swarm = Swarm::new(transport, behaviour, local_peer_id, swarm_config);

        Ok(Libp2pNode {
            swarm: Arc::new(Mutex::new(Some(swarm))),
            local_peer_id,
            runtime: Arc::new(runtime),
            event_queue: Arc::new(Mutex::new(Vec::new())),
            connection_stats: Arc::new(Mutex::new(HashMap::new())),
            running: Arc::new(Mutex::new(false)),
        })
    }

    fn get_peer_id(&self) -> String {
        self.local_peer_id.to_string()
    }

    fn start_listening(&self, address: String) -> PyResult<()> {
        let addr: Multiaddr = address.parse()
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("Invalid address: {}", e)))?;
        
        if let Ok(mut swarm_guard) = self.swarm.lock() {
            if let Some(ref mut swarm) = *swarm_guard {
                swarm.listen_on(addr)
                    .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;
            }
        }
        Ok(())
    }

    fn dial(&self, address: String) -> PyResult<()> {
        let addr: Multiaddr = address.parse()
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("Invalid address: {}", e)))?;
        
        if let Ok(mut swarm_guard) = self.swarm.lock() {
            if let Some(ref mut swarm) = *swarm_guard {
                swarm.dial(addr)
                    .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;
            }
        }
        Ok(())
    }

    fn publish_gossip(&self, topic: String, data: Vec<u8>) -> PyResult<()> {
        if let Ok(mut swarm_guard) = self.swarm.lock() {
            if let Some(ref mut swarm) = *swarm_guard {
                let topic = gossipsub::IdentTopic::new(topic);
                swarm.behaviour_mut().gossipsub
                    .publish(topic, data)
                    .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;
            }
        }
        Ok(())
    }

    fn subscribe_gossip(&self, topic: String) -> PyResult<()> {
        if let Ok(mut swarm_guard) = self.swarm.lock() {
            if let Some(ref mut swarm) = *swarm_guard {
                let topic = gossipsub::IdentTopic::new(topic);
                swarm.behaviour_mut().gossipsub
                    .subscribe(&topic)
                    .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;
            }
        }
        Ok(())
    }

    fn unsubscribe_gossip(&self, topic: String) -> PyResult<()> {
        if let Ok(mut swarm_guard) = self.swarm.lock() {
            if let Some(ref mut swarm) = *swarm_guard {
                let topic = gossipsub::IdentTopic::new(topic);
                let result = swarm.behaviour_mut().gossipsub.unsubscribe(&topic);
                if !result {
                    return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Failed to unsubscribe from topic"));
                }
            }
        }
        Ok(())
    }

    fn send_request(&self, peer_id: String, data: Vec<u8>) -> PyResult<()> {
        let peer: PeerId = peer_id.parse()
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("Invalid peer ID: {}", e)))?;
        
        if let Ok(mut swarm_guard) = self.swarm.lock() {
            if let Some(ref mut swarm) = *swarm_guard {
                swarm.behaviour_mut().request_response.send_request(&peer, data);
            }
        }
        Ok(())
    }

    fn add_address(&self, peer_id: String, address: String) -> PyResult<()> {
        let peer: PeerId = peer_id.parse()
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("Invalid peer ID: {}", e)))?;
        let addr: Multiaddr = address.parse()
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("Invalid address: {}", e)))?;
        
        if let Ok(mut swarm_guard) = self.swarm.lock() {
            if let Some(ref mut swarm) = *swarm_guard {
                swarm.behaviour_mut().kademlia.add_address(&peer, addr);
            }
        }
        Ok(())
    }

    fn bootstrap(&self) -> PyResult<()> {
        if let Ok(mut swarm_guard) = self.swarm.lock() {
            if let Some(ref mut swarm) = *swarm_guard {
                match swarm.behaviour_mut().kademlia.bootstrap() {
                    Ok(_) => Ok(()),
                    Err(e) => Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string())),
                }
            } else {
                Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Swarm not initialized"))
            }
        } else {
            Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Failed to acquire swarm lock"))
        }
    }

    fn get_connected_peers(&self) -> Vec<String> {
        if let Ok(swarm_guard) = self.swarm.lock() {
            if let Some(ref swarm) = *swarm_guard {
                return swarm.connected_peers().map(|p| p.to_string()).collect();
            }
        }
        vec![]
    }

    fn get_listeners(&self) -> Vec<String> {
        if let Ok(swarm_guard) = self.swarm.lock() {
            if let Some(ref swarm) = *swarm_guard {
                return swarm.listeners().map(|addr| addr.to_string()).collect();
            }
        }
        vec![]
    }

    fn get_external_addresses(&self) -> Vec<String> {
        if let Ok(swarm_guard) = self.swarm.lock() {
            if let Some(ref swarm) = *swarm_guard {
                return swarm.external_addresses().map(|addr| addr.to_string()).collect();
            }
        }
        vec![]
    }

    fn start_event_loop(&self) -> PyResult<()> {
        let swarm_arc = self.swarm.clone();
        let event_queue_arc = self.event_queue.clone();
        let running_arc = self.running.clone();
        let connection_stats_arc = self.connection_stats.clone();

        if let Ok(mut running) = running_arc.lock() {
            if *running {
                return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Event loop already running"));
            }
            *running = true;
        }

        // Move the swarm out of the Arc<Mutex<>> for the duration of the event loop
        let swarm = {
            if let Ok(mut swarm_guard) = swarm_arc.lock() {
                swarm_guard.take()
            } else {
                return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Failed to acquire swarm lock"));
            }
        };

        if let Some(mut swarm) = swarm {
            self.runtime.spawn(async move {
                loop {
                    // Check if we should stop
                    let should_stop = {
                        if let Ok(running) = running_arc.lock() {
                            !*running
                        } else {
                            true // If we can't check, assume we should stop
                        }
                    };

                    if should_stop {
                        break;
                    }

                    match swarm.select_next_some().await {
                        LibP2PSwarmEvent::NewListenAddr { address, .. } => {
                            if let Ok(mut queue) = event_queue_arc.lock() {
                                queue.push(CustomSwarmEvent {
                                    event_type: "NewListenAddr".to_string(),
                                    peer_id: None,
                                    data: None,
                                    address: Some(address.to_string()),
                                    topic: None,
                                });
                            }
                        },
                        LibP2PSwarmEvent::ConnectionEstablished { peer_id, endpoint, .. } => {
                            if let Ok(mut stats) = connection_stats_arc.lock() {
                                *stats.entry(peer_id.to_string()).or_insert(0) += 1;
                            }
                            if let Ok(mut queue) = event_queue_arc.lock() {
                                queue.push(CustomSwarmEvent {
                                    event_type: "ConnectionEstablished".to_string(),
                                    peer_id: Some(peer_id.to_string()),
                                    data: None,
                                    address: Some(endpoint.get_remote_address().to_string()),
                                    topic: None,
                                });
                            }
                        },
                        LibP2PSwarmEvent::ConnectionClosed { peer_id, cause, .. } => {
                            if let Ok(mut queue) = event_queue_arc.lock() {
                                queue.push(CustomSwarmEvent {
                                    event_type: "ConnectionClosed".to_string(),
                                    peer_id: Some(peer_id.to_string()),
                                    data: Some(format!("{:?}", cause).into_bytes()),
                                    address: None,
                                    topic: None,
                                });
                            }
                        },
                        LibP2PSwarmEvent::Behaviour(event) => {
                            // Handle specific behaviour events
                            if let Ok(mut queue) = event_queue_arc.lock() {
                                queue.push(CustomSwarmEvent {
                                    event_type: "BehaviourEvent".to_string(),
                                    peer_id: None,
                                    data: Some(format!("{:?}", event).into_bytes()),
                                    address: None,
                                    topic: None,
                                });
                            }
                        },
                        _ => {}
                    }

                    // Limit event queue size
                    if let Ok(mut queue) = event_queue_arc.lock() {
                        if queue.len() > 1000 {
                            queue.drain(0..500); // Remove oldest half
                        }
                    }
                }
                
                // Put swarm back when done
                if let Ok(mut swarm_guard) = swarm_arc.lock() {
                    *swarm_guard = Some(swarm);
                }
            });
        } else {
            return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("No swarm available"));
        }

        Ok(())
    }

    fn stop_event_loop(&self) -> PyResult<()> {
        if let Ok(mut running) = self.running.lock() {
            *running = false;
        }
        Ok(())
    }

    fn get_events(&self) -> Vec<CustomSwarmEvent> {
        if let Ok(mut queue) = self.event_queue.lock() {
            let events = queue.clone();
            queue.clear();
            events
        } else {
            vec![]
        }
    }

    fn get_connection_stats(&self) -> HashMap<String, u64> {
        if let Ok(stats) = self.connection_stats.lock() {
            stats.clone()
        } else {
            HashMap::new()
        }
    }

    fn is_running(&self) -> bool {
        if let Ok(running) = self.running.lock() {
            *running
        } else {
            false
        }
    }

    fn ping_peer(&self, peer_id: String) -> PyResult<()> {
        let peer: PeerId = peer_id.parse()
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("Invalid peer ID: {}", e)))?;
        
        if let Ok(mut swarm_guard) = self.swarm.lock() {
            if let Some(ref mut swarm) = *swarm_guard {
                // Ping is automatic, but we can trigger identify
                swarm.behaviour_mut().identify.push(std::iter::once(peer));
            }
        }
        Ok(())
    }

    fn get_network_info(&self) -> HashMap<String, String> {
        let mut info = HashMap::new();
        info.insert("peer_id".to_string(), self.local_peer_id.to_string());
        info.insert("listeners".to_string(), self.get_listeners().len().to_string());
        info.insert("connected_peers".to_string(), self.get_connected_peers().len().to_string());
        info.insert("external_addresses".to_string(), self.get_external_addresses().len().to_string());
        info.insert("running".to_string(), self.is_running().to_string());
        info
    }
}

#[pymodule]
fn pylibp2p(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<Libp2pNode>()?;
    m.add_class::<CustomSwarmEvent>()?;
    m.add_class::<crate::protocols::GossipsubManager>()?;
    m.add_class::<crate::protocols::FloodsubManager>()?;
    m.add_class::<crate::protocols::RequestResponseManager>()?;
    m.add_class::<crate::protocols::RelayManager>()?;
    m.add_class::<crate::protocols::StreamManager>()?;
    m.add_class::<crate::transport::TransportManager>()?;
    m.add_class::<crate::transport::MultiaddrBuilder>()?;
    m.add_class::<crate::crypto::KeypairManager>()?;
    m.add_class::<crate::crypto::HashManager>()?;
    m.add_class::<crate::discovery::MdnsManager>()?;
    m.add_class::<crate::discovery::KademliaManager>()?;
    m.add_class::<crate::discovery::AutonatManager>()?;
    m.add_class::<crate::discovery::RendezvousManager>()?;
    m.add_class::<crate::discovery::IdentifyManager>()?;
    m.add_class::<crate::discovery::DiscoveredPeer>()?;
    m.add_class::<crate::storage::MemoryStorage>()?;
    m.add_class::<crate::storage::PersistentStorage>()?;
    Ok(())
}