import grpc
from concurrent import futures
import threading

import relianet_pb2
import relianet_pb2_grpc

class RegistryServicer(relianet_pb2_grpc.RegistryServicer):
    def __init__(self):
        # Dictionary to store peers as "ip:port" -> NodeInfo object
        self.peers = {} 
        self.lock = threading.Lock() 

    def RegisterNode(self, request, context):
        """Standard registration for new nodes."""
        peer_key = f"{request.ip}:{request.port}"
        
        with self.lock:
            if peer_key not in self.peers:
                self.peers[peer_key] = request
                print(f"[REGISTRY] New node joined: {request.ip}:{request.port}", flush=True)
            
            response = relianet_pb2.PeerList()
            response.peers.extend(self.peers.values())
            
        return response

    # --- NEW FOR DAY 4 REPLICATION ---
    def GetPeers(self, request, context):
        """Handles the 'Empty' request and returns all active peers."""
        with self.lock:
            response = relianet_pb2.PeerList()
            response.peers.extend(self.peers.values())
            print(f"[REGISTRY] Serving peer list to a node ({len(self.peers)} active nodes).", flush=True)
            return response

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    relianet_pb2_grpc.add_RegistryServicer_to_server(RegistryServicer(), server)
    
    # Port 50051 is our central discovery port
    server.add_insecure_port('[::]:50051')
    print("[REGISTRY] Server alive and listening on port 50051...", flush=True)
    server.start()
    server.wait_for_termination()

if __name__ == '__main__':
    serve()