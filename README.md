# HJwebserver

A small Python web framework for internal tools: routes, static files, JSON
parsing, a database layer (SQLite / MSSQL / MySQL), login through Authentik
with roles from AD groups, audit log, security headers and optional HTTPS —
with almost no code to write.

## Documentation

The wiki lives in [`docs/`](docs/README.md):

- [Getting started](docs/README.md) - install, minimal app, project layout
- [WebServer reference](docs/webserver.md) - every method and parameter (`setDatabase`, `settings`, `route`, ...)
- [Routes & requests](docs/routes.md) - handlers, `request.body`, `request.user`, sending responses
- [Database](docs/database.md) - backends, drivers, running your own queries
- [Authentication](docs/auth.md) - login through Authentik, `.env`, public pages, local development mode
- [Users and roles](docs/users.md) - roles from Authentik groups, `roleHierarchy`, the `audit` command
- [Frontend](docs/frontend.md) - injected scripts, `hjAuth`, logout button, form token, `Notify`

## Install

```bash
pip install -r requirements.txt
```