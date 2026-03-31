# 🌐 ReliaNet: Distributed Truth-Seeking Network
**COE 892 - Distributed Systems Project**

ReliaNet is a high-availability, decentralized Key-Value (K-V) store engineered for Humanitarian Disaster Response and Critical News Infrastructure. In scenarios where centralized servers are destroyed or network links are unstable, ReliaNet ensures life-saving data—such as EMS coordinates or emergency alerts—remains synchronized and accessible across a distributed cluster.

---

## 🏗 Project Architecture

The system utilizes five core technical layers to eliminate Single Points of Failure (SPOF):
1.  **FastAPI Gateway:** The system utilizes five core technical layers to eliminate Single Points of Failure (SPOF):
2.  **The Registry:** A centralized gRPC service discovery module that tracks node health via heartbeats; it automatically evicts dead nodes from the active cluster.
3.  **Peer Nodes (gRPC):** 5 high-speed containers that manage data replication and participate in consensus voting.
4.  **Self-Healing Protocol (RabbitMQ):** An asynchronous "Anti-Entropy" mechanism that uses cryptographic hashes to detect and repair out-of-sync nodes after a reboot.
5.  **Quorum Engine:** A deterministic majority-voting system ($Threshold = \lfloor N/2 \rfloor + 1$) that ensures data consistency even during partial network failures.

---

## 🚀 Quick Start

### 1. Prerequisites
* Docker & Docker Compose (Required for cluster simulation)
* Python 3.9+ (Optional, for local script execution)

### 2. Setup
1. Extract the Submission ZIP: Unzip the zip file to your local directory.
2. Pristine Launch: Run the following command to wipe any old data, rebuild the images, and launch the cluster:
    ```bash
    make reset
    ```
3. Makefile Command Reference
    * **`make up`** (`docker-compose up -d --build`): Starts the cluster in detached mode.
    * **`make down`** (`docker-compose down -v`): Wipes the cluster and removes orphaned containers.
    * **`make logs`** (`docker-compose logs -f`): Watches real-time cluster communication.
    * **`make discard`** (`rm -rf node_data/node*/*`): Clears all persistent JSON storage.
    * **`make stop3`** (`docker-compose stop node3`): Simulates a failure of the slow node.
    * **`make stop4and5`** (`docker-compose stop node4 node5`): Prepares the cluster for Quorum testing.
    * **`make reset`** (Runs `scripts/reset.sh`): Wipes everything and launches a pristine cluster.

---

## 🎮 Interactive Demo & Feature Testing
The demo should be performed via the API Dashboard (http://localhost:8000/docs) or the Streamlit Visualization UI (http://localhost:8501).
1. Testing Data Replication
    - Action: Perform a POST to `/api/news` (e.g., `Key: "Status", Value: "Safe"`).
    - Verification: Confirm the data appears in the node_data/ folders for all 5 containers simultaneously.

2. Testing Fault Tolerance (N-2 Survival)
    - Action: Run `make stop4and5`.
    - Testing: Perform a GET request for the `"Status"` key.
    - Result: The system returns the correct value because a majority (3/5) of nodes are still operational.

3. Testing Latency Resilience (The Slow Node 3)
    - Action: Trigger a read/write involving Node 3 (programmed with a 3s network lag).
    - The Result: The Gateway returns a response in ~1.5 seconds.
    - Engineering Detail: The system uses a 1.5s gRPC deadline; it ignores the lagging node once the Quorum threshold is met by faster peers.

4. Testing Self-Healing (Anti-Entropy)
    - Action: While nodes are stopped, update a key via the API. Then run `make start4and5`.
    - The Process: The rebooted nodes will broadcast their state hashes over RabbitMQ; the Auditor will detect the mismatch and automatically sync the missing data.

---

## 📂 Project Structure
- `node_data/`: Persistent JSON storage for each node (`node1` through `node5`).
- `proto/`: gRPC service definitions (`relianet.proto`).
- `scripts/`: Contains `reset.sh` for pristine cluster rebuilds.
- `src/`: Core Python source code.
    - `gateway.py`: FastAPI server for load balancing.
    - `node.py`: Core logic for consensus and sync.
    - `registry.py`: Service discovery and health monitoring.
    - `ui.py`: Streamlit visualization dashboard.
- `Makefile`: Developer shortcuts for demo automation.
- `docker-compose.yml`: Cluster orchestration configuration.

---