from collections import defaultdict


def capacity():
    with open('capacity') as f:
        all_capacities = f.readlines()
    all_capacities = [int(c.strip()) for c in all_capacities]
    total_capacities = len(all_capacities)
    buckets_to_keep, buckets_dict = get_buckets(all_capacities, 500000)

    for b in buckets_to_keep:
        print("{0} {1} {2:.3f}".format(b, buckets_dict[b], buckets_dict[b] / total_capacities))


def fee_base_msat():
    with open('fee_base_msat') as f:
        all_fee_base_msat = f.readlines()
    all_fee_base_msat = [int(c.strip()) for c in all_fee_base_msat]
    total_fee_base_msat = len(all_fee_base_msat)
    buckets_to_keep, buckets_dict = get_buckets(all_fee_base_msat, 100)

    for b in buckets_to_keep:
        print("{0} {1} {2:.3f}".format(b, buckets_dict[b], buckets_dict[b] / total_fee_base_msat))


def fee_rate_milli_msat():
    with open('fee_rate_milli_msat') as f:
        all_fee_rate_milli_msat = f.readlines()
    all_fee_rate_milli_msat = [int(c.strip()) for c in all_fee_rate_milli_msat]
    total_fee_rate_milli_msat = len(all_fee_rate_milli_msat)
    buckets_to_keep, buckets_dict = get_buckets(all_fee_rate_milli_msat, 1)

    for b in buckets_to_keep:
        print("{0} {1} {2:.3f}".format(b, buckets_dict[b], buckets_dict[b] /
                                       total_fee_rate_milli_msat))


def get_buckets(all_values, buckets_value):
    buckets_dict = defaultdict(int)
    for c in all_values:
        buckets_dict[c - (c % buckets_value)] += 1
    buckets = sorted(buckets_dict.keys())
    buckets_to_remove = [b for b in buckets if buckets_dict[b] < 50]
    buckets_to_keep = [b for b in buckets if b not in buckets_to_remove]

    for b in buckets_to_remove:
        temp = [abs(kb - b) for kb in buckets_to_keep]
        b_replace = buckets_to_keep[temp.index(min(temp))]
        buckets_dict[b_replace] += buckets_dict[b]
        buckets_dict[b] = 0
    return buckets_to_keep, buckets_dict


def main():
    # fee_base_msat()
    fee_rate_milli_msat()


if __name__ == '__main__':
    main()