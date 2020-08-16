import random
import time
import math
import fire
import inspect
import LightningChannel
from network import Network
from typing import List
from singletons import METRICS_COLLECTOR_INSTANCE, FUNCTION_COLLECTOR_INSTANCE, BLOCKCHAIN_INSTANCE

HONEST_NODE_BALANCE_AVG = "honest_node_balance"
GRIEFING_NODE_BALANCE_AVG = "griefing_node_balance"
GRIEFING_SOFT_NODE_BALANCE_AVG = "soft_griefing_node_balance"
BLOCK_LOCKED_FUND = "block_locked_fund"
SEND_SUCCESSFULLY = "send_successfully"
PATH_LENGTH_AVG = "path_length"
NO_PATH_FOUND = "no_path_found"
SEND_FAILED = "send_failed"
MIN_TO_SEND = 0.0001 # TODO: check!
MAX_TO_SEND = 0.9 # TODO: check!
PERCENTAGE_BUCKETS = [0.05, 0.2, 0.3]
SIGMA = 0.1


def how_much_to_send(channel_starting_balance):
    mu = random.choice(PERCENTAGE_BUCKETS)
    return min(max(random.gauss(mu, SIGMA), MIN_TO_SEND), MAX_TO_SEND) * channel_starting_balance


def run_simulation(number_of_blocks, htlcs_per_block, network, channel_starting_balance, griefing_penalty):

    htlc_counter = 0
    while BLOCKCHAIN_INSTANCE.block_number < number_of_blocks:
        sender_node = random.choice(network.nodes)
        # find receiver node
        receiver_node = sender_node
        while receiver_node == sender_node:
            receiver_node = random.choice(network.nodes)

        amount_in_wei = how_much_to_send(channel_starting_balance)
        visited_nodes_to_min_hops, path_map = network.find_shortest_path(sender_node, amount_in_wei, griefing_penalty)
        if receiver_node in visited_nodes_to_min_hops:
            # find list of node between sender and receiver and edges to update their capacity
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
            total_locked_fund = 0
            for node in network.nodes:
                total_locked_fund += node.locked_funds
            METRICS_COLLECTOR_INSTANCE.average(BLOCK_LOCKED_FUND, total_locked_fund)
            print(f"increase block number. current is {BLOCKCHAIN_INSTANCE.block_number}")
            FUNCTION_COLLECTOR_INSTANCE.run()

    BLOCKCHAIN_INSTANCE.wait_k_blocks(5000)
    FUNCTION_COLLECTOR_INSTANCE.run()
    for node in network.nodes:
        for other_node in network.edges[node]:
            node.close_channel(other_node)

        if type(node) is LightningChannel.LightningNode:
            METRICS_COLLECTOR_INSTANCE.average(HONEST_NODE_BALANCE_AVG, BLOCKCHAIN_INSTANCE.get_balance_for_node(node))
        if type(node) is LightningChannel.LightningNodeGriefing:
            METRICS_COLLECTOR_INSTANCE.average(GRIEFING_NODE_BALANCE_AVG, BLOCKCHAIN_INSTANCE.get_balance_for_node(node))
        if type(node) is LightningChannel.LightningNodeSoftGriefing:
            METRICS_COLLECTOR_INSTANCE.average(GRIEFING_SOFT_NODE_BALANCE_AVG, BLOCKCHAIN_INSTANCE.get_balance_for_node(node))
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


def create_network(number_of_nodes, griefing_percentage, soft_griefing_percentage, starting_balance,
                   fee_percentage,
                   griefing_penalty_rate):
    network = Network()
    number_of_griefing_nodes = int(griefing_percentage * number_of_nodes)
    number_of_soft_griefing_nodes = int(soft_griefing_percentage * number_of_nodes)
    for _ in range(number_of_nodes - number_of_griefing_nodes - number_of_soft_griefing_nodes):
        node = LightningChannel.LightningNode(starting_balance, fee_percentage, griefing_penalty_rate)
        network.add_node(node)
    for _ in range(number_of_griefing_nodes):
        node = LightningChannel.LightningNodeGriefing(starting_balance, fee_percentage, griefing_penalty_rate)
        network.add_node(node)
    for _ in range(number_of_soft_griefing_nodes):
        node = LightningChannel.LightningNodeSoftGriefing(starting_balance, fee_percentage, griefing_penalty_rate)
        network.add_node(node)
    return network


# Redundancy network functions
def generate_redundancy_network(number_of_nodes, griefing_percentage, soft_griefing_percentage,
                                starting_balance, channel_starting_balance, fee_percentage,
                                griefing_penalty_rate):
    # connect 2 nodes if differ by 10 modulo 100 TODO: change!
    network = create_network(number_of_nodes, griefing_percentage, soft_griefing_percentage,
                             starting_balance, fee_percentage, griefing_penalty_rate)
    n = int(math.log(number_of_nodes, 10))
    jump_indexes = [10 ** i for i in range(n+1)]
    for i in range(number_of_nodes):
        for index_to_jump in jump_indexes:
            next_index = i + index_to_jump
            if next_index >= number_of_nodes:
                next_index -= number_of_nodes
            if next_index != i:
                network.add_edge(network.nodes[i], network.nodes[next_index], channel_starting_balance)
    return network


@simulation_details
def simulate_redundancy_network(number_of_nodes=500, griefing_percentage=0.05,
                                soft_griefing_percentage=0.05, number_of_blocks=15,
                                htlcs_per_block=20, channel_starting_balance=100000, starting_balance=2000000,
                                fee_percentage=0.05, griefing_penalty_rate=0.0001,
                                blockchain_fee=2):
    network = generate_redundancy_network(number_of_nodes, griefing_percentage, soft_griefing_percentage,
                                          starting_balance, channel_starting_balance, fee_percentage,
                                          griefing_penalty_rate)
    run_simulation(number_of_blocks, htlcs_per_block, network, channel_starting_balance, griefing_penalty_rate)


# Randomly network functions
def generate_network_randomly(number_of_nodes, griefing_percentage, soft_griefing_percentage,
                              channel_per_node, starting_balance, channel_starting_balance,
                              fee_percentage, griefing_penalty_rate):
    network = create_network(number_of_nodes, griefing_percentage, soft_griefing_percentage,
                             starting_balance, fee_percentage, griefing_penalty_rate)
    for node in network.nodes:
        nodes_to_connect = random.sample(network.nodes, channel_per_node)
        nodes_to_connect.remove(node)
        for node_to_connect in nodes_to_connect:
            network.add_edge(node, node_to_connect, channel_starting_balance)
    return network


@simulation_details
def simulate_random_network(number_of_nodes=100, griefing_percentage=0.05, soft_griefing_percentage=0.05,
                            number_of_blocks=15, htlcs_per_block=20, channel_per_node=10,
                            channel_starting_balance=10, starting_balance=200, fee_percentage=0.1,
                            griefing_penalty_rate=0.01, blockchain_fee=2):
    network = generate_network_randomly(number_of_nodes, griefing_percentage, soft_griefing_percentage,
                                        channel_per_node, starting_balance, channel_starting_balance,
                                        fee_percentage, griefing_penalty_rate)
    run_simulation(number_of_blocks, htlcs_per_block, network, channel_starting_balance, griefing_penalty_rate)


def main():
    fire.Fire({'random': simulate_random_network, 'redundancy': simulate_redundancy_network})


if __name__ == '__main__':
    main()



