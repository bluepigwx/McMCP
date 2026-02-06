import threading
import queue
import worktask
import select
import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class ClientSession:
    def __init__(self, socket, session_id):
        self.buffer = b''
        self.socket = socket
        self.session_id = session_id


class WorkThread(threading.Thread):
    def __init__(self, args = ...):
        super().__init__()
        
        self.task_queue = queue.Queue()
        self.task_id = worktask.WorkTask.WORK_TASK_ID_BEGIN
        self.running = True
        
        # 等待结果队列
        self.waiting_queue = {}
        
        self.server_socket = args[0]
        
        self.client_sockets = []
        self.client_map = {} # socket -> session
        self.client_session_map = {} # session_id -> session
        
        self.session_id_begin = 1
        
    
    def remove_socket(self, socket):
        session = None
        if socket in self.client_map:
            session = self.client_map[socket]
            self.client_map.pop(socket, None)
            
        if socket in self.client_sockets:
            self.client_sockets.remove(socket)
            
        if session:
            self.client_session_map.pop(session.session_id, None)
            
        socket.close()
        
    
    def insert_socket(self, socket):
        if socket in self.client_map:
            logger.error(f"client_map duplicated socket {socket}")
            return
        
        if socket in self.client_sockets:
            logger.error(f"client_sockets duplicated socket {socket}")
            return
        
        self.client_sockets.append(socket)
        new_session = ClientSession(socket, self.session_id_begin)
        self.client_map[socket] = new_session
        self.client_session_map[self.session_id_begin] = new_session
        self.session_id_begin += 1
        
        
    def get_session(self, session_id):
        """
        注意只能在workthread线程内调用
        """
        if threading.current_thread() != self:
            raise RuntimeError(f"invalid thread")
        
        if session_id not in self.client_session_map:
            return None
        
        return self.client_session_map[session_id]
    
    
    def stop(self):
        """
        注意只能在workthread线程内调用
        """
        if threading.current_thread() != self:
            raise RuntimeError(f"invalid thread")
        
        self.running = False
        logger.info(f"work thread stopped")
        
    
    def submit(self, func, command, timeout=10)-> Dict[str, Any]:
        result_queue = queue.Queue()
        
        task = worktask.WorkTask(self.task_id, func, command)
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
            while not self.task_queue.empty():
                task, result_queue = self.task_queue.get()
                
                ret_code = task.func(task.command)
                if ret_code == worktask.TaskStage.Finish:
                    #任务已经完成则通知调用线程
                    result_queue.put((worktask.TaskRetCode.Success, {}))
                elif ret_code == worktask.TaskStage.Wating_Result:
                    #任务未完成继续等待网络收包
                    self.waiting_queue[task.task_id] = result_queue
                    
            #处理网络收包
            all_sockets = [self.server_socket] + self.client_sockets
            readable, _, excptional = select.select(all_sockets, [], [], 0.1)
            
            for socket in readable:
                if self.server_socket == socket:
                    try:
                        new_socket, addr = self.server_socket.accept()
                        self.insert_socket(new_socket)
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
                    
                    data = socket.recv(8192)
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
                                client.buffer = b'' #收满了清理当前buffer
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
                        