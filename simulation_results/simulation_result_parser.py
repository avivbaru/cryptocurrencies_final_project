
import json
import os


def main():
    files = os.listdir('.')
    all_data = []
    for f_name in files:
        if f_name.endswith('_rawdata'):
            with open(f_name, 'r') as f:
                all_data.extend(f.readlines())
    all_data = [json.loads(d.strip()) for d in all_data if d]
    runs = {}
    for line in all_data:
        parameters = [str(i[1]) for i in sorted(line['parameters'].items(), key=lambda x: x[0])]
        runs['_'.join(parameters)] = line['metrics']
    with open('../simulation_gui/runs.json', 'w') as f:
        f.write(json.dumps(runs))


if __name__ == '__main__':
    main()