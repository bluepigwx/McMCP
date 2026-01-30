from fastmcp import FastMCP
import sys
from typing import AsyncIterator, Dict, Any
from contextlib import asynccontextmanager
import threading
import socket
import json

_host = "localhost"
_port = 9987

_mc_client = None
_lock = threading.Lock()


def get_client(check=False):
    with _lock:
        if check == True:
            if not _mc_client:
                raise Exception(f"None Client")
            
        return _mc_client
    
    
def init_client(client_socket):
    with _lock:
        if get_client() != None:
            return
        
        global _mc_client
        _mc_client = MCClient(client_socket)



class MCClient:
    def __init__(self, client_socket):
        self.client_socket = client_socket
        
        
    def send_command(self, cmd_type : str, params : Dict[str, Any] = None) -> Dict[str, Any]:
        print(f"enter send_command : command {cmd_type} params {params}")
        
        command = {
            "type":cmd_type,
            "params":params
        }
        
        print(f"send cmd")
        self.client_socket.sendall(json.dump(command).encode("utf-8"))
        print(f"waiting for respone")
        
        self.client_socket.settimeout(50)



def _handle_client_accept(client):
    """
    处理客户端链接
    """
    client.settimeout(None)
    
    running = True
    while running:
        print(f"waiting for accept")
        new_socket, addr = client.accept()
        if get_client() != None:
            continue
        
        print(f"new socket with addr {addr}")
        #创建客户端链接对象，用于发送指令
        init_client(new_socket)
        


@asynccontextmanager
async def server_lifespan(server: FastMCP) -> AsyncIterator[Dict[str, Any]]:
    """
    创建一个服务端链接，等待MC客户端链接进来
    """
    print(f"enter server_lifespan")
    try:
        try:
            listen_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            listen_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listen_socket.bind((_host, _port))
            listen_socket.listen(1)
        
            listen_thread = threading.Thread(target=_handle_client_accept, args=(listen_socket,))
            listen_thread.daemon = True
            listen_thread.start()
        except Exception as e:
            pass
    
        yield {}
        
    finally:
        listen_socket.close()
    


mcp = FastMCP(
    "MCMCP",
    lifespan=server_lifespan
)


@mcp.tool()
def test(message : str)->str:
    cl = get_client(True)
    cl.send_command("test")
