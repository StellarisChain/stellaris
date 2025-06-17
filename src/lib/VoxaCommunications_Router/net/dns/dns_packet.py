import json
from typing import Any, Optional, Union
from lib.VoxaCommunications_Router.net.ssu.ssu_packet import SSUPacket
from schema.dns.a_record import ARecord
from schema.dns.dns_record import DNSRecord

DNS_PACKET_HEADER: str = "DNS"

class DNSPacket(SSUPacket):
    dns_dict: dict = {}

    def to_schema(self) -> Union[ARecord, DNSRecord]:
        """
        Convert the DNS packet to a schema object.
        Returns:
            ARecord or DNSRecord: The schema object representing the DNS packet.
        """
        self.remove_header()
        if not self.str_data:
            self.raw_to_str()
        self.dns_dict = json.loads(self.str_data) if self.str_data else {}
        
        match self.dns_dict.get("record_type"):
            case "A":
                return ARecord(**self.dns_dict)
            case _:
                return DNSRecord(**self.dns_dict)
    
    def from_schema(self, schema: Union[ARecord, DNSRecord]) -> None:
        """
        Convert a schema object to a DNS packet.
        Args:
            schema (ARecord or DNSRecord): The schema object to convert.
        """
        self.dns_dict = schema.dict()
        
        self.str_data = json.dumps(self.dns_dict)
        self.assemble_header(DNS_PACKET_HEADER)