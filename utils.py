from collections import defaultdict
from typing import List, Callable, Tuple
import singletons


class MetricsCollector:
    """
    Class for a singleton to collects metric about a run of a simulation.
    """
    def __init__(self):
        self.init_parameters()

    def init_parameters(self):
        """
        Resets this instance.
        """
        self._metrics = defaultdict(int)
        self._average_metrics = defaultdict(int)
        self._average_metrics_count = defaultdict(int)

    def average(self, key, value):
        """
        Adds `value` to the average count of `key`.
        """
        self._average_metrics[key] += value
        self._average_metrics_count[key] += 1

    # Assume all values > 0
    def max(self, key, value):
        """
        Updates the max value of `key` by `value` if needed.
        """
        self._metrics[key] = max(value, self._metrics[key])

    # Assume all values > 0
    def min(self, key, value):
        """
        Updates the min value of `key` by `value` if needed.
        """
        self._metrics[key] = min(value, self._metrics.get(key, float('inf')))

    def count(self, key):
        """
        Updates the value of `key` by 1.
        """
        self._metrics[key] += 1

    def sum(self, key, value):
        """
        Updates the value of `key` by `value`.
        """
        self._metrics[key] += value

    def get_metrics(self):
        """
        @return: a dictionary of all metrics.
        """
        average_metrics = {metric: sum / self._average_metrics_count[metric] for metric, sum in self._average_metrics.items()}
        return {**self._metrics, **average_metrics}


class FunctionCollector:
    """
    Singleton class to collect function during a simulation run and invoke it on a certain time (block number)
    """
    def __init__(self):
        self.init_parameters()

    def init_parameters(self):
        """
        Resets this instance.
        """
        self._function_to_run: List[Tuple[Callable[[], None], int]] = []

    def run(self):
        """
        Invokes all the functions that requested to run on the current block number (or lower).
        """
        temp_function_to_run = [f for (f, k) in self._function_to_run
                                if k <= singletons.BLOCKCHAIN_INSTANCE.block_number]
        for f in temp_function_to_run:
            f()
        self._function_to_run = [(f, k) for (f, k) in self._function_to_run
                                if f not in temp_function_to_run]

    def append(self, f: Callable[[], None], k: int):
        """
        Collects function `f` to be invoked on block number `k`.
        """
        self._function_to_run.append((f, k))

    def get_max_k(self):
        """
        @return: the latest time a function asked to be called.
        """
        return max([k for (f, k) in self._function_to_run]) if self._function_to_run else None

    def get_min_k(self):
        """
        @return: the earliest time a function asked to be called.
        """
        return min([k for (f, k) in self._function_to_run])  if self._function_to_run else None
