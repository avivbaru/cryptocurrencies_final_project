import random
from collections import defaultdict
from typing import Dict, List, Tuple, Callable
import time
import fire
import pprint
import LightningChannel
from Blockchain import BLOCKCHAIN_INSTANCE

PATH_LENGTH_AVG = "path_length_avg"

NO_PATH_FOUND = "no_path_found"
SEND_FAILED = "send_failed"
MIN_TO_SEND = 0.0001 # TODO: check!
MAX_TO_SEND = 0.9 # TODO: check!


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
        channel.owner2_add_funds(10)

    def get_edges_with_enough_capacity(self, amount_in_wei, capacity_map):
        return {from_node: [to_node for to_node in nodes if
                            capacity_map[(from_node, to_node)] > amount_in_wei]
                for from_node, nodes in self.edges.items()}


class MetricsCollector:
    def __init__(self):
        self._metrics = defaultdict(int)
        self._average_metrics = defaultdict(int)
        self._average_metrics_count = defaultdict(int)

    def average(self, key, value):
        self._average_metrics[key] += value
        self._average_metrics_count[key] += 1

    # Assume all values > 0
    def max(self, key, value):
        self._metrics[key] = max(value, self._metrics[key])

    # Assume all values > 0
    def min(self, key, value):
        self._metrics[key] = min(value, self._metrics.get(key, float('inf')))

    def count(self, key):
        self._metrics[key] += 1

    def get_metrics(self):
        average_metrics = {metric: sum / self._average_metrics_count[metric] for metric, sum in self._average_metrics.items()}
        return {**self._metrics, **average_metrics}


class FunctionCollector:
    def __init__(self):
        self._function_to_run: List[Callable[[], bool]] = []

    def run(self):
        self._function_to_run = [f for f in self._function_to_run if not f()]


def generate_fee_map(edges, amount_in_wei):
    fees: Dict[Tuple[LightningChannel.LightningNode, LightningChannel.LightningNode], int] = {}
    for from_node in edges:
        for to_node in edges[from_node]:
            # TODO: implement calculate_fee
            fees[(from_node, to_node)] = amount_in_wei * 0.1#to_node.calculate_fee(amount_in_wei)
    return fees


def generate_capacity_map(edges):
    capacity: Dict[Tuple[LightningChannel.LightningNode, LightningChannel.LightningNode], int] = {}
    for from_node, to_nodes in edges.items():
        for to_node in to_nodes:
            capacity[(from_node, to_node)] = from_node.get_capacity_left(to_node)
    return capacity


def generate_redundancy_network(number_of_nodes, connectivity, starting_balance,
                                metrics_collector, function_collector):
    # connect 2 nodes if differ by 10 modulo 100 TODO: change!
    network = Network()
    prev = None
    for i in range(number_of_nodes):
        node = LightningChannel.LightningNode(starting_balance, metrics_collector, function_collector)
        if prev:
            network.add_edge(prev, node)
        prev = node
        network.add_node(node)
    for i in range(number_of_nodes):
        for j in range(i + connectivity, number_of_nodes, connectivity):
            network.add_edge(network.nodes[i], network.nodes[j])
    network.add_edge(network.nodes[0], network.nodes[-1])
    return network


def generate_network_randomly(number_of_nodes, connectivity, starting_balance,
                              metrics_collector, function_collector):
    network = Network()
    for i in range(number_of_nodes):
        node = LightningChannel.LightningNode(starting_balance, metrics_collector, function_collector)
        network.add_node(node)
    for node in network.nodes:
        nodes_to_connect = random.sample(network.nodes, connectivity)
        nodes_to_connect.remove(node)
        for node_to_connect in nodes_to_connect:
            network.add_edge(node, node_to_connect)
    return network


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


def how_much_to_send(starting_balance, mu, sigma):
    # TODO: change?
    return max(min(random.gauss(mu, sigma), MIN_TO_SEND), MAX_TO_SEND) * starting_balance


def run_simulation(number_of_blocks, network, starting_balance, mean_percentage_of_capacity,
                   sigma_percentage_of_capacity, metrics_collector, htlcs_per_block, function_collector):
    starting_time = time.time()
    htlc_counter = 0
    while BLOCKCHAIN_INSTANCE.block_number < number_of_blocks:
        sender_node = random.choice(network.nodes)
        amount_in_wei = how_much_to_send(starting_balance, mean_percentage_of_capacity,
                                         sigma_percentage_of_capacity)
        if amount_in_wei == 0:
            continue
        # prepare data to find path from sender to any node
        capacity_map = generate_capacity_map(network.edges)
        edges = network.get_edges_with_enough_capacity(amount_in_wei, capacity_map)
        fee_map = generate_fee_map(edges, amount_in_wei)
        visited_nodes_to_min_hops, path_map = find_shortest_path(set(network.nodes), edges, sender_node,
                                                                 fee_map, capacity_map, amount_in_wei)
        # find receiver node
        receiver_node = sender_node
        while receiver_node == sender_node:
            receiver_node = random.choice(network.nodes)
        if receiver_node in visited_nodes_to_min_hops:
            # find list of node between sender and receiver
            nodes_between = []
            curr = receiver_node
            while curr != sender_node:
                nodes_between.append(curr)
                curr = path_map[curr]
            metrics_collector.average(PATH_LENGTH_AVG, len(nodes_between))
            send_htlc_successfully = sender_node.start_htlc(receiver_node, amount_in_wei,
                                                            list(reversed(nodes_between)))
            if not send_htlc_successfully:
                metrics_collector.count(SEND_FAILED)
        else:
            metrics_collector.count(NO_PATH_FOUND)

        htlc_counter += 1
        if htlc_counter == htlcs_per_block:
            htlc_counter = 0
            BLOCKCHAIN_INSTANCE.wait_k_blocks(1)
            function_collector.run()

    for node in network.nodes:
        for other_node in network.edges[node]:
            node.close_channel(other_node)

        metrics_collector.average("node_balance_avg", BLOCKCHAIN_INSTANCE.get_balance_for_node(node))
    time_took = time.time() - starting_time
    print(f"Finish the simulation in {int(time_took)}s.")
    metrics_str = '\n'.join([f'{k}:{v}' for k, v in metrics_collector.get_metrics().items()])
    print(f"Metrics of this run: \n{metrics_str}")


def simulate_random_network(number_of_nodes=100, number_of_blocks=15, htlcs_per_block=20, connectivity=10,
                     mean_percentage_of_capacity=0.3, sigma_percentage_of_capacity=0.1, fee_percentage=0.1,
                     min_fee=2, starting_balance=10, blockchain_fee=2):
    print(f"Start random simulation. parameters are- \nnumber_of_nodes:{number_of_nodes}, "
          f"number_of_blocks:{number_of_blocks}, htlcs_per_block:{htlcs_per_block}, "
          f"connectivity:{connectivity}, mean_percentage_of_capacity:{mean_percentage_of_capacity}, "
          f"sigma_percentage_of_capacity:{sigma_percentage_of_capacity}.")
    metrics_collector = MetricsCollector()
    function_collector = FunctionCollector()

    network = generate_network_randomly(number_of_nodes, connectivity, starting_balance,
                                        metrics_collector, function_collector)
    run_simulation(number_of_blocks, network, starting_balance, mean_percentage_of_capacity,
                   sigma_percentage_of_capacity, metrics_collector, htlcs_per_block, function_collector)


def simulate_redundancy_network(number_of_nodes=100, number_of_blocks=15, htlcs_per_block=20,
                                connectivity=10, mean_percentage_of_capacity=0.3,
                                sigma_percentage_of_capacity=0.1, fee_percentage=0.1,
                                min_fee=2, starting_balance=10, blockchain_fee=2):
    # changeable parameters: number of block, channel per block, fee, starting balance, transaction amount,
    #                        blockchain fee.

    print(f"Start redundancy simulation. parameters are- \nnumber_of_nodes:{number_of_nodes}, "
          f"number_of_blocks:{number_of_blocks}, htlcs_per_block:{htlcs_per_block}, "
          f"connectivity:{connectivity}, mean_percentage_of_capacity:{mean_percentage_of_capacity}, "
          f"sigma_percentage_of_capacity:{sigma_percentage_of_capacity}.")
    metrics_collector = MetricsCollector()
    function_collector = FunctionCollector()

    network = generate_redundancy_network(number_of_nodes, connectivity, starting_balance,
                                          metrics_collector, function_collector)
    run_simulation(number_of_blocks, network, starting_balance, mean_percentage_of_capacity,
                   sigma_percentage_of_capacity, metrics_collector, htlcs_per_block, function_collector)


def main():
    fire.Fire()


if __name__ == '__main__':
    main()



