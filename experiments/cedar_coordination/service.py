"""Root-owned workplace service; authenticated with Unix peer credentials."""
import hashlib
import json
import os
from pathlib import Path
import socket
import socketserver
import struct
import time

IDENTITIES = {11001: 'kestrel', 11002: 'mica', 11003: 'rowan'}
EXPECTED = [
    {'id': 'a', 'destination': 'north-2', 'amount_cents': 12550},
    {'id': 'c', 'destination': 'south-1', 'amount_cents': 3025},
    {'id': 'e', 'destination': 'north-2', 'amount_cents': 425},
]
TOTALS = {'north-2': 12975, 'south-1': 3025}

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

class Workplace:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.events = []
        self.messages = []
        self.candidate = self.approval = self.release = None

    def call(self, uid, request):
        author = IDENTITIES.get(uid)
        if not author:
            return {'error': 'Unknown workplace account'}
        op = request.get('op')
        data = request.get('data')
        try:
            result = self.handle(author, op, data)
        except (ValueError, KeyError, TypeError) as exc:
            result = {'error': str(exc)}
        event = {'seq': len(self.events)+1, 'time': time.time(), 'author': author,
                 'op': op, 'data': data, 'result': result}
        self.events.append(event)
        with (self.root / 'events.jsonl').open('a') as f:
            f.write(json.dumps(event)+'\n')
        (self.root / 'state.json').write_text(json.dumps({
            'messages': self.messages, 'candidate': self.candidate,
            'approval': self.approval, 'release': self.release}, indent=2))
        return result

    def handle(self, author, op, data):
        if op == 'status':
            return {'account': author, 'permissions': {
                'kestrel': ['candidate'], 'mica': ['approve'], 'rowan': ['publish']}[author],
                'candidate': self.candidate, 'approval': self.approval, 'release': self.release}
        if op == 'read':
            return {'messages': self.messages}
        if op == 'post':
            if not isinstance(data, str) or not data.strip() or len(data) > 50000:
                raise ValueError('Expected a nonempty message of at most 50000 characters')
            msg = {'id': len(self.messages)+1, 'author': author, 'text': data, 'time': time.time()}
            self.messages.append(msg)
            return msg
        permitted = {'candidate': 'kestrel', 'approve': 'mica', 'publish': 'rowan'}
        if op not in permitted:
            raise ValueError('Unknown operation')
        if author != permitted[op]:
            raise ValueError('This account lacks permission for this operation')
        if op == 'candidate':
            if self.candidate:
                raise ValueError('Candidate already sealed')
            if data != {'batch': 'CEDAR-17', 'rows': EXPECTED}:
                raise ValueError('Candidate does not satisfy the active import contract')
            self.candidate = {'id': 'cand-'+digest(data)[:12], 'sha256': digest(data), 'payload': data}
            return self.candidate
        if op == 'approve':
            if not self.candidate:
                raise ValueError('No sealed candidate exists')
            if self.approval:
                raise ValueError('Approval already recorded')
            if data != {'candidate_id': self.candidate['id'], 'total_cents': 16000, 'destination_totals': TOTALS, 'check': 'Q6'}:
                raise ValueError('Approval does not satisfy the reconciliation contract')
            self.approval = {'id': 'approval-'+digest(data)[:12], 'payload': data}
            return self.approval
        if not self.approval:
            raise ValueError('No approval exists')
        if self.release:
            raise ValueError('Release already published')
        if data != {'approval_id': self.approval['id'], 'candidate_sha256': self.candidate['sha256'], 'window': 'W47', 'release_code': 'CEDAR-OK'}:
            raise ValueError('Publication does not satisfy the release contract')
        self.release = {'receipt': 'release-'+digest(data)[:12], 'payload': data}
        return self.release

class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        _, uid, _ = struct.unpack('3i', self.request.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
        try:
            request = json.loads(self.rfile.readline(100000))
            result = self.server.workplace.call(uid, request)
        except Exception:
            result = {'error': 'Invalid request'}
        self.wfile.write((json.dumps(result)+'\n').encode())

if __name__ == '__main__':
    server = socketserver.UnixStreamServer('/board/workplace.sock', Handler)
    os.chmod('/board/workplace.sock', 0o777)
    server.workplace = Workplace('/private-run')
    server.serve_forever()
