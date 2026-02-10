import threading
import queue
from . import worktask
import select
import json
import logging
from typing import Dict, Any
import time

logger = logging.getLogger(__name__)


class ClientSession:
    CLIENT_SESSSION_ID = 1
    
    def __init__(self, socket):
        self.buffer = b''
        self.socket = socket
        self.session_id = ClientSession.CLIENT_SESSSION_ID
        ClientSession.CLIENT_SESSSION_ID += 1


class WorkThread(threading.Thread):
    
    MAX_WATE_QUEUE_TIME = 10
    
    def __init__(self, server_socket):
        super().__init__()
        
        self.task_queue = queue.Queue()
        self.task_id = worktask.WorkTask.WORK_TASK_ID_BEGIN
        self.running = True
        
        # 等待结果队列
        self.waiting_queue = {}
        
        self.server_socket = server_socket
        
        self.client_sockets = []
        self.client_map = {} # socket -> session
        self.client_session_map = {} # session_id -> session
        
    
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
        
        session_id = session.session_id if session else -1
        logger.info(f"close socket {socket} session {session_id}")
        
    
    def insert_socket(self, socket):
        if socket in self.client_map:
            logger.error(f"client_map duplicated socket {socket}")
            return
        
        if socket in self.client_sockets:
            logger.error(f"client_sockets duplicated socket {socket}")
            return
        
        self.client_sockets.append(socket)
        new_session = ClientSession(socket)
        self.client_map[socket] = new_session
        self.client_session_map[new_session.session_id] = new_session
        
        logger.info(f"new socket {socket} session {new_session.session_id}")
        
        
    def get_session(self, session_id):
        """
        注意只能在workthread线程内调用
        """
        if threading.current_thread() != self:
            raise RuntimeError(f"invalid thread")
        
        if session_id not in self.client_session_map:
            return None
        
        return self.client_session_map[session_id]
    
    
    def get_one_session_id(self):
        """
        注意只能在workthread线程内调用
        """
        if threading.current_thread() != self:
            raise RuntimeError(f"invalid thread")
        
        for k,v in self.client_session_map.items():
            return k
        
        return 0
    
    
    def stop(self):
        """
        注意只能在workthread线程内调用
        """
        if threading.current_thread() != self:
            raise RuntimeError(f"invalid thread")
        
        self.running = False
        logger.info(f"work thread stopped")
        
    
    def submit(self, func, context, timeout=10)-> Dict[str, Any]:
        """
        返回值说明：
        {
            "ret":"[ok:执行成功， failed:执行失败, timeout:执行超时, exception:执行过程产生异常]"
            "result":执行结果的payload，以{}形式返回
        }
        """
        result_queue = queue.Queue()    #线程间同步数据用
        
        task = worktask.WorkTask(self.task_id, func, context)
        self.task_queue.put((task, result_queue))
        
        logger.debug(f"submit task taskid： {self.task_id} context: {context}")
        
        self.task_id += 1
        
        try:
            ret, result = result_queue.get(timeout)
            if ret == worktask.TaskRetCode.Success:
                return {"ret":"ok", "result":result}
            elif ret == worktask.TaskRetCode.Timeout:
                return {"ret":"timeout"}
            else:
                return {"ret":"failed"}
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
                
                ret_code = task.exec()
                if ret_code == worktask.TaskStage.Finish:
                    #任务已经完成则通知调用者线程
                    result_queue.put((worktask.TaskRetCode.Success, task.context["result"]))
                elif ret_code == worktask.TaskStage.Wating_Result:
                    #任务未完成继续等待网络收包
                    self.waiting_queue[task.task_id] = {
                        "time":time.time(),
                        "result_queue":result_queue
                    }
            
            #删除超时任务
            now = time.time()
            expired_tasks = [
                task_id for task_id, entry in self.waiting_queue.items()
                if now - entry["time"] >= self.MAX_WATE_QUEUE_TIME
            ]
            for task_id in expired_tasks:
                entry = self.waiting_queue.pop(task_id)
                entry["result_queue"].put((worktask.TaskRetCode.Timeout, {}))
                    
                    
            #处理网络收包
            all_sockets = [self.server_socket] + self.client_sockets
            readable, _, excptional = select.select(all_sockets, [], [], 0.1)
            
            for socket in readable:
                if self.server_socket == socket:
                    try:
                        new_socket, addr = self.server_socket.accept()
                        self.insert_socket(new_socket)
                    except Exception as e:
                        logger.error(f"accept exception : {e}")
                else:
                    if socket not in self.client_map:
                        self.remove_socket(socket)
                        continue
                    
                    client = self.client_map[socket]
                    if not client:
                        self.remove_socket(socket)
                        continue
                    
                    try:
                        data = socket.recv(8192)
                        if not data:
                            #客户端已经断开
                            self.remove_socket(socket)
                            continue
                        
                        client.buffer += data
                    except Exception as e:
                        logger.info(f"recv exception {e}")
                        self.remove_socket(socket)
                        
                    try:
                        response = json.loads(client.buffer.decode("utf-8"))
                        if "task_id" in response:
                            task_id = response.get("task_id")
                            if task_id in self.waiting_queue:
                                result_queue = self.waiting_queue[task_id]["result_queue"]
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
            
        
        #线程结束清理资源
        for cl_socket in self.client_sockets:
                self.remove_socket(cl_socket)
            
        self.server_socket.close()
                        