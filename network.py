from collections import defaultdict
from typing import Dict, List, Tuple, Set
import lightning_node


LightningNode = lightning_node.LightningNode


class Network:
    """
    Represent Lightning network.
    """
    def __init__(self, nodes=None, edges=None):
        self.nodes: List[LightningNode] = nodes if nodes else []
        self.edges: defaultdict[LightningNode, List[LightningNode]] = edges if edges else defaultdict(list)

    def add_node(self, value):
        """
        Add new node.
        """
        self.nodes.append(value)

    def add_edge(self, from_node: LightningNode, to_node: LightningNode, channel_starting_balance: int, is_bad_channel=False):
        """
        Add new edge between nodes.
        """
        self.edges[from_node].append(to_node)
        self.edges[to_node].append(from_node)
        channel = to_node.establish_channel(from_node, channel_starting_balance, is_bad_channel)
        from_node.add_money_to_channel(channel, channel_starting_balance)

    def find_shortest_path(self, last_node: LightningNode, initial_node: LightningNode, amount_in_msat: int,
                           griefing_penalty_rate: float, is_gp_protocol: bool):
        """
        Gets target node and source node, find path from source to target using minimal fee. Also check that target to source
        can lock Griefing penalty.
        The search is done from target to source.
        """
        nodes: Set[LightningNode] = set(self.nodes)
        visited: Dict[LightningNode, int] = {last_node: amount_in_msat}
        path: Dict[LightningNode, List[LightningNode]] = {last_node: []}

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
            current_msat = visited[min_node]

            neighbors = self.edges[min_node].copy()
            for edge_node in neighbors:
                capacity_between = edge_node.get_capacity_left(min_node)
                # check if the channel closed already
                if capacity_between is None:
                    self.edges[min_node].remove(edge_node)
                    self.edges[edge_node].remove(min_node)
                    continue
                # calculate amount + fee
                new_msat = (current_msat + edge_node.base_fee) / (1 - edge_node.fee_percentage) if \
                    edge_node != initial_node else current_msat
                if capacity_between >= new_msat:
                    # check if griefing is possible
                    is_griefing_possible = True
                    if is_gp_protocol and griefing_penalty_rate > 0:
                        is_griefing_possible = Network.is_griefing_possible(path[min_node], edge_node,
                                                                            visited,
                                                                            griefing_penalty_rate, new_msat)

                    if (edge_node not in visited or new_msat < visited[edge_node]) and is_griefing_possible:
                        visited[edge_node] = new_msat
                        path[edge_node] = path[min_node] + [edge_node]

        return visited, path

    @staticmethod
    def is_griefing_possible(nodes_in_path: List[LightningNode], final_node: LightningNode, visited: Dict[LightningNode, float],
                             griefing_penalty_rate: float, new_msat: int):
        """
        Return True if can send from the final_node to last first node in nodes_in_path and lock the griefing penalty necessary.
        """
        length = len(nodes_in_path) + 1
        reversed_nodes_in_path = list(reversed(nodes_in_path))
        prev = final_node
        griefing_penalty_sum = 0
        for n in reversed_nodes_in_path:
            amount_to_send = visited.get(prev, new_msat)
            griefing_penalty_sum += int(amount_to_send * griefing_penalty_rate * length * 1440)
            if griefing_penalty_sum > n.get_capacity_left(prev):
                return False
            prev = n
            length -= 1
        return True
