# Vertebrate
Industrial Data Centric Tech Stack




# Installation:
 
 - OPTIONAL for Frontend: create a Win11 or Server 2022 VM that can run VMs (https://learn.microsoft.com/en-us/virtualization/hyper-v-on-windows/user-guide/enable-nested-virtualization)
 - create a folder in C: called 10_Projects where all the project files will be (PLC; kafka,...)
 - OPTIONAL for Frontend: download and install codesys control win to be able to program and engineer a PLC (https://store.codesys.com/en/codesys-control-win-sl-1.html)
 - OPTIONAL for Frontend: install vscode (https://code.visualstudio.com/)
 - install github desktop and clone our repo and use VScode as the editor
 - install docker desktop (https://www.docker.com/products/docker-desktop/)
 - download the Kafka UI container from Github (https://github.com/provectus/kafka-ui)
 - Install Python from MS store
 - Download Kafka Scala 2.13   to run the zookeeper and broker (https://kafka.apache.org/downloads) - currently apps running from the terminal
 -   for Kafka: the folders must be like this:
      * for Kafka zookeper properties: dataDir=C:/10_Projects/Kafka/zookeeper
      * for KAFKA BROKER properties: log.dirs=C:/10_Projects/Kafka/kafka-logs
       
 - install/update Java JavaSetup8u421
 - OPTIONAL for Frontend: install UAexpert OPC viewer to be able to see and manupliate PLC data for testing

 for Vertebrate project, we need extra libraries
 on terminal run:  
   - pip install opcua confluent_kafka
   - pip install Flask

# Docker architecture

`docker compose up --build` brings up the core stack; the BaSyx services (bold) start only with
`--profile aas`. Services:

| Service | Image | Port(s) | Purpose |
|---|---|---|---|
| zookeeper | confluentinc/cp-zookeeper | (internal) | Kafka coordination |
| kafka | confluentinc/cp-kafka | 9092 (host), 29092 (internal) | real-time data bus (PLC → app) |
| db | postgres:15-alpine | (internal) | application database (PostgreSQL) |
| vertebrate-app | built from `Dockerfile` | 5001 | Flask app — SCADA, orders, AAS export/sync |
| **aas-environment** | eclipsebasyx/aas-environment | 8082 (8081 is the PLC simulator's status page) | Eclipse BaSyx v2 AAS + Submodel repositories (DotAAS Part 2 REST API) |
| **aas-ui** | eclipsebasyx/aas-gui | 3000 | BaSyx AAS Web UI — browse synced shells/submodels |

The app container is hardened (multi-stage build, non-root `appuser`, HEALTHCHECK
on `/login`). The BaSyx environment is configured via
`basyx/aas-env.properties` (in-memory backend + CORS for the Web UI).

**Key environment variables** (set in your shell or a `.env` file):
- `SECRET_KEY` — stable Flask session signing. If unset, the app generates an
  ephemeral key (sessions don't survive a restart).
- `BASYX_AAS_ENV_URL` — where the app pushes AAS to; with `--profile aas` set it to
  `http://aas-environment:8081` (the internal Docker hostname). Blank (the default) disables sync.

## AAS → BaSyx usage

1. `BASYX_AAS_ENV_URL=http://aas-environment:8081 docker compose --profile aas up --build -d`
   (add `--profile sim` for the PLC simulator) — wait ~30s for `aas-environment` to finish booting.
2. Log in (`User_Admin` / `12345`), open **AAS viewer** (`/aas-viewer`).
3. Enter an asset (e.g. `equipment` / `filling-machine-1`), click **Push to BaSyx**
   (or `POST /api/aas/sync/<type>/<id>`). Expect `{"status":"synced","submodel_count":3}`.
4. Open the **BaSyx Web UI** at http://localhost:3000 and browse the shell plus
   its DigitalNameplate / SiteHierarchy / OperationalData submodels.

> The BaSyx backend is in-memory — shells are lost when the environment container
> restarts. Persistent backends and a registry/discovery layer are planned follow-ups.
> The pinned BaSyx image tags may need refreshing over time (`docker pull`).

# Running the Program

Option A: Docker Compose (recommended)
- Prerequisites: Install Docker Desktop.
- From the project root, run:
  - docker compose up --build
- Services started: see the **Docker architecture** table above
  (Kafka stack, PostgreSQL, the Flask app on http://localhost:5001, plus the
  with `--profile aas` the BaSyx AAS environment on :8082 and Web UI on :3000).
- Data persistence:
  - The SQLite database file is stored in code/instance/UserManagement.db and is bind-mounted into the container. Your data persists across container restarts.
- Stop stack:
  - docker compose down

Option B: Manual (legacy)

--------------Kafka - Terminal --------------
C:\10_Projects\Kafka\kafka
- .\bin\windows\zookeeper-server-start.bat .\config\zookeeper.properties
- .\bin\windows\kafka-server-start.bat .\config\server.properties

--------------Kafka UI - Docker --------------
Run the Docker for the Kafka UI
- Kafka UI Container: http://localhost:8080/

- Cluster ID = **<check the kafka log>**  # was rYljdbXyQDSKW0su40H0kA
- from now on will use node **<check the kafka log>**:9092

--------------PLC - Taskbar --------------
- make sure the plc is running
- open UAexpert and subscribe to the programs tags

--------------Kafka producer and consumer - VScode --------------
- Run the producer PLCtoKafka python app
- Run the consumer App.py app 
- open trending at http://localhost:5001/
 
 


# Demo mode (PLC simulator, two users in two tabs)

Start the stack with the simulated PLC and seed the demo data:

    docker compose --profile sim up -d --build
    docker compose exec vertebrate-app python seed_demo.py

Two users can stay logged in side by side in one browser window. `localhost` and `127.0.0.1`
are different hosts for the browser, so each tab keeps its own session cookie:

| Tab | URL | User | Role |
|---|---|---|---|
| A | http://localhost:5001 | prod.manager | Production Manager – creates and releases orders |
| B | http://127.0.0.1:5001 | operator | Operator – runs the order in Process Instructions |

User_Admin (role Admin-All) can use either URL. The header shows `user · role` with a coloured
stripe per role (blue Production Manager, amber Operator, purple Admin).

- Idle logout: `SESSION_IDLE_MINUTES` (default 5, docker-compose sets 60 so the idle tab survives a recording).
- After a release in tab A, refresh Process Instructions in tab B to see the order in the dropdown.
- After rebuilding `plc-sim`, restart the bridges: `docker compose --profile sim restart plc2nexus nexus2plc`.
- PLC simulator status page: http://localhost:8081


# Testing

This project includes a comprehensive test suite for both application functionality and 21 CFR Part 11 audit trail compliance.

## Running Tests in Docker (Recommended)

### Prerequisites
- Docker Desktop running
- Containers started: `docker compose up -d`

### Audit Trail Tests
```bash
# Run all audit trail compliance tests (Tests 1-5)
docker compose exec vertebrate-app python /app/code/tests/run_all_tests.py

# Run individual test suites
docker compose exec vertebrate-app python /app/code/tests/test_audit_setup.py
docker compose exec vertebrate-app python /app/code/tests/test_audit_connection.py
