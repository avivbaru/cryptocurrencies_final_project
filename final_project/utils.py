from collections import defaultdict
from typing import List, Callable


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
        average_metrics = {metric + "_avg": sum / self._average_metrics_count[metric]
                           for metric, sum in self._average_metrics.items()}
        return {**self._metrics, **average_metrics}


class FunctionCollector:
    def __init__(self):
        self._function_to_run: List[Callable[[], bool]] = []

    def run(self):
        self._function_to_run = [f for f in self._function_to_run if not f()]

    def append(self, f: Callable[[], bool]):
        self._function_to_run.append(f)