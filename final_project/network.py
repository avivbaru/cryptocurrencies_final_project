from collections import defaultdict
from typing import Dict, List, Tuple
import LightningChannel


class Network:
    def __init__(self):
        self.nodes: List[LightningChannel.LightningNode] = list()
        self.edges: defaultdict[LightningChannel.LightningNode, List[LightningChannel.LightningNode]] = defaultdict(list)

    def add_node(self, value):
        self.nodes.append(value)

    def add_edge(self, from_node, to_node):
        self.edges[from_node].append(to_node)
        self.edges[to_node].append(from_node)
        channel = to_node.establish_channel(from_node, 10)
        from_node.add_money_to_channel(channel, 10)

    def get_edges_with_enough_capacity(self, amount_in_wei, capacity_map):
        return {from_node: [to_node for to_node in nodes if
                            capacity_map[(from_node, to_node)] > amount_in_wei]
                for from_node, nodes in self.edges.items()}


def generate_fee_map(edges, amount_in_wei):
    fees: Dict[Tuple[LightningChannel.LightningNode, LightningChannel.LightningNode], int] = {}
    for from_node in edges:
        for to_node in edges[from_node]:
            fees[(from_node, to_node)] = amount_in_wei * to_node.fee_percentage
    return fees


def generate_capacity_map(edges):
    capacity: Dict[Tuple[LightningChannel.LightningNode, LightningChannel.LightningNode], int] = {}
    for from_node, to_nodes in edges.items():
        for to_node in to_nodes:
            capacity[(from_node, to_node)] = from_node.get_capacity_left(to_node)
    return capacity


def find_shortest_path(nodes, edges, initial, fee_map, capacity_map, amount_in_wei):
    visited = {initial: amount_in_wei}
    path = {}
    capacity_left_in_path = {initial: float('inf')}

    while nodes:
        min_node = None
        for node in nodes:
            if node in visited:
                if min_node is None:
                    min_node = node
                elif visited[node] < visited[min_node]:
                    min_node = node

        if min_node is None:
            break

        nodes.remove(min_node)
        current_weight = visited[min_node]

        for edge in edges[min_node]:
            weight = current_weight + fee_map[(min_node, edge)]
            capacity_left = min(capacity_left_in_path[min_node], capacity_map[((min_node, edge))]) - fee_map[(min_node, edge)]
            if (edge not in visited or weight < visited[edge]) and capacity_left >= 0:
                visited[edge] = weight
                path[edge] = min_node
                capacity_left_in_path[edge] = capacity_left

    return visited, path