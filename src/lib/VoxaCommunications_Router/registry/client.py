import requests
from typing import Optional

class RegistryClient:
    def __init__(self, client_type: str = "relay" | "node" | "user" | "other", registry_url: str = "https://voxa-registry.connor33341.dev/", api_version: str = "v1", credentials: Optional[dict] = None):
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
    
    def login(self):
        if self.credentials != {} or None:
            request = requests.post(
                f"{self.base_url}login",
                json={
                    "email": self.credentials["email"],
                    "password": self.credentials["password"],
                    #"token": self.credentials["token"], # Cannot use tokens yet
                    "code": self.credentials["code"]
                }
            )
            if request.status_code == 200:
                response = request.json()
                self.session_token = response.get("token", "")
                return True
            else:
                print(f"Login failed: {request.text}")
                return False