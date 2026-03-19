import argparse
import time
import grpc
import os
import json
import threading
from concurrent import futures

import relianet_pb2
import relianet_pb2_grpc

class PeerNodeServicer(relianet_pb2_grpc.PeerNodeServicer):
    def __init__(self, node_id):
        self.node_id = node_id
        # Define where this node will save its data (matches your docker-compose volume)
        self.data_dir = "/app/data"
        self.db_file = os.path.join(self.data_dir, f"node_{self.node_id}_db.json")
        
        self.data_store = {}
        self.lock = threading.Lock()
        
        os.makedirs(self.data_dir, exist_ok=True)
        self.load_from_disk()

    def load_from_disk(self):
        if os.path.exists(self.db_file):
            try:
                with open(self.db_file, "r") as f:
                    self.data_store = json.load(f)
                print(f"[NODE-{self.node_id}] Recovered {len(self.data_store)} items from disk.", flush=True)
            except Exception:
                print(f"[NODE-{self.node_id}] Starting fresh database.", flush=True)

    def save_to_disk(self):
        with open(self.db_file, "w") as f:
            json.dump(self.data_store, f, indent=4)

    def Replicate(self, request, context):
        """This handles the 'Submitting news' call from your client."""
        with self.lock:
            self.data_store[request.key] = request.value
            self.save_to_disk()
            
        print(f"[NODE-{self.node_id}] Saved: [{request.key}] -> {request.value}", flush=True)
        return relianet_pb2.Ack(success=True)

def register_with_registry(ip, port):
    registry_host = os.environ.get("REGISTRY_HOST", "localhost")
    print(f"[NODE] Contacting registry at {registry_host}:50051...", flush=True)
    channel = grpc.insecure_channel(f"{registry_host}:50051")
    stub = relianet_pb2_grpc.RegistryStub(channel)
    
    time.sleep(2) 
    try:
        # Note: Ensure these field names (ip, port) match your .proto exactly
        request = relianet_pb2.NodeInfo(ip=ip, port=port)
        response = stub.RegisterNode(request)
        print(f"[NODE] Registered! Peers: {len(response.peers)}", flush=True)
    except Exception as e:
        print(f"[NODE] Registry error: {e}", flush=True)

def serve(node_id, port):
    """This starts the actual gRPC server so the node can listen."""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    relianet_pb2_grpc.add_PeerNodeServicer_to_server(PeerNodeServicer(node_id), server)
    server.add_insecure_port(f'[::]:{port}')
    server.start()
    print(f"[NODE-{node_id}] gRPC Server listening on port {port}...", flush=True)
    server.wait_for_termination()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--id', type=str, required=True)
    parser.add_argument('--port', type=int, required=True)
    args = parser.parse_args()

    # 1. Register with the phonebook
    container_ip = f"node{args.id}"
    register_with_registry(container_ip, args.port)
    
    # 2. Start the server (Replaces the while True: sleep)
    serve(args.id, args.port)