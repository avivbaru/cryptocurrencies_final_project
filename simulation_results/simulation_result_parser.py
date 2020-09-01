import itertools
import json
import os
from collections import defaultdict


def main():
    files = os.listdir('.')
    all_data = []
    for f_name in files:
        if f_name.endswith('_rawdata'):
            with open(f_name, 'r') as f:
                all_data.extend(f.readlines())
    all_data = [json.loads(d.strip()) for d in all_data if d.strip()]
    runs = {}
    all_parameters = defaultdict(set)
    for line in all_data:
        for p in line['parameters']:
            all_parameters[p].add(line['parameters'][p])
        parameters = [str(i[1]) for i in sorted(line['parameters'].items(), key=lambda x: x[0])]
        runs['_'.join(parameters)] = line['metrics']

    # Calculate average
    all_parameters_with_multiple_values = {k: v for k, v in all_parameters.items() if len(v) > 1}
    for i in range(1, len(all_parameters_with_multiple_values.keys()) + 1):
        for per in itertools.permutations(all_parameters_with_multiple_values.keys(), i):
            permutation = [[[aa] for aa in i[1]] if i[0] not in per else [list(i[1])] * len(i[1]) for i in
                           sorted(all_parameters.items(), key=lambda x: x[0])]
            for values in itertools.product(*permutation):
                metrics = defaultdict(int)
                count = 0
                key_to_calculate_average = '_'.join([str(z[0]) if len(z) == 1 else 'Average' for z in values])
                for opt in itertools.product(*values):
                    current_key = '_'.join([str(z) for z in opt])
                    for metric_name, metric_value in runs[current_key].items():
                        metrics[metric_name] += metric_value
                    count += 1
                runs[key_to_calculate_average] = {k: v / count for k, v in metrics.items()} # calculate the average
    for r in runs:
        print(r, runs[r])

    with open('../simulation_gui/runs.json', 'w') as f:
        f.write(json.dumps(runs))


if __name__ == '__main__':
    main()