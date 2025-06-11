from pydantic import BaseModel
from typing import Optional, Any
from util.logging import log

class RoutingMap(BaseModel):
    """
    Represents a routing map for the Voxa Communications Router.
    This class is used to define the routing structure and rules for communication.
    """
    routes: dict = {} # Will be populated from routing.route, each route has a "child-route" and each "child-route" has one aswell
    
    def get_nth_child_route(self, n: int) -> Optional[Any]:
        """
        Get the nth child route by traversing the nested "child-route" structure.
        
        Args:
            n (int): The index of the child route to retrieve (0-based)
            
        Returns:
            Optional[Any]: The nth child route if it exists, None otherwise
        """
        if not self.routes or n < 0:
            return None
        
        current_route = self.routes
        for i in range(n + 1):
            if "child_route" not in current_route:
                return None
            current_route = current_route["child_route"]
            if not current_route:
                return None
                
        return current_route
    
    def get_total_children(self) -> int:
        """
        Get the total number of child routes by traversing the nested "child_route" structure.
        **Count starts at 0**
        
        Returns:
            int: The total number of child routes in the routing chain
        """
        logger = log()
        if not self.routes:
            logger.warning("No routes defined in the routing map.")
            return 0
            
        count = 0
        current_route = self.routes
        
        while "child_route" in current_route and current_route["child_route"]:
            count += 1
            current_route = current_route["child_route"]
            
        return count