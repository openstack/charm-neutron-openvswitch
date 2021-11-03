#!/usr/bin/env bash
set -eu

PATH="/snap/bin:/usr/local/bin:$PATH"
FILE=/var/lib/nagios/ovs_vsctl.out
TMP_FILE="$(tempfile)"
RC_FILE=/var/lib/nagios/ovs_vsctl.rc
LOCK_FILE=/var/lib/nagios/ovs_vsctl.lock
CMD="ovs-vsctl list-br"
GROUP="nagios"

if [ $# -gt 0 ]; then
    echo "This program will cache the output of '${CMD}' as follows"
    echo "    stdout + stderr -> ${FILE}"
    echo "    return code     -> ${RC_FILE}"
    echo
    echo "It does not accept any option or argument"
    exit 0
fi

sleep $[$RANDOM % 60 + 10]s # sleep 10-70s
if [ -f "${LOCK_FILE}" ]; then
    echo "Lock file (${LOCK_FILE}) in use, abandoning" >&2
    exit 1
fi

touch "${LOCK_FILE}"
$CMD 2>&1 > $TMP_FILE
RC=$?
echo $RC > $RC_FILE
mv $TMP_FILE $FILE
chown :$GROUP $FILE
chmod 644 $FILE
rm "${LOCK_FILE}"
exit 0
