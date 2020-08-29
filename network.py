from collections import defaultdict
from typing import Dict, List, Tuple, Set
import lightning_node


LightningNode = lightning_node.LightningNode


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

    def update_capacity_map(self, sender: LightningNode,
                            nodes_between: Dict[LightningNode, List[LightningNode]]):
        prev = sender
        for curr in nodes_between:
            self.capacity[(prev, curr)] = prev.get_capacity_left(curr)
            self.capacity[(curr, prev)] = curr.get_capacity_left(prev)
            prev = curr

    def get_fees_map(self) -> Dict[Tuple[LightningNode, LightningNode], float]:
        if not self.fees_rate_map:
            for from_node in self.edges:
                for to_node in self.edges[from_node]:
                    self.fees_rate_map[(from_node, to_node)] = to_node.fee_percentage
        return self.fees_rate_map

    def find_shortest_path(self, initial: LightningNode, amount_in_wei: int,
                           griefing_penalty_rate: float):
        fee_map: Dict[Tuple[LightningNode, LightningNode], float] = self.get_fees_map()
        capacity_map: Dict[Tuple[LightningNode, LightningNode], int] = self.get_capacity_map()
        nodes: Set[LightningNode] = set(self.nodes)
        visited: Dict[LightningNode, int] = {initial: amount_in_wei}
        first_node_in_path_map: Dict[LightningNode, LightningNode] = {}
        capacity_left_in_path: Dict[LightningNode, int] = {initial: float('inf')}
        fee_paid_map: Dict[LightningNode, int] = {initial: 0}
        path: Dict[LightningNode, List[LightningNode]] = {initial: []}

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
            current_wei = visited[min_node]

            for edge_node in self.edges[min_node]:
                capacity_between = capacity_map[(min_node, edge_node)]
                if capacity_between >= amount_in_wei:
                    fee_between = int(fee_map[(min_node, edge_node)] * current_wei)
                    capacity_left = min(capacity_left_in_path[min_node],
                                        capacity_between - amount_in_wei) - fee_between
                    new_wei = current_wei + fee_between

                    # check if griefing is possible
                    is_griefing_possible = True
                    nodes_between = path[min_node] + [edge_node]
                    if griefing_penalty_rate > 0:
                        is_griefing_possible = Network._is_griefing_possible(capacity_map, nodes_between,
                                                                             fee_paid_map,
                                                                             griefing_penalty_rate,
                                                                             initial, new_wei)

                    if (edge_node not in visited or new_wei < visited[edge_node]) \
                            and capacity_left >= 0 and is_griefing_possible:
                        visited[edge_node] = new_wei
                        first_node_in_path_map[edge_node] = min_node
                        path[edge_node] = nodes_between
                        capacity_left_in_path[edge_node] = capacity_left
                        fee_paid_map[edge_node] = fee_between

        return visited, path

    @staticmethod
    def _is_griefing_possible(capacity_map, nodes_in_path, fee_paid_map, griefing_penalty_rate, initial,
                              new_wei):
        length = len(nodes_in_path) + 1
        prev = initial
        temp_wei = new_wei
        is_griefing_possible = True
        griefing_penalty_sum = 0
        for i, n in enumerate(nodes_in_path):
            griefing_penalty_sum += temp_wei * griefing_penalty_rate * length * 1440
            is_griefing_possible = is_griefing_possible and \
                                   griefing_penalty_sum <= capacity_map[(n, prev)]
            prev = n
            length -= 1
            temp_wei -= fee_paid_map.get(n, 0)
        return is_griefing_possible
