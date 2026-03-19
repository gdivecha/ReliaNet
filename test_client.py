import grpc
import sys
import os

# Import the stubs you already generated
import relianet_pb2
import relianet_pb2_grpc

def run():
    channel = grpc.insecure_channel('node1:50052')
    stub = relianet_pb2_grpc.PeerNodeStub(channel) # Match your Service name

    # Match your Message name
    news = relianet_pb2.DataPayload(
        key="local_news", 
        value="Massive traffic jam reported on the 410 in Brampton."
    )
    
    try:
        print("Submitting news to node1...")
        # Note: Your proto calls this Replicate or PutData? 
        # Looking at your proto screenshot, use Replicate or QuorumRead
        # If you didn't add PutData to the proto, use Replicate for this test
        response = stub.Replicate(news) 
        if response.success:
            print("✅ SUCCESS: Data accepted by node1!")
    except Exception as e:
        print(f"❌ FAILED: {e}")

if __name__ == '__main__':
    run()