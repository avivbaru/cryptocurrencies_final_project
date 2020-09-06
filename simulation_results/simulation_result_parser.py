import json
import os
from collections import defaultdict
import fire


def main():
    files = os.listdir('./GoodRuns/')
    all_data = []
    for f_name in reversed(files):
        if f_name.endswith(f'_rawdata'):
            print(f"Opening file {f_name}")
            with open('./GoodRuns/' + f_name, 'r') as f:
                all_data.extend(f.readlines())
            break
    all_data = [json.loads(d.strip()) for d in all_data if d.strip()]
    runs_sum = defaultdict(lambda: defaultdict(float))
    runs_count = defaultdict(lambda: defaultdict(float))
    for line in all_data:
        parameters = [str(i[1]) for i in sorted(line['parameters'].items(), key=lambda x: x[0])]
        key = '_'.join(parameters)
        for m in line['metrics']:
            runs_sum[key][m] += line['metrics'][m]
            runs_count[key][m] += 1
    runs = defaultdict(lambda: defaultdict(float))
    for k in runs_sum:
        for m in runs_sum[k]:
            runs[k][m] = runs_sum[k][m] / runs_count[k][m]

    for r in runs:
        print(r, runs_sum[r])

    with open(f'../simulation_gui/runs.js', 'w') as f:
        f.write(f"data_json = '{json.dumps(runs_sum)}';")


if __name__ == '__main__':
    fire.Fire()
