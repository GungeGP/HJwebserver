"""Server-side includes for HTML pages.

Any HTML the framework serves may contain

    <!--#include file="header.html" -->

which is replaced by the contents of that file before the page is sent. Paths
are relative to the including file; a leading ``/`` means "from the static
folder root". Included files may themselves include others (up to a depth of
5). A file outside the static folder, or one that does not exist, is replaced
by an HTML comment describing the problem instead of failing the whole page.
"""

import os
import re

INCLUDE_RE = re.compile(rb'<!--#include\s+(?:file|virtual)="([^"]+)"\s*-->')
MAX_DEPTH = 5


def process_includes(content, current_file, root):
    """Expand include directives in ``content`` (bytes).

    current_file: absolute path of the file being served (for relative includes)
    root:         directory includes must stay inside (normally the static folder)
    """
    if b'<!--#include' not in content:
        return content
    root = os.path.realpath(root)
    return _expand(content, os.path.dirname(os.path.realpath(current_file)), root, 0, set())


def _expand(content, current_dir, root, depth, stack):
    def replace(match):
        target = match.group(1).decode('utf-8', 'replace').strip()
        if target.startswith('/'):
            candidate = os.path.join(root, target.lstrip('/'))
        else:
            candidate = os.path.join(current_dir, target)
        candidate = os.path.realpath(candidate)

        if os.path.commonpath([root, candidate]) != root:
            return f'<!-- include "{target}" refused: outside the static folder -->'.encode('utf-8')
        if not os.path.isfile(candidate):
            return f'<!-- include "{target}" not found -->'.encode('utf-8')
        if depth >= MAX_DEPTH or candidate in stack:
            return f'<!-- include "{target}" skipped: too deep or circular -->'.encode('utf-8')

        with open(candidate, 'rb') as f:
            included = f.read()
        return _expand(included, os.path.dirname(candidate), root, depth + 1, stack | {candidate})

    return INCLUDE_RE.sub(replace, content)
