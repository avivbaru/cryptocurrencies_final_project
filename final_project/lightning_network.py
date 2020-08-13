import random
from collections import defaultdict
from typing import Dict, List, Tuple, Set

from LightningChannel import LightningNode, BlockChain


class Network:
    def __init__(self):
        self.nodes: List[LightningNode] = list()
        self.edges: defaultdict[LightningNode] = defaultdict(list)

    def add_node(self, value):
        self.nodes.append(value)

    def add_edge(self, from_node, to_node):
        self.edges[from_node].append(to_node)
        self.edges[to_node].append(from_node)


class MetricsCollector:
    def __init__(self):
        self._metrics = {}
        self._average_metrics_counter = defaultdict(int)
        self._average_metrics_sum = defaultdict(int)

    def average(self, key, value):
        self._average_metrics_counter[key] += 1
        self._average_metrics_sum[key] += value

    def max(self, key, value):
        self._metrics[key] = value if not self._metrics[key] or \
                                      self._metrics[key] < value else self._metrics[key]

    def min(self, key, value):
        self._metrics[key] = value if not self._metrics[key] or \
                                      self._metrics[key] > value else self._metrics[key]

    def get_metrics(self):
        average_metrics = {self._average_metrics_sum[metric] / self._average_metrics_counter[metric] for
                           metric in self._average_metrics_counter}
        return {**self._metrics, **average_metrics}


def generate_distances(edges, amount_in_wei):
    distances: Dict[Tuple[LightningNode, LightningNode], int] = {}
    for from_node in edges:
        for to_node in edges[from_node]:
            # TODO: implement calculate_fee
            distances[(from_node, to_node)] = to_node[1].calculate_fee(amount_in_wei)
    return distances


def generate_network(number_of_nodes, connectivity, blockchain, metrics_collector):
    network = Network()
    prev = None
    for i in range(number_of_nodes):
        node = LightningNode(i, blockchain)
        if prev:
            node.establish_channel(prev, 10)
            network.add_edge(prev, node)
        prev = node
        network.add_node(node)
    for i in range(number_of_nodes):
        for j in range(i + connectivity, number_of_nodes, connectivity):
            network.nodes[i].establish_channel(network.nodes[j], 10)
            network.add_edge(network.nodes[i], network.nodes[j])
    network.nodes[0].establish_channel(network.nodes[-1], 10)
    network.add_edge(network.nodes[0], network.nodes[-1])
    return network


def find_shortest_path(nodes, edges, initial, distances):
    visited = {initial: 0}
    path = {}

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
            weight = current_weight + distances[(min_node, edge)]
            if edge not in visited or weight < visited[edge]:
                visited[edge] = weight
                path[edge] = min_node

    return visited, path


def how_much_to_send():
    return 1


def main():
    # changeable parameters: number of block, channel per block, fee, starting balance, transaction amount,
    #                        blockchain fee.
    blockchain = BlockChain()
    metrics_collector = MetricsCollector()
    number_of_block = 100
    connectivity = 10
    failed_sends = 0
    network = generate_network(number_of_block, connectivity, blockchain, metrics_collector)
    for sender_node in network.nodes:
        amount_in_wei = how_much_to_send()
        # check API with Yakir
        edges = [edge for edge in network.edges if has_enough_money(edge, amount_in_wei)]
        distances = generate_distances(edges, amount_in_wei)
        visited, path = find_shortest_path(set(network.nodes), edges, sender_node, distances)
        node_to_send_wei = sender_node
        while node_to_send_wei == sender_node:
            node_to_send_wei = random.choice(network.nodes)
        if node_to_send_wei in visited:
            nodes_between = []
            curr = node_to_send_wei
            while curr != sender_node:
                nodes_between.append(curr)
                curr = path[curr]
            sender_node.start_htlc(amount_in_wei, node_to_send_wei, list(reversed(nodes_between)))
        else:
            failed_sends += 1


        print(path)


if __name__ == '__main__':
    main()



