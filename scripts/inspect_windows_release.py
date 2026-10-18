#!/usr/bin/env python3
"""Inspect a downloaded official MSIX without installing or changing the app.

Download source: https://learn.chatgpt.com/docs/enterprise/windows-deployment
Only metadata and feature markers are emitted; vendor code stays local.
This is structural evidence, NOT a native-menu compatibility certification.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import shutil
import xml.etree.ElementTree as ET
import zipfile


def digest(stream):
    result = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1024 * 1024), b''):
        result.update(chunk)
    return result.hexdigest()


def inspect_asar(stream):
    stream.seek(0, 2)
    total = stream.tell()
    stream.seek(0)
    prefix = stream.read(16)
    if len(prefix) != 16:
        raise ValueError('Truncated ASAR header')
    _, header_size, _, json_size = struct.unpack('<4I', prefix)
    if not 2 <= json_size <= 32 * 1024 * 1024 or header_size < json_size + 8:
        raise ValueError('Unsupported ASAR header')
    header = json.loads(stream.read(json_size))
    base = 8 + header_size

    def read_entry(entry):
        if entry.get('unpacked') or 'offset' not in entry:
            raise ValueError('Expected a packed archive entry')
        start, size = base + int(entry['offset']), int(entry['size'])
        if size < 0 or size > 32 * 1024 * 1024 or start < base or start + size > total:
            raise ValueError('Invalid ASAR entry bounds')
        stream.seek(start)
        data = stream.read(size)
        integrity = entry.get('integrity', {})
        if integrity.get('algorithm') == 'SHA256':
            if hashlib.sha256(data).hexdigest() != integrity['hash']:
                raise ValueError('ASAR entry integrity mismatch')
        return data

    package = json.loads(read_entry(header['files']['package.json']))
    assets = header['files']['webview']['files']['assets']['files']
    bundles = []
    for name, entry in assets.items():
        if not name.endswith('.js') or not name.startswith(('profile-dropdown', 'app-initial-')):
            continue
        data = read_entry(entry)
        code = data.decode('utf-8')
        bundles.append({
            'file': name,
            'sha256': hashlib.sha256(data).hexdigest(),
            'size': len(data),
            'integrity_metadata': bool(entry.get('integrity')),
            'markers': {marker: marker in code for marker in (
                'modelProviderName', 'authMethod', 'ambientUsage',
                'ambient_usage', 'codex.profileDropdown.usageRemaining',
                'authAccountId', 'currentAccountId',
            )},
        })
    if not any(b['file'].startswith('profile-dropdown') for b in bundles):
        raise ValueError('Menu structure changed; manual release review required')
    return {'application_version': package['version'], 'bundles': bundles}


def inspect_msix(path):
    with Path(path).open('rb') as source:
        sha = digest(source)
    with zipfile.ZipFile(path) as archive:
        manifest = ET.fromstring(archive.read('AppxManifest.xml'))
        identity = manifest.find('{http://schemas.microsoft.com/appx/manifest/foundation/windows10}Identity')
        if identity is None:
            raise ValueError('Missing MSIX identity')
        with archive.open('app/resources/app.asar') as packed, tempfile.TemporaryFile() as asar:
            shutil.copyfileobj(packed, asar)
            result = inspect_asar(asar)
        result.update({
            'msix_identity': identity.attrib,
            'msix_sha256': sha,
            'signature_file_present': 'AppxSignature.p7x' in archive.namelist(),
            'signature_trust_verified': False,
            'native_menu_runtime_verified': False,
        })
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('msix', type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect_msix(args.msix), ensure_ascii=False, indent=2))
