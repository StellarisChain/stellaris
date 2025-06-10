import requests
import uuid
from typing import Optional

class RegistryClient:
    def __init__(self, client_type: str = "relay", registry_url: str = "https://voxa-registry.connor33341.dev/", api_version: str = "v1", credentials: Optional[dict] = None):
        self.client_type = client_type
        self.registry_url = registry_url
        self.api_version = api_version
        self.base_url = f"{self.registry_url}/api/{self.api_version}/"
        self.credentials = credentials or {
            "email": None,
            "password": None,
            "token": None,
            "code": None
        }
        self.session_token = ""
        self.ids = {
            "node_id": None,
            "user_id": None,
            "relay_id": None
        }
        self.node_ip = None

    def set_credentials(self, email: Optional[str] = None, password: Optional[str] = None, token: Optional[str] = None, code: Optional[str] = None):
        """
        Set the credentials for the client.

        Args:
            email (str): The email address of the user.
            password (str): The password of the user.
            token (str): The authentication token.
            code (str): The verification code.
        """
        if email is not None:
            self.credentials["email"] = email
        if password is not None:
            self.credentials["password"] = password
        if token is not None:
            self.credentials["token"] = token
        if code is not None:
            self.credentials["code"] = code
    
    def register_node(self, callsign: str, node_ip: Optional[str] = None, node_type: str = "testnet"):
        request_json = {
            "name": callsign,
            "type": node_type
        }
        if node_ip is not None:
            request_json["ip"] = node_ip
        if (self.credentials != {} or None) and self.session_token != "":
            request = requests.post(
                f"{self.base_url}register_node",
                json = request_json,
                headers = {
                    "Authorization": f"Bearer {self.session_token}",
                    "Content-Type": "application/json"
                }
            )
            if request.status_code == 201:
                response: dict = request.json()
                self.ids["node_id"] = response.get("node_id", "")
                self.ids["user_id"] = response.get("registered", "")
                self.node_ip = response.get("node_ip", node_ip)
                return True
            else:
                print(f"Login failed: {request.text}")
                return False
    
    def login(self):
        if self.credentials != {} or None:
            request = requests.post(
                f"{self.base_url}login",
                json = {
                    "email": self.credentials["email"],
                    "password": self.credentials["password"],
                    #"token": self.credentials["token"], # Cannot use tokens yet
                    "code": self.credentials["code"]
                },
            )
            if request.status_code == 200:
                response: dict = request.json()
                self.session_token = response.get("token", "")
                self.ids["user_id"] = response.get("user_id", "")
                return True
            else:
                print(f"Login failed: {request.text}")
                return False
            
    def register(self, name: Optional[str] = None) -> None | bool:
        if self.credentials != {} or None:
            if not name:
                name = f"voxa-{self.client_type}-{str(uuid.uuid4())}"
            request = requests.post(
                f"{self.base_url}register",
                json = {
                    "email": self.credentials["email"],
                    "password": self.credentials["password"],
                    "name": name # technically required, but it dosent do anything at the moment
                },
            )
            if request.status_code == 201:
                response: dict = request.json()
                self.ids["user_id"] = response.get("user_id", "")
                return True
            else:
                print(f"Registration failed: {request.text}")
                return False