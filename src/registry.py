import grpc
from concurrent import futures
import threading

import relianet_pb2
import relianet_pb2_grpc

class RegistryServicer(relianet_pb2_grpc.RegistryServicer):
    def __init__(self):
        # Dictionary to store peers as "ip:port" -> NodeInfo object
        # This prevents duplicate registrations if a node restarts
        self.peers = {} 
        self.lock = threading.Lock() # Thread-safe operations for Docker

    def RegisterNode(self, request, context):
        peer_key = f"{request.ip}:{request.port}"
        
        with self.lock:
            if peer_key not in self.peers:
                self.peers[peer_key] = request
                print(f"[REGISTRY] New node joined: {request.ip}:{request.port}", flush=True)
            
            # Package the current list of peers to send back
            response = relianet_pb2.PeerList()
            response.peers.extend(self.peers.values())
            
        return response

def serve():
    # Allow up to 10 nodes to talk to the registry simultaneously
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    relianet_pb2_grpc.add_RegistryServicer_to_server(RegistryServicer(), server)
    
    # Listen on all Docker network interfaces for port 50051
    server.add_insecure_port('[::]:50051')
    print("[REGISTRY] Server alive and listening on port 50051...", flush=True)
    server.start()
    server.wait_for_termination()

if __name__ == '__main__':
    serve()