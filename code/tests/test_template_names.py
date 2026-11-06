"""
test_template_names.py

Every template and static file the code references must exist with exactly that
spelling.  macOS file systems ignore case, Linux (the Docker image, CI) does not:
render_template('updated-User.html') worked on a Mac and crashed in the container
because the file is Updated-User.html.
"""

import os
import re

import pytest

CODE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES_DIR = os.path.join(CODE_DIR, 'templates')
STATIC_DIR = os.path.join(CODE_DIR, 'static')

TEMPLATE_REF = re.compile(
    r"render_template\(\s*['\"]([^'\"]+)['\"]|\{%\s*(?:extends|include)\s+['\"]([^'\"]+)['\"]")
STATIC_REF = re.compile(r"url_for\(\s*['\"]static['\"]\s*,\s*filename\s*=\s*['\"]([^'\"]+)['\"]")


def _files_below(root):
    """Relative paths of all files below root, with their exact spelling."""
    found = set()
    for dirpath, _dirs, files in os.walk(root):
        for name in files:
            found.add(os.path.relpath(os.path.join(dirpath, name), root).replace(os.sep, '/'))
    return found


def _sources():
    for name in sorted(os.listdir(CODE_DIR)):
        if name.endswith('.py'):
            yield os.path.join(CODE_DIR, name)
    for name in sorted(_files_below(TEMPLATES_DIR)):
        if name.endswith('.html'):
            yield os.path.join(TEMPLATES_DIR, name)


def _references():
    refs = []
    for path in _sources():
        with open(path, encoding='utf-8', errors='replace') as f:
            src = f.read()
        where = os.path.relpath(path, CODE_DIR)
        refs += [(where, 'templates', m.group(1) or m.group(2)) for m in TEMPLATE_REF.finditer(src)]
        refs += [(where, 'static', m.group(1)) for m in STATIC_REF.finditer(src)]
    return refs


REFERENCES = _references()
EXISTING = {'templates': _files_below(TEMPLATES_DIR), 'static': _files_below(STATIC_DIR)}


def test_references_were_found():
    assert len(REFERENCES) > 50


@pytest.mark.parametrize('where, folder, name', REFERENCES,
                         ids=[f'{w}:{n}' for w, _, n in REFERENCES])
def test_referenced_file_exists_with_exact_spelling(where, folder, name):
    if name in EXISTING[folder]:
        return
    same_but_case = [f for f in EXISTING[folder] if f.lower() == name.lower()]
    assert not same_but_case, f"{where} references {folder}/{name}, the file is {folder}/{same_but_case[0]}"
    pytest.fail(f"{where} references {folder}/{name}, which does not exist")
