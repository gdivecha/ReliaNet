# 🌐 ReliaNet: Distributed Truth-Seeking Network
**COE 892 - Distributed Systems Project**

ReliaNet is a fault-tolerant, self-healing distributed database designed to store and verify "News" data across a peer-to-peer network. It features **Quorum Consensus** for data consistency and an **API Gateway** for modern web integration.

---

## 🏗 Project Architecture

The system consists of five main layers:
1.  **FastAPI Gateway:** A modern REST API that translates HTTP traffic into gRPC commands for the cluster.
2.  **The Registry:** A central gRPC discovery service that tracks all active peer nodes.
3.  **Peer Nodes:** Servers that store data in a thread-safe memory cache and persist it to local JSON databases.
4.  **RabbitMQ Auditor:** An asynchronous "immune system" that detects data mismatches (hash-based) and automatically repairs out-of-sync nodes.
5.  **Quorum Engine:** A majority-voting system that ensures the most recent "truth" is served even if nodes are offline.

---

## 🚀 Quick Start

### 1. Prerequisites
* **Docker & Docker Compose**
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

## 🎮 Interactive Demo (The Web UI)
Once the cluster is running, you can interact with the network directly through your browser—no terminal commands required.
1. Open the API Dashboard: http://localhost:8000/docs
2. Write Data (POST): Use the `/api/news` endpoint to replicate a news string across all nodes.
3. Read Data (GET): Use the `/api/news` endpoint to trigger a Quorum Read. Node 1 will poll its peers, reach a majority consensus, and return the verified value.

---

## 🧪 Fault Tolerance & Recovery

### Testing the "Immune System"
ReliaNet is designed to heal itself automatically:
1. Kill a Node: `docker-compose stop node2`
2. Update Data: Use the API (or `test_client.py`) to write new data while Node 2 is dead.
3. Restart & Heal: `docker-compose start node2`
4. Watch the Logs: Within 10-15 seconds, you will see Node 1 or 3 detect the mismatch via RabbitMQ and "push" the missing data to Node 2:
`⚠️ [NODE-1 AUDIT] Mismatch with Node 2! Sending missing data...`

### Testing the Quorum Read
Even if one node is down, the system remains highly available. The QuorumRead logic will still return the correct data as long as a majority (N/2 + 1) of nodes are healthy.

---

## 📂 Project Structure
- `proto/`: Contains the gRPC service definitions (`relianet.proto`).
- `src/node.py`: The core peer logic, including Quorum voting and RabbitMQ auditing.
- `src/gateway.py`: The FastAPI server providing the REST interface.
- `node_data/`: Persistent JSON storage for each individual node.
- `test_client.py`: A raw gRPC Python client for internal network testing.

---