"""
test_aas_viewer_tree.py

F2: the tree in /aas-viewer opens with its root and first level expanded, so the
user sees the content of each entry instead of rows like "0: {4 items}".

The test image has no JavaScript engine, so these tests check the script the page serves.
"""

import re

import pytest

from .test_demo_pages import demo_users, login  # noqa: F401 - module fixture and login helper


@pytest.fixture
def viewer_html(app):
    resp = login(app, 'smoke.admin').get('/aas-viewer')
    assert resp.status_code == 200
    return resp.get_data(as_text=True)


def test_tree_opens_root_and_first_level(viewer_html):
    levels = re.search(r'buildNode\(data, null, (\d+)\)', viewer_html)
    assert levels, "renderTree must tell buildNode how many levels to open"
    assert int(levels.group(1)) == 2


def test_each_nested_level_opens_one_level_fewer(viewer_html):
    child_levels = re.findall(r'buildNode\(v, \w+, ([^)]+)\)', viewer_html)
    assert child_levels == ['openLevels - 1', 'openLevels - 1']
    assert 'const expanded = openLevels > 0;' in viewer_html
