from pydantic import BaseModel
from typing import Optional

# Unencrypted plaintext packet structure
class Packet(BaseModel):
    raw_data: Optional[bytes] = None # UTF-8 encoded string data
    str_data: Optional[str] = None
    addr: Optional[tuple[str, int]] = None

    def raw_to_str(self):
        if self.raw_data:
            self.str_data = self.raw_data.decode('utf-8', errors='ignore')
    
    def str_to_raw(self):
        if self.str_data:
            self.raw_data = self.str_data.encode('utf-8', errors='ignore')
    
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