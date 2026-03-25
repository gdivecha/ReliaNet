from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import grpc

import relianet_pb2
import relianet_pb2_grpc

app = FastAPI(title="ReliaNet Distributed Database API", description="ReliaNet API Gateway")

class DataEntry(BaseModel):
    key: str
    value: str

def get_stub():
    # Connecting to node1 as the entry point
    channel = grpc.insecure_channel('node1:50052')
    return relianet_pb2_grpc.PeerNodeStub(channel)

@app.post("/api/data", status_code=201)
def write_data(entry: DataEntry):
    """Writes any key-value pair to the cluster."""
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
    """Reads a specific key from the cluster using Quorum Consensus."""
    try:
        stub = get_stub()
        req = relianet_pb2.ReadRequest(key=key)
        response = stub.QuorumRead(req)
        
        # --- THE FIX ---
        # If the gRPC call succeeded but the data isn't there, return 404
        if not response.found:
            raise HTTPException(
                status_code=404, 
                detail=f"Key '{key}' not found. It hasn't been created yet."
            )
            
        return {
            "status": "success", 
            "key": key,
            "consensus_value": response.value
        }
            
    except grpc.RpcError as e:
        # Actual cluster crash / Network timeout
        raise HTTPException(status_code=503, detail=f"Cluster unavailable: {e.details()}")
    except HTTPException as he:
        # Re-raise our 404
        raise he
    except Exception as e:
        # Generic fallback
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")