from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import grpc

import relianet_pb2
import relianet_pb2_grpc

app = FastAPI(title="ReliaNet Distributed Database API", description="ReliaNet API Gateway")

# --- UPDATED: Accepts any key and value ---
class DataEntry(BaseModel):
    key: str
    value: str

def get_stub():
    channel = grpc.insecure_channel('node1:50052')
    return relianet_pb2_grpc.PeerNodeStub(channel)

@app.post("/api/data", status_code=201)
def write_data(entry: DataEntry):
    """Writes any key-value pair to the cluster."""
    try:
        stub = get_stub()
        # Use the key provided by the user instead of hardcoding 'local_news'
        payload = relianet_pb2.DataPayload(key=entry.key, value=entry.value)
        response = stub.Replicate(payload)
        
        if response.success:
            return {"status": "success", "message": f"Key '{entry.key}' replicated."}
        raise HTTPException(status_code=500, detail="Cluster rejected the write.")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cluster communication failed: {str(e)}")

@app.get("/api/data/{key}")
def read_data(key: str):
    """Reads a specific key from the cluster using Quorum Consensus."""
    try:
        stub = get_stub()
        # Use the key from the URL path
        req = relianet_pb2.ReadRequest(key=key)
        response = stub.QuorumRead(req)
        
        if response.found:
            return {
                "status": "success", 
                "key": key,
                "consensus_value": response.value
            }
        else:
            raise HTTPException(status_code=404, detail=f"Key '{key}' not found in cluster.")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cluster communication failed: {str(e)}")