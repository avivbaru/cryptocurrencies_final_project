from collections import defaultdict
from typing import Dict, List, Tuple, Set, NewType
import LightningChannel 


LightningNode = NewType('LightningNode', LightningChannel.LightningNode)


class Network:
    def __init__(self, nodes=None, edges=None):
        self.nodes: List[LightningNode] = nodes if nodes else []
        self.edges: defaultdict[LightningNode, List[LightningNode]] = edges if edges else defaultdict(list)
        self.fees_rate_map: Dict[Tuple[LightningNode, LightningNode], float] = {}
        self.capacity: Dict[Tuple[LightningNode, LightningNode], int] = {}

    def add_node(self, value):
        self.nodes.append(value)

    def add_edge(self, from_node: LightningNode, to_node: LightningNode, channel_starting_balance: int):
        self.edges[from_node].append(to_node)
        self.edges[to_node].append(from_node)
        channel = to_node.establish_channel(from_node, channel_starting_balance)
        from_node.add_money_to_channel(channel, channel_starting_balance)

    def get_capacity_map(self) -> Dict[Tuple[LightningNode, LightningNode], int]:
        if not self.capacity:
            for from_node, to_nodes in self.edges.items():
                for to_node in to_nodes:
                    self.capacity[(from_node, to_node)] = from_node.get_capacity_left(to_node)
        return self.capacity

    def update_capacity_map(self, edges_to_update: List[Tuple[LightningNode, LightningNode]]):
        for edge in edges_to_update:
            self.capacity[edge] = edge[0].get_capacity_left(edge[1])

    def get_fees_map(self) -> Dict[Tuple[LightningNode, LightningNode], float]:
        if not self.fees_rate_map:
            for from_node in self.edges:
                for to_node in self.edges[from_node]:
                    self.fees_rate_map[(from_node, to_node)] = to_node.fee_percentage
        return self.fees_rate_map

    def find_shortest_path(self, initial: LightningNode, amount_in_wei: int):
        fee_map: Dict[Tuple[LightningNode, LightningNode], float] = self.get_fees_map()
        capacity_map: Dict[Tuple[LightningNode, LightningNode], int] = self.get_capacity_map()
        nodes: Set[LightningNode] = set(self.nodes)
        visited: Dict[LightningNode, int] = {initial: amount_in_wei}
        path: Dict[LightningNode, LightningNode] = {}
        capacity_left_in_path: Dict[LightningNode, int] = {initial: float('inf')}

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

            for edge in self.edges[min_node]:
                capacity_between = capacity_map[(min_node, edge)]
                if capacity_between >= amount_in_wei:
                    fee_between = int(fee_map[(min_node, edge)] * current_weight)
                    weight = current_weight + fee_between
                    capacity_left = min(capacity_left_in_path[min_node], capacity_between - amount_in_wei) - \
                                    fee_between
                    if (edge not in visited or weight < visited[edge]) and capacity_left >= 0:
                        visited[edge] = weight
                        path[edge] = min_node
                        capacity_left_in_path[edge] = capacity_left

        return visited, path

