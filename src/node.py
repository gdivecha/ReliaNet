import argparse
import time
import grpc
import os

import relianet_pb2
import relianet_pb2_grpc

def register_with_registry(ip, port):
    # Docker Compose passes the registry hostname via environment variables
    registry_host = os.environ.get("REGISTRY_HOST", "localhost")
    
    print(f"[NODE] Attempting to contact registry at {registry_host}:50051...", flush=True)
    channel = grpc.insecure_channel(f"{registry_host}:50051")
    stub = relianet_pb2_grpc.RegistryStub(channel)
    
    # Give the Registry container a few seconds to fully boot up
    time.sleep(3) 
    
    try:
        request = relianet_pb2.NodeInfo(ip=ip, port=port)
        response = stub.RegisterNode(request)
        print(f"[NODE] Successfully registered! Active peers in network: {len(response.peers)}", flush=True)
    except Exception as e:
        print(f"[NODE] Failed to connect to registry: {e}", flush=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--id', type=str, required=True)
    parser.add_argument('--port', type=int, required=True)
    args = parser.parse_args()

    print(f"[NODE-{args.id}] Booting up on port {args.port}...", flush=True)
    
    # In Docker, the container name (e.g., 'node1') acts as its DNS/IP address
    container_ip = f"node{args.id}" 
    
    # Ping the registry
    register_with_registry(container_ip, args.port)

    # Keep the container alive (we will add the actual gRPC server for the node later)
    while True:
        time.sleep(86400)