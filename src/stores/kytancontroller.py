from kytan import KytanClient, KytanServer
from kytan.kytan import KytanBase # dumb way to steal the KytanBase Class
from util.jsonreader import read_json_from_namespace
from util.filereader import file_to_str

class KytanController:
    def __init__(self):
        self.client: KytanClient = None
        self.server: KytanServer = None
        self.config: dict = read_json_from_namespace("config.kytan") or {}
        
    def serve(self):
        server_config: dict = self.config.get("server", {})
        if self.server:
            self.server.serve(
                port=server_config.get("port", 9527),
                bind=server_config.get("host", "0.0.0.0"),
                dns=server_config.get("dns", None),
                key=file_to_str(server_config.get("key_file")) or ""
            )

    # Methods
    def get_client(self) -> KytanClient:
        return self.client
    def set_client(self, client: KytanClient):
        self.client = client
    def get_server(self) -> KytanServer:
        return self.server
    def set_server(self, server: KytanServer):
        self.server = server
    def get_config(self) -> dict:
        return self.config
    def set_config(self, config: dict):
        self.config = config

kytan_controller: KytanController = None

def get_kytan_controller() -> KytanController:
    return kytan_controller

def set_kytan_controller(controller: KytanController):
    global kytan_controller
    if not isinstance(controller, KytanController):
        raise TypeError("Expected an instance of KytanController")
    kytan_controller = controller