# HJwebserver

A small Python web framework for internal tools: routes, static files, JSON
parsing, a database layer (SQLite / MSSQL / MySQL), login through Authentik
with roles from AD groups, audit log, security headers and optional HTTPS —
with almost no code to write.

## Documentation

The wiki lives in [`docs/guide/`](docs/guide/README.md):

- [Getting started](docs/guide/README.md) - install, minimal app, project layout
- [WebServer reference](docs/guide/webserver.md) - every method and parameter (`setDatabase`, `settings`, `route`, ...)
- [Routes & requests](docs/guide/routes.md) - handlers, `request.body`, `request.user`, sending responses
- [Database](docs/guide/database.md) - backends, drivers, running your own queries
- [Authentication](docs/guide/auth.md) - login through Authentik, `.env`, public pages, local development mode
- [Users and roles](docs/guide/users.md) - roles from Authentik groups, `roleHierarchy`, the `audit` command
- [Frontend](docs/guide/frontend.md) - injected scripts, `hjAuth`, logout button, form token, `Notify`
- [Side menu](docs/guide/menu.md) - `app.menu(...)`: a menu on the left of every page, items hidden by role, Admin button

## Install

```bash
pip install -r requirements.txt
```