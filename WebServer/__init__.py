"""The clean interface your teammates will actually use.

WebServer's implementation is split by feature under WebServer/core/ (see
that package's docstring) and composed here as mixins into one class, so
``app = WebServer(...)`` still works exactly as before - this file is just
the seam, not where the logic lives.
"""

from WebServer.core.server import DEFAULT_CSP, ServerMixin
from WebServer.core.filehandler import FileHandlerMixin
from WebServer.core.assets import AssetsMixin
from WebServer.core.auth import AuthMixin
from WebServer.core.tableviewer import TableViewerMixin
from WebServer.tableviewer import dateFilter, duration, selectFilter


class WebServer(ServerMixin, FileHandlerMixin, AssetsMixin, AuthMixin, TableViewerMixin):
    """The clean interface your teammates will actually use.

    See WebServer/core/ for the implementation, split one feature per file:
      ServerMixin       (core/server.py)      - construction, routing, TLS, start()
      FileHandlerMixin   (core/filehandler.py) - addPath()
      AssetsMixin        (core/assets.py)      - the framework's own bundled js/css assets
      AuthMixin          (core/auth.py)        - settings(auth=...), user/session/audit management
      TableViewerMixin   (core/tableviewer.py) - addTableViewer()
    """
