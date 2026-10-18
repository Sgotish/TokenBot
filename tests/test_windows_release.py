import hashlib
import io
import json
import struct

import pytest

from scripts.inspect_windows_release import inspect_asar


def fixture_archive(menu_name='profile-dropdown-test.js'):
    payload = b''
    files = {}
    for path, data in (
        ('package.json', b'{"version":"test"}'),
        ('webview/assets/' + menu_name, b'authMethod modelProviderName'),
    ):
        node = files
        parts = path.split('/')
        for part in parts[:-1]:
            node = node.setdefault(part, {'files': {}})['files']
        node[parts[-1]] = {
            'offset': str(len(payload)), 'size': len(data),
            'integrity': {'algorithm': 'SHA256', 'hash': hashlib.sha256(data).hexdigest()},
        }
        payload += data
    header = json.dumps({'files': files}).encode()
    return struct.pack('<4I', 4, len(header) + 8, len(header) + 4, len(header)) + header + payload


def test_inspection_does_not_certify_runtime_or_emit_vendor_code():
    result = inspect_asar(io.BytesIO(fixture_archive()))
    assert result['application_version'] == 'test'
    assert result['bundles'][0]['markers']['modelProviderName']
    assert not result['bundles'][0]['markers']['ambient_usage']
    assert 'authMethod modelProviderName' not in json.dumps(result)


def test_corrupted_menu_is_not_accepted_as_compatible():
    data = fixture_archive()
    with pytest.raises(ValueError, match='integrity mismatch'):
        inspect_asar(io.BytesIO(data[:-1] + b'X'))


def test_new_layout_requires_review():
    with pytest.raises(ValueError, match='structure changed'):
        inspect_asar(io.BytesIO(fixture_archive('renamed-menu.js')))


def test_truncated_archive_fails():
    with pytest.raises(ValueError, match='bounds'):
        inspect_asar(io.BytesIO(fixture_archive()[:-10]))
