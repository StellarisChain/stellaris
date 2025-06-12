from pydantic import BaseModel
from typing import Optional, Any
from copy import deepcopy
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
        if not self.routes:
            return None
        
        current_route = self.routes
        for i in range(n):  # Fixed: changed from range(n + 1) to range(n)
            if "child_route" not in current_route:
                return None
            child_route = current_route["child_route"]
            if not child_route:  # Fixed: check child_route instead of current_route
                return None
            else:
                current_route = child_route
        
        if n < 0:
            return self.routes # ex. -1 which returns the root route
        
        # For n=0, we want the first child route
        if "child_route" not in current_route:
            return None
        
        # Return a deep copy to avoid circular references
        route_copy = deepcopy(current_route["child_route"])
        return route_copy
    
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
    
    def set_nth_child_route(self, n: int, route: dict | bytes) -> bool:
        """
        Set the nth child route by traversing the nested "child-route" structure.
        
        Args:
            n (int): The index of the child route to set (0-based)
            route (dict): The route to set at the nth position
        Returns:
            bool: True if the route was set successfully, False otherwise
        """
        if not self.routes or n < 0:
            return False
        
        current_route = self.routes
        for i in range(n):
            if "child_route" not in current_route:
                return False
            current_route = current_route["child_route"]
        
        current_route["child_route"] = route
        return True