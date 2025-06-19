use pyo3::prelude::*;
use libp2p::{
    noise, yamux, ping, identify,
    swarm::{SwarmEvent, Swarm},
    PeerId, Multiaddr, Transport,
};
use libp2p_swarm::NetworkBehaviour;
use multiaddr::Error as MultiaddrError;
use std::sync::{Arc, Mutex};
use futures::stream::StreamExt;

#[derive(NetworkBehaviour)]
struct Behaviour {
    ping: ping::Behaviour,
    identify: identify::Behaviour,
}

#[pyclass]
struct Libp2pNode {
    swarm: Arc<Mutex<Option<Swarm<Behaviour>>>>,
}

#[pymethods]
impl Libp2pNode {
    #[new]
    fn new() -> PyResult<Self> {
        let local_key = libp2p::identity::Keypair::generate_ed25519();
        let local_peer_id = PeerId::from(local_key.public());

        let transport = libp2p::tcp::async_io::Transport::new(libp2p::tcp::Config::default().nodelay(true))
            .upgrade(libp2p::core::upgrade::Version::V1)
            .authenticate(noise::Config::new(&local_key).unwrap())
            .multiplex(yamux::Config::default())
            .boxed();

        let behaviour = Behaviour {
            ping: ping::Behaviour::new(ping::Config::new()),
            identify: identify::Behaviour::new(identify::Config::new(
                "/ipfs/0.1.0".into(),
                local_key.public(),
            )),
        };

        let swarm = Swarm::new(transport, behaviour, local_peer_id, libp2p::swarm::Config::with_async_std_executor());

        Ok(Libp2pNode {
            swarm: Arc::new(Mutex::new(Some(swarm))),
        })
    }

    fn listen_on(&self, addr: String) -> PyResult<()> {
        let addr: Multiaddr = addr.parse()
            .map_err(|e: MultiaddrError| PyErr::new::<pyo3::exceptions::PyValueError, _>(e.to_string()))?;
        let swarm = self.swarm.clone();
        
        if let Some(ref mut swarm) = swarm.lock().unwrap().as_mut() {
            swarm.listen_on(addr)
                .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;
        }
        Ok(())
    }

    fn dial(&self, peer_addr: String) -> PyResult<()> {
        let addr: Multiaddr = peer_addr.parse()
            .map_err(|e: MultiaddrError| PyErr::new::<pyo3::exceptions::PyValueError, _>(e.to_string()))?;
        let swarm = self.swarm.clone();
        
        if let Some(ref mut swarm) = swarm.lock().unwrap().as_mut() {
            swarm.dial(addr)
                .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;
        }
        Ok(())
    }

    fn get_local_peer_id(&self) -> PyResult<String> {
        let swarm = self.swarm.lock().unwrap();
        if let Some(ref swarm) = swarm.as_ref() {
            Ok(swarm.local_peer_id().to_string())
        } else {
            Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Swarm not initialized"))
        }
    }

    fn run_event_loop(&self) -> PyResult<()> {
        let swarm = self.swarm.clone();
        let rt = tokio::runtime::Runtime::new().unwrap();
        
        rt.block_on(async {
            if let Some(mut swarm) = swarm.lock().unwrap().take() {
                loop {
                    match swarm.select_next_some().await {
                        SwarmEvent::Behaviour(event) => {
                            match event {
                                BehaviourEvent::Ping(ping::Event { peer, result, .. }) => {
                                    println!("Ping event from {}: {:?}", peer, result);
                                }
                                BehaviourEvent::Identify(identify::Event::Received { peer_id, info, .. }) => {
                                    println!("Identify event from {}: {:?}", peer_id, info.protocol_version);
                                }
                                _ => {}
                            }
                        }
                        SwarmEvent::NewListenAddr { address, .. } => {
                            println!("Listening on {}", address);
                        }
                        SwarmEvent::ConnectionEstablished { peer_id, .. } => {
                            println!("Connected to {}", peer_id);
                        }
                        SwarmEvent::ConnectionClosed { peer_id, .. } => {
                            println!("Disconnected from {}", peer_id);
                        }
                        _ => {}
                    }
                }
            }
        });
        
        Ok(())
    }
}

#[pymodule]
fn pylibp2p(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<Libp2pNode>()?;
    Ok(())
}