#!/usr/bin/env python3
# -*- coding: us-ascii -*-

import os

from nagios_plugin3 import (
    CriticalError,
    UnknownError,
    try_check,
    check_file_freshness,
)

INPUT_FILE = "/var/lib/nagios/ovs_vsctl.out"
INPUT_RC = "/var/lib/nagios/ovs_vsctl.rc"


def parse_output():
    """Parse the ovs-vsctl list-br output and raise alertable states."""

    if not os.path.exists(INPUT_FILE):
        raise UnknownError(
            "UNKNOWN: {} does not exist (yet?)".format(INPUT_FILE))

    if not os.path.exists(INPUT_RC):
        raise UnknownError(
            "UNKNOWN: {} does not exist (yet?)".format(INPUT_RC))

    try_check(check_file_freshness, INPUT_FILE)

    with open(INPUT_RC) as rc_raw:
        code = rc_raw.readline().strip()
        if code != "0":
            raise CriticalError("CRITICAL: ovs-vsctl list-br returns error")

    with open(INPUT_FILE) as brs_raw:
        brs = brs_raw.readlines()
        if len(brs) == 0:
            raise CriticalError(
                "CRITICAL: ovs-vsctl list-br returned no bridges")

        msg = ", ".join(br.strip() for br in brs)
        print("OK: {}".format(msg))


def main():
    """Define main subroutine."""
    try_check(parse_output)


if __name__ == "__main__":
    main()
