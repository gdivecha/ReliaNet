from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import grpc
import random
import os

import relianet_pb2
import relianet_pb2_grpc

app = FastAPI(title="ReliaNet Distributed Database API", description="ReliaNet API Gateway")

class DataEntry(BaseModel):
    key: str
    value: str

# --- THE "A+" FIX: Load Balancing & High Availability ---
def get_stub():
    """
    Dynamically finds a healthy node by asking the Registry.
    Removes Node 1 as a Single Point of Failure.
    """
    registry_host = os.environ.get("REGISTRY_HOST", "registry")
    
    try:
        # 1. Ask the Registry for the current list of healthy peers
        with grpc.insecure_channel(f"{registry_host}:50051") as channel:
            registry_stub = relianet_pb2_grpc.RegistryStub(channel)
            # Short timeout so we don't hang if the registry is struggling
            response = registry_stub.GetPeers(relianet_pb2.Empty(), timeout=2.0)
            
            if not response.peers:
                raise Exception("Registry reported zero healthy nodes.")

            # 2. Pick a random node from the healthy list
            target_peer = random.choice(response.peers)
            target_address = f"{target_peer.ip}:{target_peer.port}"
            
            # 3. Connect to that specific healthy node
            channel = grpc.insecure_channel(target_address)
            return relianet_pb2_grpc.PeerNodeStub(channel)
            
    except Exception as e:
        # Fallback: If Registry is down, try Node 1 as a last resort
        print(f"⚠️ Gateway could not reach Registry. Falling back to Node 1: {e}")
        channel = grpc.insecure_channel('node1:50052')
        return relianet_pb2_grpc.PeerNodeStub(channel)

@app.post("/api/data", status_code=201)
def write_data(entry: DataEntry):
    try:
        stub = get_stub()
        payload = relianet_pb2.DataPayload(key=entry.key, value=entry.value)
        response = stub.Replicate(payload)
        
        if response.success:
            return {"status": "success", "message": f"Key '{entry.key}' replicated."}
        raise HTTPException(status_code=400, detail="Cluster rejected the write.")
        
    except grpc.RpcError as e:
        raise HTTPException(status_code=503, detail=f"Cluster connection failed: {e.details()}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/data/{key}")
def read_data(key: str):
    try:
        stub = get_stub()
        req = relianet_pb2.ReadRequest(key=key)
        response = stub.QuorumRead(req)
        
        if not response.found:
            raise HTTPException(status_code=404, detail=f"Key '{key}' not found.")
            
        return {"status": "success", "key": key, "consensus_value": response.value}
            
    except grpc.RpcError as e:
        raise HTTPException(status_code=503, detail=f"Cluster unavailable: {e.details()}")
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Error: {str(e)}")