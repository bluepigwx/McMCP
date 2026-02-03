import threading
import queue
import worktask
import select
import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class ClientSession:
    def __init__(self, name):
        self.buffer = []
        self.name = name


class WorkThread(threading.Thread):
    def __init__(self, args = ...):
        super().__init__()
        
        self.task_queue = queue.Queue()
        self.task_id = worktask.WorkTask.WORK_TASK_ID_BEGIN
        self.running = True
        
        # 等待结果队列
        self.waiting_list = {}
        
        self.server_socket = args[0]
        self.client_sockets = []
        
        self.client_map = {}
        
    
    def remove_socket(self, socket):
        if socket in self.client_map:
            self.client_map.pop(socket, None)
            
        if socket in self.client_sockets:
            self.client_sockets.remove(socket)
            
        socket.close()
        
    
    def stop(self):
        """
        注意只能在workthread线程内调用
        """
        if threading.current_thread() != self:
            raise RuntimeError(f"invalid tread")
        
        self.running = False
        logger.info(f"work thread stopped")
        
    
    def submit(self, task, timeout=10, *args, **kwagrs)-> Dict[str, Any]:
        result_queue = queue.Queue()
        
        task = worktask.WorkTask(self.task_id, args, kwagrs)
        self.task_queue.put((task, result_queue))
        self.task_id += 1
        
        try:
            ret, result = result_queue.get(timeout)
            if ret == worktask.TaskRetCode.Success:
                return {"ret":"ok", "result":result}
            else:
                return {"ret":"invalid_response"}
        except queue.Empty:
            return {"ret":"timeout"}
        except Exception as e:
            logger.error(f"submit exception : {e}")
            return {"ret":"exception"}
            
        
    
    def run(self):
        while self.running:
            #首先处理任务队列
            while self.task_queue:
                task, result_queue = self.task_queue.get()
                
                ret_code = task.exec()
                if ret_code == worktask.TaskStage.Finish:
                    #任务已经完成则通知调用线程
                    result_queue.put((worktask.TaskRetCode.Success, task.get_result()))
                elif ret_code == worktask.TaskStage.Wating_Result:
                    #任务未完成继续等待网络收包
                    self.waiting_queue.put[task.task_id] = result_queue
                    
            #处理网络收包
            all_sockets = [self.server_socket] + self.client_sockets
            readable, _, excptional = select.select(all_sockets, [], [], None)
            
            for socket in readable:
                if self.server_socket == socket:
                    try:
                        new_socket, addr = self.server_socket.accept()
                        self.client_sockets.append(new_socket)
                        self.client_map[new_socket] = ClientSession(f"{addr[0]}:{addr[1]}")
                    except Exception as e:
                        pass
                else:
                    if socket not in self.client_map:
                        self.remove_socket(socket)
                        continue
                    
                    client = self.client_map[socket]
                    if not client:
                        self.remove_socket(socket)
                        continue
                    
                    data = socket.recve(8192)
                    if not data:
                        #客户端已经断开
                        self.remove_socket(socket)
                        continue
                        
                    client.buffer += data
                    try:
                        response = json.loads(client.buffer.decode("utf-8"))
                        if "task_id" in response:
                            task_id = response.get("task_id")
                            if task_id in self.waiting_queue:
                                result_queue = self.waiting_queue[task_id]
                                result_queue.put((worktask.TaskRetCode.Success, response)) # 通知挂起线程进行处理
                            else:
                                logger.error(f"invalid task_id : {task_id} in waiting_queue")
                                raise Exception(f"invalid task_id : {task_id} in waiting_queue")
                        else:
                            logger.error(f"invalid response : {response}")
                            raise Exception(f"invalid response : {response}")
                    except json.JSONDecodeError:
                        continue
                    except Exception as e:
                        logger.error(f"close socket by exception {socket}")
                        self.remove_socket(socket)
                        
            #清理异常socket
            for exc_socket in excptional:
                if exc_socket in self.client_map:
                    self.remove_socket(exc_socket)
                        