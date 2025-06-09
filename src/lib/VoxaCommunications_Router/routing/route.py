from typing import Optional, Union
from schema.RRISchema import RRISchema

class Route(RRISchema):
    child_route: Optional[dict] | RRISchema = None