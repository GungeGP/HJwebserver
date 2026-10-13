"""WebServer's implementation, split one feature per file:

  * server.py       - construction, routing, TLS, database wiring, start()
  * filehandler.py  - addPath() (pairs with WebServer.FileHandler)
  * assets.py       - the framework's own bundled js/css assets
  * auth.py         - settings(auth=...) and user/session/audit management
  * tableviewer.py  - addTableViewer() (pairs with WebServer.database.tableviewer)

WebServer/__init__.py composes these as mixins into a single WebServer class,
so from a consumer's point of view nothing here is visible or changes - it's
purely about where a maintainer goes to find the code for one feature instead
of reading one large file end to end.
"""
