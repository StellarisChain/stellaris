from kytan import KytanClient, KytanServer
from kytan.kytan import KytanBase # dumb way to steal the KytanBase Class
from util.jsonreader import read_json_from_namespace

class KytanController:
    def __init__(self):
        self.client: KytanClient = None
        self.server: KytanServer = None
        self.config: dict = read_json_from_namespace("config.kytan") or {}

    def get_client(self) -> KytanClient:
        return self.client
    def set_client(self, client: KytanClient):
        self.client = client
    def get_server(self) -> KytanServer:
        return self.server
    def set_server(self, server: KytanServer):
        self.server = server

kytan_controller: KytanController = None

def get_kytan_controller() -> KytanController:
    return kytan_controller

def set_kytan_controller(controller: KytanController):
    global kytan_controller
    if not isinstance(controller, KytanController):
        raise TypeError("Expected an instance of KytanController")
    kytan_controller = controller