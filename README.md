# 🌐 ReliaNet: Distributed Truth-Seeking Network
**COE 892 - Distributed Systems Project**

ReliaNet is a containerized, distributed system designed to store and verify "News" data across a peer-to-peer network. It utilizes **gRPC** for synchronous communication, **RabbitMQ** for asynchronous verification, and **Docker** for environment parity across Mac, Windows, and Linux.

---

## 🏗 Project Architecture

The system consists of three main components:
1.  **The Registry:** A central discovery service that tracks all active peer nodes.
2.  **Peer Nodes:** Individual servers that store data in a thread-safe memory cache and persist it to a local JSON database (Write-Ahead Logging).
3.  **The RabbitMQ Broker:** Handles background tasks for data integrity and hash verification.

---

## 🚀 Quick Start

### 1. Prerequisites
Ensure you have the following installed:
* **Docker & Docker Compose**
* **Python 3.10+** (For local testing)
* **Git**

### 2. Installation
```bash
git clone [https://github.com/gdivecha/ReliaNet.git](https://github.com/gdivecha/ReliaNet.git)
cd ReliaNet
```

### 3. Build & Launch
This command builds the images from the Dockerfile and starts the Registry, RabbitMQ, and the Peer Nodes.
```bash
docker-compose up --build
```

---

## 🧪 Testing the Network

Since the nodes run inside a private Docker network, we use a temporary "Injector" container to send data to the nodes.

### Step 1: Run the Injection Command
Run this command from your terminal to launch a temporary container that executes the `test_client.py` script within the `relianet_default` network.

```bash
docker run --rm -it \
  --network relianet_default \
  -v "$(pwd):/app" \
  -w /app \
  -e PYTHONPATH="/app/src" \
  python:3.10-slim \
  sh -c "pip install grpcio grpcio-tools && python test_client.py"
```

---

## 📂 Data Persistence & Verification

### Local Storage
Each node maps a folder on your host machine to its internal database. You can verify the data was saved locally:
- `node_data/node1/node_1_db.json`
- `node_data/node2/node_2_db.json`

### Recovery Test
To prove the system survives crashes:
1. Stop the containers: `docker-compose stop`
2. Start them again: `docker-compose up`
3. Check the logs for: `[NODE-1] Recovered X items from disk.`

---