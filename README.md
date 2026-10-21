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

# Running the Program

Option A: Docker Compose (recommended)
- Prerequisites: Install Docker Desktop.
- From the project root, run:
  - docker compose up --build
- Services started:
  - Zookeeper (internal)
  - Kafka (exposes 9092 for host, 29092 for internal broker-to-broker and containers)
  - Vertebrate Flask app (exposes http://localhost:5001)
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
