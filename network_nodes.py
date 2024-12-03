# network_nodes.py

import uuid
from typing import Optional, Dict, List, Tuple

class Point:
    def __init__(self, lat: float, lon: float):
        self.lat = lat
        self.lon = lon

class Node(Point):
    def __init__(self, lat: float, lon: float, id: Optional[str] = None):
        super().__init__(lat, lon)
        self.id = id if id else str(uuid.uuid4())
        self.connections: List[Connection] = []
        self.icon_url = ""

    def connect(self, node: 'Node') -> 'Connection':
        return self._connect(node)

    def _connect(self, node: 'Node') -> 'Connection':
        connection = Connection(self, node)
        return connection

    def remove_connection(self, connection: 'Connection'):
        if connection in self.connections:
            self.connections.remove(connection)

class Connection:
    def __init__(self, start_node: Node, end_node: Node, id: Optional[str] = None):
        self.id = id if id else str(uuid.uuid4())
        self.start_node = start_node
        self.end_node = end_node
        self.selected = False
        
        self.start_node.connections.append(self)
        self.end_node.connections.append(self)

    def remove(self):
        self.start_node.remove_connection(self)
        self.end_node.remove_connection(self)

class OLTNode(Node):
    def __init__(self, lat: float, lon: float, id: Optional[str] = None):
        super().__init__(lat, lon, id)
        self.icon_url = "https://symbols.getvecta.com/stencil_37/6_mainframe.fb99fbaf71.svg"

    def connect(self, node: 'Node') -> 'Connection':
        if isinstance(node, OLTNode):
            raise ValueError("OLT nodes cannot connect with other OLT nodes.")
        return self._connect(node)

class ONUNode(Node):
    def __init__(self, lat: float, lon: float, id: Optional[str] = None, bandwidth: int = 0, traffic_proportions: Dict[int, float] = None):
        super().__init__(lat, lon, id)
        self.icon_url = "https://symbols.getvecta.com/stencil_37/7_router.dde201f0d4.svg"
        self.bandwidth = bandwidth
        self.olt_connection_ids: List[str] = []
        
        if traffic_proportions:
            self.traffic_proportions = traffic_proportions
        else:
            self.traffic_proportions = {1:0 ,2: 0.6, 3: 0.2, 4: 0.2}

    def connect(self, node: 'Node') -> 'Connection':
        if isinstance(node, ONUNode):
            raise ValueError("ONU nodes cannot connect with other ONU nodes.")
        return self._connect(node)

    
    def get_olt_connection_ids(self, node=None, visited=None):
        if visited is None and node is None:
            self.olt_connection_ids = []
            visited = set()
            node = self
       
        if node.id in visited:
            return False
        
        visited.add(node.id)
        for connection in node.connections:
            if isinstance(connection.end_node, OLTNode) or isinstance(connection.start_node, OLTNode):
                self.olt_connection_ids.append(connection.id)
                return True
            
            next_node = connection.end_node if connection.start_node == node else connection.start_node
            if len(next_node.connections) == 1:
                continue
            
            if self.get_olt_connection_ids(next_node, visited):
                self.olt_connection_ids.append(connection.id)
                return True
        return False

class SplitterNode(Node):
    def __init__(self, lat: float, lon: float, id: Optional[str] = None):
        super().__init__(lat, lon, id)
        self.icon_url = "https://symbols.getvecta.com/stencil_37/9_switch.a8945b4320.svg"