from fastmcp import FastMCP
import sys
from typing import AsyncIterator, Dict, Any
from contextlib import asynccontextmanager
import threading
import socket
import json
import logging
import select
import queue
import workthread
import worktask

_host = "localhost"
_port = 9987


_work_thread = None


logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(name)s - [%(filename)s:%(funcName)s:%(lineno)d] - %(levelname)s - %(message)s",
                    handlers=[
                        logging.StreamHandler()
                    ])

logger = logging.getLogger("mcp-server")
logger.setLevel(logging.DEBUG)

    
    

def send_client_command(client_session, cmd_type:str, params:Dict[str, Any])->Dict[str, Any]:
    """
    往指定客户端发包
    """
    global _work_thread
    
    command = {
        "session":client_session,
        "cmd":cmd_type,
        "params":params
    }
    
    def exec_func(params):
        session_id = params.get("session")
        session = _work_thread.get_session(session_id)
        if not session:
            return worktask.TaskStage.Finish
        
        session.socket.sendall(json.dumps(command).encode("utf-8"))
        return worktask.TaskStage.Wating_Result
    
    
    result = _work_thread.submit(exec_func, command)
    if result["ret"] != "ok":
        return {"ret":"failed"}
    
    return {"ret":"success", "result":result["result"]}



@asynccontextmanager
async def server_lifespan(server: FastMCP) -> AsyncIterator[Dict[str, Any]]:
    """
    创建一个服务端链接，等待MC客户端链接进来
    """
    logger.info(f"enter server_lifespan")
    
    global _work_thread
    
    try:
        try:
            listen_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            listen_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listen_socket.bind((_host, _port))
            listen_socket.listen(1)
            listen_socket.setblocking(False)
            
            
            _work_thread = workthread.WorkThread(args=(listen_socket,))
            _work_thread.daemon = True
            _work_thread.start()
        except Exception as e:
            logger.error(f"star server_lifespan exception :{e}")
    
        yield {}
        
        def stop_func(param):
            _work_thread.stop()
            #立即返回，不进行异步等待
            return worktask.TaskStage.Finish
            
        _work_thread.submit(stop_func, {})
        
    finally:
        listen_socket.close()
    


mcp = FastMCP(
    "MCMCP",
    lifespan=server_lifespan
)


@mcp.prompt()
def get_prompt()->str:
    """
    返回每次操作前注入模型的上下文
    """
    
    return """这是一个基于OpenGL坐标系编写的类似《我的世界的》的小游戏：
    1.世界由大量的block小方块组成，每个block的长，宽，高占据1个OpenGL的长度单位，每个block有一个数字type代表他的类型
    2.世界中有一个相机来决定视口的内容，相机由标准的position,up,forward,right这几个向量来定义
    3.每种方块的类型id和名字对应关系如下：
        50: name "Torch", model models.torch, texture.top torch_top, texture.bottom torch, texture.sides torch
        79: name "Ice", model models.tinted_glass, texture.all ice
        53: name "Wooden Stairs", model models.stairs, texture.all planks
        60: name "Soil", model models.soil, texture.all dirt, texture.top soil
        78: name "Snow", model models.snow, texture.all sno
        44: name "Slab", model models.slab, texture.sides slab_side, texture.y slab_y
        68: name "Sign", model models.sign, texture.all planks
        63: name "Sign Post", model models.sign_post, texture.all planks
        70: name "Stone Pressure Plate", model models.pressure_plate, texture.all stone
        72: name "Wooden Pressure Plate", model models.pressure_plate, texture.all planks
        6:  name "Sapling", model models.plant, texture.all sapling
        37: name "Yellow Flower", model models.plant, texture.all yellow_flower
        38: name "Red Rose", model models.plant, texture.all red_rose
        39: name "Brown Mushroom", model models.plant, texture.all brown_mushroom
        40: name "Red Mushroom", model models.plant, texture.all red_mushroom
        8:  name "Water", model models.liquid, texture.all water
        10: name "Lava", model models.liquid, texture.all lava
        69: name "Lever", model models.lever, texture.all lever
        18: name "Leaves", model models.leaves, texture.all leaves
        65: name "Ladder", model models.ladder, texture.all ladder
        20: name "Glass", model models.glass, texture.all glass
        64: name "Wooden Door", model models.door, texture.all wooden_door
        71: name "Iron Door", model models.door, texture.all iron_door_bottom_half
        51: name "Fire", model models.fire, texture.all fire
        59: name "Crops", model models.crop, texture.all crops
        81: name "Cactus", model models.cactus, texture.top cactus_top, texture.bottom cactus_bottom, texture.sides cactus_side
        77: name "Stone Button", model models.button, texture.all stone
    """


@mcp.tool()
def hello(message : str)->str:
    """发送一条hello消息"""
    result = send_client_command(1, "hello", {})
    return json.dumps(result).encode("utf-8")



@mcp.tool()
def get_scene_info()->str:
    """
    "camera" : {},
    "blocks" : [],
    以json形式返回场景中的所有信息，包括摄相机position, forward, up
    场景中每个方块的类型和世界坐标位置等
    """
    result = send_client_command(1, "get_scene_info", {})
    logger.debug(f"sencen info : {result}")
    return json.dumps(result).encode("utf-8")



@mcp.tool()
def set_scene_blocks(blocks : list)->str:
    """
    设置场景中的方块
    参数:
        blocks: 方块的数组，格式为[{"type":int, "wx":float, "wy":float, "wz":float}, ...]
            其中type为block的数字类型，wx,wy,wz为方块的世界坐标
    """
    result = send_client_command(1, "set_blocks", {"blocks":blocks})
    logger.debug(f"set_blocks response : {result}")
    return json.dumps(result).encode("utf-8")
