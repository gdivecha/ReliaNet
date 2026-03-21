import argparse
import time
import grpc
import os
import json
import threading
import hashlib
import pika
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

    def get_data_hash(self):
        """Generates a SHA-256 hash of the current database."""
        with self.lock:
            sorted_items = sorted(self.data_store.items())
            data_string = json.dumps(sorted_items)
            return hashlib.sha256(data_string.encode('utf-8')).hexdigest()

    def Replicate(self, request, context):
        with self.lock:
            if request.key in self.data_store and self.data_store[request.key] == request.value:
                return relianet_pb2.Ack(success=True)

            self.data_store[request.key] = request.value
            self.save_to_disk()
            
        print(f"[NODE-{self.node_id}] Saved locally. Propagating to network...", flush=True)

        registry_host = os.environ.get("REGISTRY_HOST", "registry")
        try:
            with grpc.insecure_channel(f"{registry_host}:50051") as channel:
                stub = relianet_pb2_grpc.RegistryStub(channel)
                response = stub.GetPeers(relianet_pb2.Empty())
                
                for peer in response.peers:
                    if peer.port == self.port:
                        continue
                    try:
                        with grpc.insecure_channel(f"{peer.ip}:{peer.port}") as p_channel:
                            p_stub = relianet_pb2_grpc.PeerNodeStub(p_channel)
                            p_stub.Replicate(request)
                            print(f"[NODE-{self.node_id}] Successfully replicated to {peer.ip}:{peer.port}", flush=True)
                    except Exception as e:
                        pass
        except Exception as e:
            pass

        return relianet_pb2.Ack(success=True)

    # --- DAY 5 FIX: The Catch-Up Push ---
    def push_all_data_to_peer(self, peer_host, peer_port):
        """Pushes all local data to an out-of-sync peer."""
        with self.lock:
            items_to_send = list(self.data_store.items())
            
        try:
            with grpc.insecure_channel(f"{peer_host}:{peer_port}") as channel:
                stub = relianet_pb2_grpc.PeerNodeStub(channel)
                for key, value in items_to_send:
                    request = relianet_pb2.DataPayload(key=key, value=value)
                    stub.Replicate(request)
            print(f"[NODE-{self.node_id}] Sent missing data to {peer_host}:{peer_port} to sync state.", flush=True)
        except Exception as e:
            print(f"[NODE-{self.node_id}] Failed to sync with {peer_host}: {e}", flush=True)


def register_with_registry(ip, port):
    registry_host = os.environ.get("REGISTRY_HOST", "registry")
    registered = False
    while not registered:
        try:
            channel = grpc.insecure_channel(f"{registry_host}:50051")
            stub = relianet_pb2_grpc.RegistryStub(channel)
            request = relianet_pb2.NodeInfo(ip=ip, port=port)
            stub.RegisterNode(request)
            print(f"[NODE-{ip}] Registered with Registry as {ip}:{port}", flush=True)
            registered = True
        except Exception as e:
            print(f"[NODE-{ip}] Registry not ready, retrying...", flush=True)
            time.sleep(2)


# --- DAY 5: RabbitMQ Publisher ---
def rabbitmq_heartbeat(node_id, servicer):
    rabbitmq_host = os.environ.get("RABBITMQ_HOST", "rabbitmq")
    time.sleep(8) 
    while True:
        try:
            connection = pika.BlockingConnection(pika.ConnectionParameters(host=rabbitmq_host))
            channel = connection.channel()
            channel.exchange_declare(exchange='node_heartbeats', exchange_type='fanout')
            
            while True:
                current_hash = servicer.get_data_hash()
                message = json.dumps({"node_id": node_id, "hash": current_hash})
                channel.basic_publish(exchange='node_heartbeats', routing_key='', body=message)
                print(f"[NODE-{node_id}] Heartbeat sent -> Hash: {current_hash[:6]}...", flush=True)
                time.sleep(10)
        except Exception:
            time.sleep(5)


# --- DAY 5: RabbitMQ Auditor (Listener) ---
def rabbitmq_auditor(node_id, servicer):
    rabbitmq_host = os.environ.get("RABBITMQ_HOST", "rabbitmq")
    time.sleep(12) 
    
    while True:
        try:
            connection = pika.BlockingConnection(pika.ConnectionParameters(host=rabbitmq_host))
            channel = connection.channel()
            channel.exchange_declare(exchange='node_heartbeats', exchange_type='fanout')
            
            result = channel.queue_declare(queue='', exclusive=True)
            queue_name = result.method.queue
            channel.queue_bind(exchange='node_heartbeats', queue=queue_name)
            
            def callback(ch, method, properties, body):
                message = json.loads(body)
                peer_id = message.get("node_id")
                peer_hash = message.get("hash")
                
                if peer_id == str(node_id):
                    return
                    
                my_hash = servicer.get_data_hash()
                
                # If hashes mismatch, we found the gap! Send them our data.
                if peer_hash != my_hash:
                    print(f"⚠️ [NODE-{node_id} AUDIT] Mismatch with Node {peer_id}! Theirs: {peer_hash[:6]}, Mine: {my_hash[:6]}", flush=True)
                    
                    # Calculate the peer's port based on your setup (Node 1=50052, Node 2=50053, etc.)
                    peer_host = f"node{peer_id}"
                    peer_port = 50051 + int(peer_id)
                    servicer.push_all_data_to_peer(peer_host, peer_port)

            channel.basic_consume(queue=queue_name, on_message_callback=callback, auto_ack=True)
            print(f"[NODE-{node_id}] Auditor is actively listening...", flush=True)
            channel.start_consuming()
            
        except Exception:
            time.sleep(5)


def serve(node_id, port):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    servicer = PeerNodeServicer(node_id, port)
    relianet_pb2_grpc.add_PeerNodeServicer_to_server(servicer, server)
    server.add_insecure_port(f'[::]:{port}')
    server.start()
    print(f"[NODE-{node_id}] gRPC Server listening on port {port}...", flush=True)
    
    # Start BOTH background threads
    threading.Thread(target=rabbitmq_heartbeat, args=(node_id, servicer), daemon=True).start()
    threading.Thread(target=rabbitmq_auditor, args=(node_id, servicer), daemon=True).start()
    
    server.wait_for_termination()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--id', type=str, required=True)
    parser.add_argument('--port', type=int, required=True)
    args = parser.parse_args()

    container_ip = f"node{args.id}"
    threading.Thread(target=register_with_registry, args=(container_ip, args.port), daemon=True).start()
    
    serve(args.id, args.port)