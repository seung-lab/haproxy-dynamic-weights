#!/usr/bin/env python
from __future__ import print_function

import json
import logging
import os
import socket
from time import sleep

import redis

BASE_CPU_USAGE = 0.01
MAX_CPU_USAGE = 0.9

log = logging.getLogger("haproxy-weight-balancer")
logging.basicConfig()


def get_cpu_weight():
    # Using last minute average
    cpu_usage = os.getloadavg()[0] / os.cpu_count()
    cpu_usage = min(max(BASE_CPU_USAGE, cpu_usage), MAX_CPU_USAGE)

    weight = int(
        255
        + (0 - 255) / (MAX_CPU_USAGE - BASE_CPU_USAGE) * (cpu_usage - BASE_CPU_USAGE)
    )
    return weight


def critical_status():
    # TODO: Check if other required services are down?
    return False


if __name__ == "__main__":
    with open("config.json", "r") as f:
        cfg = json.load(f)

    redis_db = redis.Redis(cfg["host"], cfg["port"], password=cfg["pw"])
    hostname = socket.gethostname()

    while True:
        if critical_status():
            weight = 0
        else:
            weight = get_cpu_weight()

        message = json.dumps({"weight": weight})
        log.debug("%s: %s" % (hostname, message))
        redis_db.publish(hostname, message)

        sleep(5)
