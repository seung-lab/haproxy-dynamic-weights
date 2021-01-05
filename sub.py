#!/usr/bin/env python
from __future__ import print_function

import json
import logging

import redis

try:
    from subprocess import getstatusoutput
except ImportError:
    from commands import getstatusoutput  # Python2


SOCKET = "~/haproxy.sock"

log = logging.getLogger("haproxy-weight-balancer")
logging.basicConfig()

state = {}


def process_msg(message):
    # NOTE: Assume that weights for a host
    #       will be the same across all sites
    global state
    hostname = message["channel"]
    state_update = json.loads(message["data"])
    cmds = []

    if "weight" in state_update:
        new_weight = state_update["weight"]

        # Check old weight (only sampling one site)
        old_weight = 0
        for hosts in state.values():
            if hostname in hosts:
                old_weight = hosts[hostname]["weight"]
                break

        # If same weight, skip update
        if old_weight == new_weight:
            return

        # Log update
        perc = (new_weight * 100.0 / max(0.0001, old_weight)) - 100.0
        log.info(
            "Weight Update: %s from %s to %s (%.2f%%)"
            % (
                hostname,
                old_weight,
                new_weight,
                perc,
            )
        )

        # Build update command
        for pxname, hosts in state.items():
            if hostname in hosts:
                cmds.append("set weight %s/%s %d" % (pxname, hostname, new_weight))

        # Update HAProxy
        log.debug('Running `echo "%s" | socat stdio %s`' % ("; ".join(cmds), SOCKET))
        status = getstatusoutput(
            'echo "%s" | socat stdio %s' % ("; ".join(cmds), SOCKET)
        )
        if status[1].strip():
            log.error("State update failed: %s" % status[1])
            return

        # Update internal state
        for pxname, hosts in state.items():
            if hostname in hosts:
                hosts[hostname]["weight"] = new_weight
        return

    raise ValueError("Unsupported message: %s" % message["data"])


def update_state():
    global state
    status = getstatusoutput('echo "show stat" | socat %s stdio' % SOCKET)
    lines = status[1].split("\n")

    for l in lines:
        vals = l.split(",")

        # Skip Comments
        if not vals[0] or vals[0].startswith("#") or vals[0] == "":
            continue

        # Skip Frontend/Backend summary lines
        if vals[1] in ("FRONTEND", "BACKEND"):
            continue

        pxname, hostname, status, weight, check_status = (
            vals[0],
            vals[1],
            vals[17],
            vals[18],
            vals[36],
        )

        if pxname not in state:
            state[pxname] = {}

        state[pxname][hostname] = {
            "status": status,
            "weight": int(weight),
            "check_status": check_status,
        }


if __name__ == "__main__":
    with open("config.json", "r") as f:
        cfg = json.load(f)

    log.setLevel(cfg["log_level"])

    # Grab HAProxy state from socket
    update_state()
    hostnames = set(hostname for hosts in state.values() for hostname in hosts)

    # Connect to Redis / Subscribe to all hosts specified in HAProxy proxy states
    redis_db = redis.Redis(
        cfg["host"], cfg["port"], password=cfg["pw"], decode_responses=True
    )
    pubsub = redis_db.pubsub(ignore_subscribe_messages=True)
    pubsub.subscribe(hostnames)

    # Process incoming messages (blocking) - see handle_msg()
    for message in pubsub.listen():
        try:
            process_msg(message)
        except ValueError as e:
            log.error("Invalid message: %s" % message, exc_info=True)
            continue
