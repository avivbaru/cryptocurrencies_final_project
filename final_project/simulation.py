import random
import time
import math
import fire
import inspect
import LightningChannel
from network import Network
from typing import List
from singletons import METRICS_COLLECTOR_INSTANCE, FUNCTION_COLLECTOR_INSTANCE, BLOCKCHAIN_INSTANCE

SEND_SUCCESSFULLY = "send_successfully"
PATH_LENGTH_AVG = "path_length_avg"
NO_PATH_FOUND = "no_path_found"
SEND_FAILED = "send_failed"
MIN_TO_SEND = 0.0001 # TODO: check!
MAX_TO_SEND = 0.9 # TODO: check!
PERCENTAGE_BUCKETS = [0.05, 0.2, 0.3]
SIGMA = 0.1


def how_much_to_send(channel_starting_balance):
    mu = random.choice(PERCENTAGE_BUCKETS)
    return min(max(random.gauss(mu, SIGMA), MIN_TO_SEND), MAX_TO_SEND) * channel_starting_balance


def run_simulation(number_of_blocks, htlcs_per_block, network, channel_starting_balance):

    htlc_counter = 0
    while BLOCKCHAIN_INSTANCE.block_number < number_of_blocks:
        sender_node = random.choice(network.nodes)
        # find receiver node
        receiver_node = sender_node
        while receiver_node == sender_node:
            receiver_node = random.choice(network.nodes)

        amount_in_wei = how_much_to_send(channel_starting_balance)
        visited_nodes_to_min_hops, path_map = network.find_shortest_path(sender_node, amount_in_wei)
        if receiver_node in visited_nodes_to_min_hops:
            # find list of node between sender and receiver
            nodes_between = []
            edge_to_update = []
            curr = receiver_node
            while curr != sender_node:
                nodes_between.append(curr)
                edge_to_update.append((path_map[curr], curr))
                edge_to_update.append((curr, path_map[curr]))
                curr = path_map[curr]

            METRICS_COLLECTOR_INSTANCE.average(PATH_LENGTH_AVG, len(nodes_between))
            nodes_between.reverse()
            send_htlc_successfully = sender_node.start_htlc(receiver_node, amount_in_wei, nodes_between)
            network.update_capacity_map(edge_to_update)
            if send_htlc_successfully:
                METRICS_COLLECTOR_INSTANCE.count(SEND_SUCCESSFULLY)
            else:
                METRICS_COLLECTOR_INSTANCE.count(SEND_FAILED)
        else:
            METRICS_COLLECTOR_INSTANCE.count(NO_PATH_FOUND)

        htlc_counter += 1
        if htlc_counter == htlcs_per_block:
            htlc_counter = 0
            BLOCKCHAIN_INSTANCE.wait_k_blocks(1)
            FUNCTION_COLLECTOR_INSTANCE.run()

    for node in network.nodes:
        for other_node in network.edges[node]:
            node.close_channel(other_node)

        METRICS_COLLECTOR_INSTANCE.average("node_balance_avg", BLOCKCHAIN_INSTANCE.get_balance_for_node(node))
    metrics_str = '\n'.join([f'{k}:{v}' for k, v in METRICS_COLLECTOR_INSTANCE.get_metrics().items()])
    print(f"Metrics of this run: \n{metrics_str}")


def simulation_details(func):
    def wrapper(*args, **kwargs):
        func_args = inspect.signature(func).bind(*args, **kwargs)
        func_args.apply_defaults()
        func_args_str = ", ".join("{} = {!r}".format(*item) for item in func_args.arguments.items())
        print(f"Start to run {func.__qualname__} with arguments: ( {func_args_str} )")
        starting_time = time.time()
        res = func(*args, **kwargs)
        time_took = time.time() - starting_time
        print(f"Finish the run in {int(time_took)}s.")
        return res

    return wrapper


# Redundancy network functions
def generate_redundancy_network(number_of_nodes, connectivity, starting_balance, channel_starting_balance,
                                fee_percentage, griefing_penalty_rate):
    # connect 2 nodes if differ by 10 modulo 100 TODO: change!
    network = Network()
    prev = None
    for i in range(number_of_nodes):
        node = LightningChannel.LightningNodeGriefing(starting_balance, fee_percentage, griefing_penalty_rate)
        if prev:
            network.add_edge(prev, node, channel_starting_balance)
        prev = node
        network.add_node(node)
    n = int(math.log(number_of_nodes, 10))
    jump_indexes = [10 ** i for i in range(1, n+1)]
    for i in range(number_of_nodes):
        for index_to_jump in jump_indexes:
            next_index = i + index_to_jump
            if next_index >= number_of_nodes:
                next_index -= number_of_nodes
            network.add_edge(network.nodes[i], network.nodes[next_index], channel_starting_balance)
    return network


@simulation_details
def simulate_redundancy_network(number_of_nodes=100, number_of_blocks=1500, htlcs_per_block=20,
                                connectivity=10, channel_starting_balance=10000,
                                starting_balance=200000, fee_percentage=0.05, griefing_penalty_rate=0.01,
                                blockchain_fee=2):
    network = generate_redundancy_network(number_of_nodes, connectivity, starting_balance,
                                          channel_starting_balance, fee_percentage, griefing_penalty_rate)
    run_simulation(number_of_blocks, htlcs_per_block, network, channel_starting_balance)


# Randomly network functions
def generate_network_randomly(number_of_nodes, connectivity, starting_balance, channel_starting_balance,
                              fee_percentage, griefing_penalty_rate):
    network = Network()
    for i in range(number_of_nodes):
        node = LightningChannel.LightningNode(starting_balance, fee_percentage, griefing_penalty_rate)
        network.add_node(node)
    for node in network.nodes:
        nodes_to_connect = random.sample(network.nodes, connectivity)
        nodes_to_connect.remove(node)
        for node_to_connect in nodes_to_connect:
            network.add_edge(node, node_to_connect, channel_starting_balance)
    return network


@simulation_details
def simulate_random_network(number_of_nodes=100, number_of_blocks=15, htlcs_per_block=20, connectivity=10,
                            channel_starting_balance=10, starting_balance=200, fee_percentage=0.1,
                            griefing_penalty_rate=0.01, blockchain_fee=2):
    network = generate_network_randomly(number_of_nodes, connectivity, starting_balance,
                                        channel_starting_balance, fee_percentage, griefing_penalty_rate)
    run_simulation(number_of_blocks, htlcs_per_block, network, channel_starting_balance)


def main():
    fire.Fire({'random': simulate_random_network, 'redundancy': simulate_redundancy_network})


if __name__ == '__main__':
    main()



