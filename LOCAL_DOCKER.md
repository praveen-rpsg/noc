# Local Docker setup

This checkout runs under the Compose project `ainoc-local` and uses non-default
host ports so it can coexist with other projects:

| Service | URL / host port |
| --- | --- |
| Web UI | http://localhost:3010 |
| API | http://localhost:8011 |
| API docs | http://localhost:8011/docs |
| MongoDB | localhost:27117 |

## Start

Prerequisites: Docker Desktop with the Docker daemon running.

```bash
./docker.sh start
```

The first run creates an ignored `.env` from `docker/local.env.example` and
builds the backend and frontend images. To use different ports, edit `.env`
before starting. The Compose project name, service names, network, and volume
are scoped to this checkout, so another Compose project is not stopped or
reused.

## Operate

```bash
./docker.sh status
./docker.sh logs backend
./docker.sh stop
```

The default login is `admin@noc.com` / `admin123`.
