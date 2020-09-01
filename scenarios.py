
# from singletons import *
import simulation


def init_scenario():
    network = simulation.Network()
    type_node = simulation.NodeType.SOFT_GRIEFING
    type_node = None
    wait = 1
    network.add_node(simulation.create_node(40, wait))
    network.add_node(simulation.create_node(40, wait))
    network.add_node(simulation.create_node(40, wait))
    network.add_node(simulation.create_node(40, wait, type_node))
    network.add_node(simulation.create_node(40, wait))
    network.add_node(simulation.create_node(40, wait))
    network.add_node(simulation.create_node(40, wait))
    network.add_node(simulation.create_node(40, wait))
    network.add_node(simulation.create_node(40, wait))
    network.add_node(simulation.create_node(40, wait))
    network.add_node(simulation.create_node(40, wait))
    network.add_node(simulation.create_node(40, wait))
    network.add_edge(network.nodes[0], network.nodes[1], 1000000)
    network.add_edge(network.nodes[1], network.nodes[2], 1000000)
    network.add_edge(network.nodes[3], network.nodes[2], 1000000)
    network.add_edge(network.nodes[4], network.nodes[3], 1000000)
    network.add_edge(network.nodes[5], network.nodes[4], 1000000)
    network.add_edge(network.nodes[6], network.nodes[5], 1000000)
    network.add_edge(network.nodes[7], network.nodes[6], 1000000)
    network.add_edge(network.nodes[8], network.nodes[7], 1000000)
    network.add_edge(network.nodes[8], network.nodes[9], 1000000)
    network.add_edge(network.nodes[10], network.nodes[9], 1000000)
    network.add_edge(network.nodes[10], network.nodes[11], 1000000)
    network.add_edge(network.nodes[0], network.nodes[11], 1000000)
    # network.add_edge(network.nodes[9], network.nodes[8], 1000000)
    return network


def scenario1():
    network = init_scenario()
    simulation.run_simulation(network, True)
    metrics = simulation.METRICS_COLLECTOR_INSTANCE.get_metrics()
    print(f"{metrics.get('Total locked fund in every blocks') / metrics.get('Transactions successful'):,}")


scenario1()