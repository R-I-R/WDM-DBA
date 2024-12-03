import csv
from network_nodes import Node, Connection, OLTNode, ONUNode, SplitterNode
from typing import List, Tuple

def dump_network_to_csv(components, file_path: str):
    nodes = [comp for comp in components if isinstance(comp, Node)]
    connections = [comp for comp in components if isinstance(comp, Connection)]
    
    with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['ID', 'Type', 'Latitude', 'Longitude', 'Start Node', 'End Node', 'Bandwidth', 'T-Cont1', 'T-Cont2', 'T-Cont3', 'T-Cont4']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames, delimiter=';')
        writer.writeheader()

        for node in nodes:
            row = {
                'ID': node.id,
                'Type': node.__class__.__name__,
                'Latitude': node.lat,
                'Longitude': node.lon
            }
            if isinstance(node, ONUNode):
                row['Bandwidth'] = node.bandwidth
                row['T-Cont1'] = node.traffic_proportions[1]
                row['T-Cont2'] = node.traffic_proportions[2]
                row['T-Cont3'] = node.traffic_proportions[3]
                row['T-Cont4'] = node.traffic_proportions[4]
            writer.writerow(row)

        for connection in connections:
            writer.writerow({
                'ID': connection.id,
                'Type': 'Connection',
                'Start Node': connection.start_node.id,
                'End Node': connection.end_node.id
            })

def load_network_from_csv(file_path: str) -> dict[str, Node|Connection]:
    """
    Loads the network from a CSV file.

    Args:
        file_path (str): The path to the CSV file to read.

    Returns:
        Tuple[List[Node], List<Connection]]: A tuple containing the list of nodes and connections.
    """
    nodes = {}
    
    with open(file_path, 'r', newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile, delimiter=';')
        for row in reader:
            if row['Type'] in ['OLTNode', 'SplitterNode']:
                nodes[row['ID']] = globals()[row['Type']](lat=float(row['Latitude']), lon=float(row['Longitude']), id=row['ID'])
            elif row['Type'] == 'ONUNode':
                traffic_proportions = {1: float(row['T-Cont1']), 2: float(row['T-Cont2']), 3: float(row['T-Cont3']), 4: float(row['T-Cont4'])}
                nodes[row['ID']] = ONUNode(lat=float(row['Latitude']), lon=float(row['Longitude']), id=row['ID'], bandwidth=int(row['Bandwidth']), traffic_proportions=traffic_proportions)
            elif row['Type'] == 'Connection':
                nodes[row['ID']] = Connection(start_node=nodes[row['Start Node']], end_node=nodes[row['End Node']], id=row['ID'])

    return nodes

