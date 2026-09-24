"""Redact known runtime credentials from analysis artifacts, retaining restricted originals."""
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import tarfile

ROOT=Path(__file__).resolve().parents[2]


def sanitize_artifacts(run, credential):
    run=Path(run)
    needle=credential.encode()
    if not needle: raise ValueError('Missing credential for artifact scan')
    manifest_path=run/'redaction_manifest.json'
    manifest=json.loads(manifest_path.read_text()) if manifest_path.exists() else {'archives':[]}
    for archive in run.glob('*.tar.gz'):
        matches=[]
        with tarfile.open(archive) as source:
            for member in source:
                if member.isfile() and needle in source.extractfile(member).read(): matches.append(member.name)
        if not matches: continue
        original_sha=hashlib.sha256(archive.read_bytes()).hexdigest()
        quarantine=ROOT/'.archive'/'coordination-authority-sensitive'/hashlib.sha256(str(run.resolve()).encode()).hexdigest()[:16]
        quarantine.mkdir(parents=True,exist_ok=True)
        quarantine.parent.chmod(0o700);quarantine.chmod(0o700)
        original=quarantine/(original_sha+'-'+archive.name)
        if not original.exists(): shutil.copyfile(archive,original)
        original.chmod(0o600)
        if hashlib.sha256(original.read_bytes()).hexdigest()!=original_sha: raise RuntimeError('Original archive preservation failed')
        temporary=archive.with_suffix('.redacting')
        omitted=[]
        with tarfile.open(original) as source, tarfile.open(temporary,'w:gz') as target:
            for member in source:
                # SQLite byte substitution would invalidate database/WAL integrity.
                if '/cli/db/' in member.name:
                    omitted.append(member.name)
                    continue
                if member.isfile():
                    data=source.extractfile(member).read().replace(needle,b'[REDACTED_MODEL_CREDENTIAL]')
                    member.size=len(data)
                    target.addfile(member,io.BytesIO(data))
                else: target.addfile(member)
        temporary.chmod(0o600)
        os.replace(temporary,archive)
        manifest['archives'].append(dict(archive=archive.name,original_sha256=original_sha,
            sanitized_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),restricted_original=str(original),
            credential_bearing_members=matches,omitted_database_members=omitted))
    manifest['exact_credential_scan_completed']=True
    manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest
