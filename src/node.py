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
    def __init__(self, node_id, port):
        self.node_id = node_id
        self.port = port 
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
        """Handles receiving data and propagating it to all other peers."""
        with self.lock:
            # Prevent infinite loops: if we already have this exact key/value, just ACK
            if request.key in self.data_store and self.data_store[request.key] == request.value:
                return relianet_pb2.Ack(success=True)

            self.data_store[request.key] = request.value
            self.save_to_disk()
            
        print(f"[NODE-{self.node_id}] Saved locally. Propagating to network...", flush=True)

        # --- DAY 4 REPLICATION LOGIC ---
        registry_host = os.environ.get("REGISTRY_HOST", "registry")
        try:
            with grpc.insecure_channel(f"{registry_host}:50051") as channel:
                stub = relianet_pb2_grpc.RegistryStub(channel)
                # Ask Registry for the 'Phonebook' using the new GetPeers RPC
                response = stub.GetPeers(relianet_pb2.Empty())
                
                for peer in response.peers:
                    # Skip yourself (don't send data back to the same node)
                    if peer.port == self.port:
                        continue
                    
                    try:
                        # Establish connection to the neighbor node
                        with grpc.insecure_channel(f"{peer.ip}:{peer.port}") as p_channel:
                            p_stub = relianet_pb2_grpc.PeerNodeStub(p_channel)
                            p_stub.Replicate(request)
                            print(f"[NODE-{self.node_id}] Successfully replicated to {peer.ip}:{peer.port}", flush=True)
                    except Exception as e:
                        print(f"[NODE-{self.node_id}] Replication failed for {peer.ip}: {e}", flush=True)
                        
        except Exception as e:
            print(f"[NODE-{self.node_id}] Registry discovery error: {e}", flush=True)

        return relianet_pb2.Ack(success=True)

def register_with_registry(ip, port):
    """Registers this node with the central discovery service."""
    registry_host = os.environ.get("REGISTRY_HOST", "registry")
    # Give the server a moment to start up before registering
    time.sleep(3) 
    try:
        channel = grpc.insecure_channel(f"{registry_host}:50051")
        stub = relianet_pb2_grpc.RegistryStub(channel)
        request = relianet_pb2.NodeInfo(ip=ip, port=port)
        stub.RegisterNode(request)
        print(f"[NODE] Registered with Registry as {ip}:{port}", flush=True)
    except Exception as e:
        print(f"[NODE] Registration failed: {e}", flush=True)

def serve(node_id, port):
    """Starts the gRPC server to listen for Replicate and QuorumRead calls."""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    relianet_pb2_grpc.add_PeerNodeServicer_to_server(PeerNodeServicer(node_id, port), server)
    server.add_insecure_port(f'[::]:{port}')
    server.start()
    print(f"[NODE-{node_id}] gRPC Server listening on port {port}...", flush=True)
    server.wait_for_termination()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--id', type=str, required=True)
    parser.add_argument('--port', type=int, required=True)
    args = parser.parse_args()

    # Run registration in a background thread so the server can start immediately
    container_ip = f"node{args.id}"
    threading.Thread(target=register_with_registry, args=(container_ip, args.port), daemon=True).start()
    
    serve(args.id, args.port)