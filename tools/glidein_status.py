#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

# Description:
#   Equivalent to condor_status, but with glidein specific info

import argparse
import os.path
import sys
import time

from glideinwms.lib import condorMonitor

sys.path.append(os.path.join(sys.path[0], "../.."))


################################################################################
# GLOBAL

data = {}


################################################################################
def help():
    print(
        "glidein_status.py [-help] [-gatekeeper] [-glidecluster] [-singularity] [-withmonitor] [-bench] [-total] [-site] [-pool name] [-constraint name]"
    )
    print()
    print("Options:")
    print(" -gatekeeper   : Print out the glidein gatekeeper")
    print(" -glidecluster : Print out the glidein cluster nr")
    print(" -singularity  : Print out if singularity is used and its mode (if available)")
    print(" -container    : Print out if a container sw is used and its mode (if available). Implies -singularity")
    print(" -withmonitor  : Print out the monitoring VMs, too")
    print(" -bench        : Print out the benchmarking numbers, too")
    print(" -total        : Print out only the totals (skip details)")
    print(" -site         : Summarize by site (default by entry name)")
    print(" -pool         : Same as -pool in condor_status")
    print(" -constraint   : Same as -constraint in condor_status")
    print()


def cmp(a, b):
    return (a > b) - (a < b)


def machine_cmp(x, y):
    # sort on the Machine attribute
    res = cmp(data[x]["Machine"], data[y]["Machine"])
    if res == 0:
        res = cmp(x, y)
    return res


def fmt_time(t):
    now = int(time.time())
    diff = now - t
    diff_secs = diff % 60
    diff = diff // 60
    diff_mins = diff % 60
    diff = diff // 60
    diff_hours = diff % 24
    diff_days = diff // 24
    return "%i+%02i:%02i:%02i" % (diff_days, diff_hours, diff_mins, diff_secs)


def ltotal_cmp(x, y):  # Total last
    # Total always last
    if x == "Total":
        if y == "Total":
            return 0
        else:
            return 1
    elif y == "Total":
        return -1

    return cmp(x, y)


def entry_cmp(x, y):
    # Total always last
    if x == "Total":
        if y == "Total":
            return 0
        else:
            return 1
    elif y == "Total":
        return -1

    # split in pieces and sort end to front
    x_arr = x.split("@")
    y_arr = y.split("@")
    for i in (2, 1, 0):
        res = cmp(x_arr[i], y_arr[i])
        if res != 0:
            return res
    return 0


def get_opts():
    parser = argparse.ArgumentParser(description="Equivalent to condor_status but with glidein specific info")
    parser.add_argument(
        "-gatekeeper",
        "--gatekeeper",
        dest="want_gk",
        help="Print out the glidein gatekeeper",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "-glidecluster",
        "--glidecluster",
        dest="want_gc",
        help="Print out the glidein cluster",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "-singularity",
        "--singularity",
        dest="want_singularity",
        help="Print out if singularity is used",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "-container",
        "--container",
        dest="want_container",
        help="Print out if a container software is used",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "-withmonitor",
        "--with-monitor",
        dest="want_monitor",
        help="Print out the monitoring VMs",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "-bench",
        "--bench",
        dest="want_bench",
        help="Print out benchmarking numbers",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "-total",
        "--total",
        dest="total_only",
        help="Print out totals only (skip details)",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "-site",
        "--site",
        dest="summarize_site",
        help="Summarize by site (default by entry name)",
        action="store_true",
        default=False,
    )
    parser.add_argument("-pool", "--pool", dest="pool_name", help="Same as -pool in condor_status", default=None)
    parser.add_argument(
        "-constraint", "--constraint", dest="constraint", help="Same as -constraint in condor_status", default=None
    )

    args = parser.parse_args()
    return args


def main():
    opts = get_opts()

    pool_name = opts.pool_name
    constraint = opts.constraint
    want_gk = opts.want_gk
    want_gc = opts.want_gc
    want_monitor = opts.want_monitor
    want_bench = opts.want_bench
    want_singularity = opts.want_singularity
    want_container = opts.want_container
    total_only = opts.total_only
    summarize = "entry"
    if opts.summarize_site:
        summarize = "size"

    if not want_monitor:
        if constraint is None:
            constraint = "IS_MONITOR_VM =!= TRUE"
        else:
            constraint = "(%s) && (IS_MONITOR_VM =!= TRUE)" % constraint
    if want_container:
        want_singularity = want_container

    format_list = [
        ("Machine", "s"),
        ("State", "s"),
        ("Activity", "s"),
        ("GLIDEIN_Site", "s"),
        ("GLIDEIN_Factory", "s"),
        ("GLIDEIN_Name", "s"),
        ("GLIDEIN_Entry_Name", "s"),
        ("EnteredCurrentActivity", "i"),
    ]
    attrs = [
        "State",
        "Activity",
        "GLIDEIN_Site",
        "GLIDEIN_Factory",
        "GLIDEIN_Name",
        "GLIDEIN_Entry_Name",
        "EnteredCurrentActivity",
    ]

    if want_gk:
        format_list.append(("GLIDEIN_Gatekeeper", "s"))
        format_list.append(("GLIDEIN_GridType", "s"))
        attrs.append("GLIDEIN_Gatekeeper")
        attrs.append("GLIDEIN_GridType")

    if want_gc:
        format_list.append(("GLIDEIN_ClusterId", "i"))
        format_list.append(("GLIDEIN_ProcId", "i"))
        format_list.append(("GLIDEIN_Schedd", "s"))
        attrs.append("GLIDEIN_ClusterId")
        attrs.append("GLIDEIN_ProcId")
        attrs.append("GLIDEIN_Schedd")

    if want_singularity:
        format_list.append(("HAS_SINGULARITY", "b"))
        format_list.append(("GWMS_SINGULARITY_STATUS", "s"))
        attrs.append("HAS_SINGULARITY")
        attrs.append("GWMS_SINGULARITY_STATUS")

    if want_container:
        format_list.append(("GWMS_CONTAINERSW_FULL_VERSION", "s"))
        attrs.append("GWMS_CONTAINERSW_FULL_VERSION")

    if want_bench:
        format_list.append(("KFlops", "i"))
        format_list.append(("Mips", "i"))
        attrs.append("KFlops")
        attrs.append("Mips")

    cs = condorMonitor.CondorStatus(pool_name=pool_name)
    cs.load(constraint=constraint, format_list=format_list)

    global data
    data = cs.stored_data
    keys = list(data.keys())

    keys.sort(machine_cmp)

    counts_header = (
        "Total",
        "Owner",
        "Claimed/Busy",
        "Claimed/Retiring",
        "Claimed/Other",
        "Unclaimed",
        "Matched",
        "Other",
    )

    if want_bench:
        counts_header += ("GFlops", "  GIPS")

    print_mask = "%-39s %-9s"
    if want_gk:
        print_mask += " %-5s %-43s"
    print_mask += " %-19s %-19s"
    if want_gc:
        print_mask += " %-39s %-14s"
    if want_singularity:
        print_mask += " %-12s"
    if want_bench:
        print_mask += " %-5s %-5s"
    print_mask += " %-9s %-8s %-10s"

    header = ("Name", "Site")
    if want_gk:
        header += ("Grid", "Gatekeeper")
    header += ("Factory", "Entry")
    if want_gc:
        header += ("GlideSchedd", "GlideCluster")
    if want_singularity:
        header += ("Singularity",)
    if want_bench:
        header += ("MFlop", "Mips")
    header += ("State", "Activity", "ActvtyTime")

    if not total_only:
        print()
        print(print_mask % header)
        print()

    counts = {"Total": {}}
    for c in counts_header:
        counts["Total"][c] = 0

    for vm_name in keys:
        el = data[vm_name]

        cel = {}  # this will have all the needed attributes (??? if nothing else)
        for a in attrs:
            if a in el:
                cel[a] = el[a]
            else:
                cel[a] = "???"
        if cel["EnteredCurrentActivity"] != "???":
            cel["EnteredCurrentActivity"] = fmt_time(int(cel["EnteredCurrentActivity"]))

        state = cel["State"]
        activity = cel["Activity"]

        if "KFlops" in el:
            gflops = el["KFlops"] * 1.0e-6
            mflops_str = "%i" % (el["KFlops"] // 1000)
        else:
            mflops = 0.0
            mflops_str = "???"

        if "Mips" in el:
            gips = el["Mips"] * 1.0e-3
            mips_str = el["Mips"]
        else:
            mips = 0.0
            mips_str = "???"

        if summarize == "site":
            sum_str = cel["GLIDEIN_Site"]
        else:
            sum_str = "{}@{}@{}".format(cel["GLIDEIN_Entry_Name"], cel["GLIDEIN_Name"], cel["GLIDEIN_Factory"])
        if sum_str not in counts:
            counts[sum_str] = {}
            for c in counts_header:
                counts[sum_str][c] = 0

        for t in ("Total", sum_str):
            ct = counts[t]
            ct["Total"] += 1
            if state in ("Owner", "Unclaimed", "Matched"):
                ct[state] += 1
            elif state == "Claimed":
                if activity in ("Busy", "Retiring"):
                    ct[f"{state}/{activity}"] += 1
                else:
                    ct["Claimed/Other"] += 1
            else:
                ct["Other"] += 1
            if want_bench:
                ct["GFlops"] += gflops
                ct["  GIPS"] += gips

        if not total_only:
            print_arr = (vm_name, cel["GLIDEIN_Site"])
            if want_gk:
                print_arr += (cel["GLIDEIN_GridType"], cel["GLIDEIN_Gatekeeper"])
            print_arr += ("{}@{}".format(cel["GLIDEIN_Name"], cel["GLIDEIN_Factory"]), cel["GLIDEIN_Entry_Name"])
            if want_gc:
                print_arr += (cel["GLIDEIN_Schedd"], "%i.%i" % (cel["GLIDEIN_ClusterId"], cel["GLIDEIN_ProcId"]))
            if want_singularity:
                singularity_str = "No"
                if "HAS_SINGULARITY" in el and el["HAS_SINGULARITY"]:
                    singularity_str = "Yes"
                # Get more details if possible
                if "GWMS_SINGULARITY_STATUS" in el:
                    singularity_str = el["GWMS_SINGULARITY_STATUS"]
                print_arr += (singularity_str,)
            if want_bench:
                print_arr += (mflops_str, mips_str)
            print_arr += (state, activity, cel["EnteredCurrentActivity"])

            print(print_mask % print_arr)

    print()

    count_print_mask = "%39s"
    for c in counts_header:
        count_print_mask += " %%%is" % len(c)
    print(count_print_mask % (("",) + counts_header))

    ckeys = list(counts.keys())

    if summarize == "site":
        ckeys.sort(ltotal_cmp)
    else:  # default is entry
        ckeys.sort(entry_cmp)

    if len(ckeys) > 1:
        print()  # put a space before the entry names

    count_print_val = None
    for t in ckeys:
        if t == "Total":
            print()  # put an empty line before Total
            count_print_val = [t]
        else:
            count_print_val = [""]
        for c in counts_header:
            count_print_val.append(int(counts[t][c]))

        print(count_print_mask % tuple(count_print_val))

    print()


if __name__ == "__main__":
    main()
