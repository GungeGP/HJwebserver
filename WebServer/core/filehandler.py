"""addPath() - maps one URL to one file on disk. The actual route-building
logic lives in WebServer.FileHandler (same pairing as core/auth.py ->
WebServer.auth, core/tableviewer.py -> WebServer.database.tableviewer):
this file is just the public method, FileHandler.py is the implementation.
"""

from WebServer.FileHandler import handle_file_request


class FileHandlerMixin:
    """addPath() - the only method this feature adds."""

    def addPath(self, url_path, file_path, public=False, roles=None):
        """Maps a URL to ANY file, safely resolving the path.

        When auth is enabled the page requires login unless public=True.
        roles=["admin"] restricts it to users with one of those roles.
        """
        self.routes = handle_file_request(self, url_path, file_path, public=public, roles=roles)
