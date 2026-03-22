import grpc
import sys

import relianet_pb2
import relianet_pb2_grpc

def write_data(stub, key, value):
    """Sends a write request to the cluster."""
    news = relianet_pb2.DataPayload(key=key, value=value)
    try:
        response = stub.Replicate(news)
        if response.success:
            print(f"✅ WRITE SUCCESS: Data accepted for key '{key}'")
    except Exception as e:
        print(f"❌ WRITE FAILED: {e}")

def read_data(stub, key):
    """Sends a QuorumRead request to the cluster."""
    request = relianet_pb2.ReadRequest(key=key)
    try:
        response = stub.QuorumRead(request)
        if response.found:
            print(f"✅ QUORUM READ SUCCESS: {key} = '{response.value}'")
        else:
            print(f"⚠️ QUORUM READ: Key '{key}' not found in the cluster.")
    except Exception as e:
        print(f"❌ READ FAILED: {e}")

def run():
    # Connect to Node 1
    channel = grpc.insecure_channel('node1:50052')
    stub = relianet_pb2_grpc.PeerNodeStub(channel)
    
    # Check if the user passed the "read" argument
    if len(sys.argv) > 1 and sys.argv[1] == "read":
        print("Initiating Quorum Read...")
        read_data(stub, "local_news")
    else:
        print("Initiating Network Write...")
        # Keeping the 410 traffic theme for the write test
        write_data(stub, "local_news", "Major delays on the 410 North at Steeles Ave.")

if __name__ == '__main__':
    run()