from fastmcp import FastMCP
import sys
from typing import AsyncIterator, Dict, Any
from contextlib import asynccontextmanager
import threading
import socket
import json
import logging
import time
import select

_host = "localhost"
_port = 9987

_mc_client = None
_lock = threading.Lock()


logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                    handlers=[
                        logging.StreamHandler()
                    ])

logger = logging.getLogger("mcp-server")
logger.setLevel(logging.DEBUG)


def get_client(check=False):
    with _lock:
        if check == True:
            if not _mc_client:
                raise Exception(f"None Client")
            
        return _mc_client



class MCClient:
    def __init__(self, client_socket):
        self.client_socket = client_socket
        self.buffer = []
        
        
    def send_command(self, cmd_type : str, params : Dict[str, Any] = None) -> Dict[str, Any]:
        logger.info(f"enter send_command : command {cmd_type} params {params}")
        
        command = {
            "type":cmd_type,
            "params":params
        }
        
        logger.info(f"send cmd {cmd_type} params {params}")
        self.client_socket.sendall(json.dumps(command).encode("utf-8"))
        logger.info(f"waiting for respone")
        
        
    def receive(self, data):
        pass
        
        
    def close(self):
        if self.client_socket != None:
            self.client_socket.close()
            self.client_socket = None

            

def _handle_client_message(server_socket):
    global _mc_client
    
    logger.info(f"beging handle client message...")
    
    try:
        running = True
        client_sockets = []
        
        while running:
            all_sockets = [server_socket] + client_sockets
            readable, _, excptional = select.select(all_sockets, [], [], None)
            
            with _lock:
                for socket in readable:
                    if server_socket == socket:
                        try:
                            #接受客户端新连接
                            new_socket, addr = server_socket.accept()
                            if _mc_client != None:
                                logger.warn(f"old mc client is valid when new accept comming!")
                                _mc_client.close()
                                _mc_client = None
                            
                            logger.info(f"create new mc client with socket {addr}")
                            _mc_client = MCClient(new_socket)
                            client_sockets.append(new_socket)
                            logger.info(f"clients socket len is {len(client_sockets)}")
                        except Exception as ae:
                            logger.error(f"process accept socket exception {ae}")
                    else:
                        # 先判断异常情况
                        if not _mc_client:
                            logger.error(f"mc client not ready")
                            if socket in client_sockets:
                                client_sockets.remove(socket)
                            
                            socket.close()
                            
                        if _mc_client.client_socket != socket:
                            logger.error(f"mc socket != socket")
                            if socket in client_sockets:
                                client_sockets.remove(socket)
                                socket.close()
                                
                        # 正式收取数据
                        try:
                            data = socket.recv(4096)
                            if data:
                                _mc_client.receive(data)
                            else:
                                logger.info(f"mc client closed by peer")
                                _mc_client.close()
                                _mc_client = None
                                client_sockets.remove(socket)
                        except ConnectionResetError as cer:
                            logger.error(f"client {_mc_client.client_socket} close by exception")
                            _mc_client.close()
                            _mc_client = None
                            client_sockets.remove(socket)
                
                for exc_socket in excptional:
                    if exc_socket in client_sockets:
                        client_sockets.remove(exc_socket)
                        
                    if _mc_client.client_socket == exc_socket:
                        _mc_client.close()
                        _mc_client = None
                        logger.info(f"mc client with excaptional close")
                            
    except Exception as e:
        logger.error(f"handle client message exception {e}")
        logger.error(f"main socket thread exit!!!")



@asynccontextmanager
async def server_lifespan(server: FastMCP) -> AsyncIterator[Dict[str, Any]]:
    """
    创建一个服务端链接，等待MC客户端链接进来
    """
    logger.info(f"enter server_lifespan")
    try:
        try:
            listen_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            listen_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listen_socket.bind((_host, _port))
            listen_socket.listen(1)
            listen_socket.setblocking(False)
            
            server_thread = threading.Thread(target=_handle_client_message, args=(listen_socket,))
            server_thread.daemon = True
            server_thread.start()
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
def hello(message : str)->str:
    """发送一条hello消息"""
    cl = get_client(True)
    cl.send_command("hello", {"message": message})
    return f"Hello message sent: {message}"
