import grpc
from concurrent import futures
import threading
import time
import socket

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
                print(f"[REGISTRY] Node joined: {request.ip}:{request.port}", flush=True)
            
            response = relianet_pb2.PeerList()
            response.peers.extend(self.peers.values())
            
        return response

    def GetPeers(self, request, context):
        """Returns all currently active peers."""
        with self.lock:
            response = relianet_pb2.PeerList()
            response.peers.extend(self.peers.values())
            return response

    def health_check_loop(self):
        """Actively pings nodes via TCP. Evicts unresponsive nodes."""
        while True:
            time.sleep(10) # Sweep the cluster every 10 seconds
            dead_nodes = []
            
            with self.lock:
                for peer_key, peer_info in self.peers.items():
                    try:
                        # 2-second TCP ping to verify container connectivity
                        with socket.create_connection((peer_info.ip, peer_info.port), timeout=2):
                            pass 
                    except Exception:
                        dead_nodes.append(peer_key)
                
                # Evict the dead nodes so the cluster can shrink dynamically
                for dead in dead_nodes:
                    del self.peers[dead]
                    print(f"[REGISTRY] Node {dead} unresponsive. Evicted. Active cluster size: {len(self.peers)}", flush=True)

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    servicer = RegistryServicer()
    relianet_pb2_grpc.add_RegistryServicer_to_server(servicer, server)
    
    # Port 50051 is our central discovery port
    server.add_insecure_port('[::]:50051')
    print("[REGISTRY] Server listening on port 50051. Auto-eviction enabled.", flush=True)
    
    # Start the health check daemon in the background
    threading.Thread(target=servicer.health_check_loop, daemon=True).start()
    
    server.start()
    server.wait_for_termination()

if __name__ == '__main__':
    serve()