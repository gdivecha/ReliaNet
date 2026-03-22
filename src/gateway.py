from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import grpc

import relianet_pb2
import relianet_pb2_grpc

app = FastAPI(title="ReliaNet Distributed Database API", description="ReliaNet API Gateway")

# Define the expected JSON format for incoming POST requests
class NewsUpdate(BaseModel):
    value: str

def get_stub():
    """Helper to connect to the internal gRPC cluster via Node 1."""
    # In a massive production system, you would use a load balancer here.
    channel = grpc.insecure_channel('node1:50052')
    return relianet_pb2_grpc.PeerNodeStub(channel)

@app.post("/api/news", status_code=201)
def write_news(update: NewsUpdate):
    """Writes data to the distributed cluster using Replication."""
    try:
        stub = get_stub()
        # We hardcode 'local_news' as the key for the demo
        payload = relianet_pb2.DataPayload(key="local_news", value=update.value)
        response = stub.Replicate(payload)
        
        if response.success:
            return {"status": "success", "message": "Data replicated across the cluster."}
        raise HTTPException(status_code=500, detail="Cluster rejected the write.")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cluster communication failed: {str(e)}")

@app.get("/api/news")
def read_news():
    """Reads data from the cluster using Quorum Consensus."""
    try:
        stub = get_stub()
        req = relianet_pb2.ReadRequest(key="local_news")
        response = stub.QuorumRead(req)
        
        if response.found:
            return {
                "status": "success", 
                "consensus_value": response.value
            }
        else:
            raise HTTPException(status_code=404, detail="Key 'local_news' not found in cluster.")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cluster communication failed: {str(e)}")