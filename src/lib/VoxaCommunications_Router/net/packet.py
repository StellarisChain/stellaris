from pydantic import BaseModel
from typing import Optional, Union

# Unencrypted plaintext packet structure
class Packet(BaseModel):
    raw_data: Optional[bytes] = None # UTF-8 encoded string data
    str_data: Optional[str] = None
    addr: Optional[Union[tuple[str, int], str]] = None # Either a tuple of (IP, port) or a string representing the address

    # Set the addr to a tuple
    def correct_addr(self) -> None:
        if isinstance(self.addr, str):
            parts: list[str] = self.addr.split(":")
            if len(parts) == 2:
                self.addr = (parts[0], int(parts[1]))
            else:
                # If the address dosent have a port, set a default port
                self.addr = (self.addr, 9000) # TODO: Fix this hardcoded port
        elif isinstance(self.addr, tuple) and len(self.addr) == 2:
            ip, port = self.addr
            if not isinstance(port, int):
                port = int(port)  # Ensure port is an integer
            self.addr = (ip, port)
        else:
            raise ValueError("Address must be a tuple of (IP, port) or a string in 'IP:port' format.")
    
    def raw_to_str(self):
        if self.raw_data:
            self.str_data = self.raw_data.decode('utf-8', errors='ignore')
    
    def str_to_raw(self):
        if self.str_data:
            self.raw_data = self.str_data.encode('utf-8', errors='ignore')
    
    def has_header(self, header: Optional[str] = "") -> bool:
        if not self.str_data:
            self.raw_to_str()
        if not header:
            return False
        return self.str_data.startswith(header)
    
    def assemble_header(self, header: str):
        if not self.str_data:
            self.raw_to_str()
        if not self.str_data.startswith(header):
            self.str_data = f"{header} {self.str_data}"
        self.str_to_raw()
    
    def get_header(self) -> Optional[str]:
        if not self.str_data:
            self.raw_to_str()
        split: list[str] = self.str_data.split(" ")
        if len(split) > 0:
            return split[0]
        
    def remove_header(self):
        if not self.str_data:
            self.raw_to_str()
        split: list[str] = self.str_data.split(" ", 1)
        if len(split) > 1:
            self.str_data = split[1]
        else:
            self.str_data = ""
        self.str_to_raw()

    def __str__(self):
        return f"Packet(addr={self.addr}, str_data={self.str_data}, raw_data={self.raw_data})"