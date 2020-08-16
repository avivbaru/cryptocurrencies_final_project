import random
import time
import fire
import inspect
import LightningChannel
from network import Network
from Blockchain import BLOCKCHAIN_INSTANCE
from utils import FunctionCollector, MetricsCollector

SEND_SUCCESSFULLY = "send_successfully"
PATH_LENGTH_AVG = "path_length_avg"
NO_PATH_FOUND = "no_path_found"
SEND_FAILED = "send_failed"
MIN_TO_SEND = 0.0001 # TODO: check!
MAX_TO_SEND = 0.9 # TODO: check!

METRICS_COLLECTOR_INSTANCE = MetricsCollector()
FUNCTION_COLLECTOR_INSTANCE = FunctionCollector()


def how_much_to_send(starting_balance, mu, sigma):
    # TODO: change?
    return max(min(random.gauss(mu, sigma), MIN_TO_SEND), MAX_TO_SEND) * 10


def run_simulation(number_of_blocks, network, starting_balance, mean_percentage_of_capacity,
                   sigma_percentage_of_capacity, htlcs_per_block):

    htlc_counter = 0
    while BLOCKCHAIN_INSTANCE.block_number < number_of_blocks:
        sender_node = random.choice(network.nodes)
        amount_in_wei = how_much_to_send(starting_balance, mean_percentage_of_capacity,
                                         sigma_percentage_of_capacity)
        # prepare data to find path from sender to any node
        net_network = network.get_network_with_enough_capacity(amount_in_wei)
        visited_nodes_to_min_hops, path_map = net_network.find_shortest_path(sender_node, amount_in_wei)
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
            METRICS_COLLECTOR_INSTANCE.average(PATH_LENGTH_AVG, len(nodes_between))
            send_htlc_successfully = sender_node.start_htlc(receiver_node, amount_in_wei,
                                                            list(reversed(nodes_between)))
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
def generate_redundancy_network(number_of_nodes, connectivity, starting_balance):
    # connect 2 nodes if differ by 10 modulo 100 TODO: change!
    network = Network()
    prev = None
    for i in range(number_of_nodes):
        node = LightningChannel.LightningNode(starting_balance, METRICS_COLLECTOR_INSTANCE, FUNCTION_COLLECTOR_INSTANCE)
        if prev:
            network.add_edge(prev, node)
        prev = node
        network.add_node(node)
    for i in range(number_of_nodes):
        for j in range(i + connectivity, number_of_nodes, connectivity):
            network.add_edge(network.nodes[i], network.nodes[j])
    network.add_edge(network.nodes[0], network.nodes[-1])
    return network


@simulation_details
def simulate_redundancy_network(number_of_nodes=100, number_of_blocks=15, htlcs_per_block=20,
                                connectivity=10, mean_percentage_of_capacity=0.3,
                                sigma_percentage_of_capacity=0.1, fee_percentage=0.1,
                                min_fee=2, starting_balance=200, blockchain_fee=2):
    # changeable parameters: number of block, channel per block, fee, starting balance, transaction amount,
    #                        blockchain fee.

    network = generate_redundancy_network(number_of_nodes, connectivity, starting_balance)
    run_simulation(number_of_blocks, network, starting_balance, mean_percentage_of_capacity,
                   sigma_percentage_of_capacity, htlcs_per_block)


# Randomly network functions
def generate_network_randomly(number_of_nodes, connectivity, starting_balance):
    network = Network()
    for i in range(number_of_nodes):
        node = LightningChannel.LightningNode(starting_balance, METRICS_COLLECTOR_INSTANCE, FUNCTION_COLLECTOR_INSTANCE)
        network.add_node(node)
    for node in network.nodes:
        nodes_to_connect = random.sample(network.nodes, connectivity)
        nodes_to_connect.remove(node)
        for node_to_connect in nodes_to_connect:
            network.add_edge(node, node_to_connect)
    return network


@simulation_details
def simulate_random_network(number_of_nodes=100, number_of_blocks=15, htlcs_per_block=20, connectivity=10,
                            mean_percentage_of_capacity=0.3, sigma_percentage_of_capacity=0.1,
                            fee_percentage=0.1, min_fee=2, starting_balance=10, blockchain_fee=2):

    network = generate_network_randomly(number_of_nodes, connectivity, starting_balance)
    run_simulation(number_of_blocks, network, starting_balance, mean_percentage_of_capacity,
                   sigma_percentage_of_capacity, htlcs_per_block)


def main():
    fire.Fire()


if __name__ == '__main__':
    main()



