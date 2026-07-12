#!/usr/bin/env python3
"""Enforce a close-only timeout around the real shutdown integration driver."""

import argparse
import os
import selectors
import subprocess
import sys
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--confirm", choices=("real", "accept", "cancel"), default="accept")
    parser.add_argument("--dirty", action="store_true")
    parser.add_argument("--executable")
    parser.add_argument("--project", default="configs/EDPGER02.simproject")
    parser.add_argument("--connect", action="store_true")
    parser.add_argument("--connect-ip")
    args = parser.parse_args()
    environment = os.environ.copy()
    if args.executable:
        command = [args.executable]
        environment["PLC_SHUTDOWN_INTEGRATION"] = args.confirm
        environment["PLC_SHUTDOWN_PROJECT"] = args.project
        if args.dirty: environment["PLC_SHUTDOWN_DIRTY"] = "1"
        if args.connect: environment["PLC_SHUTDOWN_CONNECT"] = "1"
        if args.connect_ip: environment["PLC_SHUTDOWN_CONNECT_IP"] = args.connect_ip
    else:
        command = [sys.executable, "scripts/integration_shutdown.py", "--confirm", args.confirm, "--project", args.project]
        if args.dirty: command.append("--dirty")
        if args.connect: command.append("--connect")
        if args.connect_ip: command.extend(("--connect-ip", args.connect_ip))
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, env=environment)
    selector = selectors.DefaultSelector(); selector.register(process.stdout, selectors.EVENT_READ)
    close_started = None; output = []
    while process.poll() is None:
        for key, _mask in selector.select(timeout=0.1):
            line = key.fileobj.readline()
            if line:
                output.append(line); print(line, end="", flush=True)
                if "CLOSE_INITIATED" in line: close_started = time.monotonic()
        if close_started is not None and time.monotonic() - close_started > args.timeout:
            process.terminate()
            try: process.wait(timeout=2)
            except subprocess.TimeoutExpired: process.kill(); process.wait()
            raise SystemExit(f"shutdown exceeded {args.timeout:.1f}s")
    remainder = process.stdout.read()
    if remainder: print(remainder, end="")
    raise SystemExit(process.returncode)


if __name__ == "__main__": main()
