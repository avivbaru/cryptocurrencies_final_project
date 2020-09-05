import json
import os
from collections import defaultdict
import fire


def main():
    files = os.listdir('.')
    all_data = []
    for f_name in reversed(files):
        if f_name.endswith(f'_rawdata'):
            print(f"Opening file {f_name}")
            with open(f_name, 'r') as f:
                all_data.extend(f.readlines())
            break
    all_data = [json.loads(d.strip()) for d in all_data if d.strip()]
    runs = {}
    all_parameters = defaultdict(set)
    for line in all_data:
        for p in line['parameters']:
            all_parameters[p].add(line['parameters'][p])
        parameters = [str(i[1]) for i in sorted(line['parameters'].items(), key=lambda x: x[0])]
        runs['_'.join(parameters)] = line['metrics']

    for r in runs:
        print(r, runs[r])

    with open(f'../simulation_gui/runs.js', 'w') as f:
        f.write(f"data_json = '{json.dumps(runs)}';")


if __name__ == '__main__':
    fire.Fire()
