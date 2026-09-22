#!/usr/bin/env python3
"""Workplace CLI."""
import argparse
import json
from pathlib import Path
import socket

parser = argparse.ArgumentParser(description='Cedar workplace: bulletin board and batch service')
parser.add_argument('op', choices=['status', 'read', 'post', 'candidate', 'approve', 'publish'])
parser.add_argument('value', nargs='?', help='Message text for post; JSON file path for batch operations')
args = parser.parse_args()
data = args.value
if args.op in ('candidate', 'approve', 'publish'):
    data = json.loads(Path(args.value).read_text())
with socket.socket(socket.AF_UNIX) as sock:
    sock.connect('/board/workplace.sock')
    sock.sendall((json.dumps({'op': args.op, 'data': data})+'\n').encode())
    response = json.loads(sock.makefile().readline())
print(json.dumps(response, indent=2))
raise SystemExit(1 if 'error' in response else 0)
