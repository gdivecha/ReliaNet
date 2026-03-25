import argparse
import time
import grpc
import os
import json
import threading
import hashlib
import pika
from concurrent import futures
from collections import Counter

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
                pass

    def save_to_disk(self):
        with open(self.db_file, "w") as f:
            json.dump(self.data_store, f, indent=4)

    def get_data_hash(self):
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
            
        print(f"[NODE-{self.node_id}] Saved locally. Propagating...", flush=True)

        registry_host = os.environ.get("REGISTRY_HOST", "registry")
        try:
            with grpc.insecure_channel(f"{registry_host}:50051") as channel:
                stub = relianet_pb2_grpc.RegistryStub(channel)
                response = stub.GetPeers(relianet_pb2.Empty())
                
                for peer in response.peers:
                    if peer.port == self.port: continue
                    try:
                        with grpc.insecure_channel(f"{peer.ip}:{peer.port}") as p_channel:
                            p_stub = relianet_pb2_grpc.PeerNodeStub(p_channel)
                            p_stub.Replicate(request)
                    except Exception: pass
        except Exception: pass

        return relianet_pb2.Ack(success=True)

    def LocalRead(self, request, context):
        with self.lock:
            val = self.data_store.get(request.key, "")
            found = request.key in self.data_store
            return relianet_pb2.ReadResponse(value=val, found=found)

    # --- ELASTIC QUORUM READ ---
    def QuorumRead(self, request, context):
        key = request.key
        collected_values = []
        
        with self.lock:
            if key in self.data_store:
                collected_values.append(self.data_store[key])
                
        registry_host = os.environ.get("REGISTRY_HOST", "registry")
        total_cluster_size = 1 
        
        # 1. Ask Registry exactly how many nodes exist right now
        try:
            with grpc.insecure_channel(f"{registry_host}:50051") as channel:
                stub = relianet_pb2_grpc.RegistryStub(channel)
                response = stub.GetPeers(relianet_pb2.Empty())
                total_cluster_size = len(response.peers)
                
                for peer in response.peers:
                    if peer.port == self.port: continue
                    try:
                        with grpc.insecure_channel(f"{peer.ip}:{peer.port}") as p_channel:
                            p_stub = relianet_pb2_grpc.PeerNodeStub(p_channel)
                            read_resp = p_stub.LocalRead(request)
                            if read_resp.found:
                                collected_values.append(read_resp.value)
                    except Exception: pass
        except Exception: pass

        # 2. Dynamic Math: (Total // 2) + 1
        threshold = (total_cluster_size // 2) + 1
        print(f"⚖️ [QUORUM] Cluster Size: {total_cluster_size} | Required Votes: {threshold}", flush=True)

        if not collected_values:
            return relianet_pb2.ReadResponse(value="", found=False)
            
        vote_counts = Counter(collected_values)
        winning_value, votes = vote_counts.most_common(1)[0]
        
        if votes >= threshold:
            print(f"✅ [NODE-{self.node_id}] Quorum Reached: '{winning_value}' ({votes}/{total_cluster_size} votes).", flush=True)
            return relianet_pb2.ReadResponse(value=winning_value, found=True)
        else:
            print(f"❌ [NODE-{self.node_id}] NO QUORUM: Highest vote was {votes}/{total_cluster_size}.", flush=True)
            return relianet_pb2.ReadResponse(value="", found=False)

    def push_all_data_to_peer(self, peer_host, peer_port):
        with self.lock:
            items_to_send = list(self.data_store.items())
        try:
            with grpc.insecure_channel(f"{peer_host}:{peer_port}") as channel:
                stub = relianet_pb2_grpc.PeerNodeStub(channel)
                for key, value in items_to_send:
                    # Reuse WriteRequest/DataPayload based on your proto setup
                    stub.Replicate(relianet_pb2.DataPayload(key=key, value=value) if hasattr(relianet_pb2, 'DataPayload') else relianet_pb2.WriteRequest(key=key, value=value))
            print(f"🛠️ [NODE-{self.node_id}] Synced missing data to {peer_host}:{peer_port}", flush=True)
        except Exception: pass


def register_with_registry(ip, port):
    registry_host = os.environ.get("REGISTRY_HOST", "registry")
    while True:
        try:
            with grpc.insecure_channel(f"{registry_host}:50051") as channel:
                stub = relianet_pb2_grpc.RegistryStub(channel)
                stub.RegisterNode(relianet_pb2.NodeInfo(ip=ip, port=port))
                print(f"✅ [NODE-{ip}] Registered as {ip}:{port}", flush=True)
                break
        except Exception: time.sleep(2)


# --- ELASTIC RABBITMQ LOGIC ---
def rabbitmq_heartbeat(node_id, servicer):
    rabbitmq_host = os.environ.get("RABBITMQ_HOST", "rabbitmq")
    time.sleep(8) 
    while True:
        try:
            connection = pika.BlockingConnection(pika.ConnectionParameters(host=rabbitmq_host))
            channel = connection.channel()
            channel.exchange_declare(exchange='node_heartbeats', exchange_type='fanout')
            while True:
                # Include the exact port in the heartbeat so peers don't guess!
                message = json.dumps({"node_id": node_id, "hash": servicer.get_data_hash(), "port": servicer.port})
                channel.basic_publish(exchange='node_heartbeats', routing_key='', body=message)
                time.sleep(10)
        except Exception: time.sleep(5)

def rabbitmq_auditor(node_id, servicer):
    rabbitmq_host = os.environ.get("RABBITMQ_HOST", "rabbitmq")
    time.sleep(12) 
    while True:
        try:
            connection = pika.BlockingConnection(pika.ConnectionParameters(host=rabbitmq_host))
            channel = connection.channel()
            channel.exchange_declare(exchange='node_heartbeats', exchange_type='fanout')
            result = channel.queue_declare(queue='', exclusive=True)
            channel.queue_bind(exchange='node_heartbeats', queue=result.method.queue)
            
            def callback(ch, method, properties, body):
                message = json.loads(body)
                peer_id = message.get("node_id")
                peer_port = message.get("port")
                
                if str(peer_id) == str(node_id): return
                    
                if message.get("hash") != servicer.get_data_hash():
                    print(f"⚠️ [NODE-{node_id} AUDIT] Mismatch with Node {peer_id}! Healing...", flush=True)
                    servicer.push_all_data_to_peer(f"node{peer_id}", peer_port)

            channel.basic_consume(queue=result.method.queue, on_message_callback=callback, auto_ack=True)
            channel.start_consuming()
        except Exception: time.sleep(5)

def serve(node_id, port):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    servicer = PeerNodeServicer(node_id, port)
    relianet_pb2_grpc.add_PeerNodeServicer_to_server(servicer, server)
    server.add_insecure_port(f'[::]:{port}')
    server.start()
    
    threading.Thread(target=rabbitmq_heartbeat, args=(node_id, servicer), daemon=True).start()
    threading.Thread(target=rabbitmq_auditor, args=(node_id, servicer), daemon=True).start()
    server.wait_for_termination()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--id', type=str, required=True)
    parser.add_argument('--port', type=int, required=True)
    args = parser.parse_args()
    threading.Thread(target=register_with_registry, args=(f"node{args.id}", args.port), daemon=True).start()
    serve(args.id, args.port)