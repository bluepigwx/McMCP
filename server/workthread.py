import threading
import queue
import worktask
import select
import json


class Client:
    def __init__(self):
        self.buffer = []


class WorkThread(threading.Thread):
    def __init__(self, group = None, target = None, name = None, args = ..., kwargs = None, *, daemon = None):
        super().__init__(group, target, name, args, kwargs, daemon=daemon)
        
        self.task_queue = queue.Queue()
        self.task_id = 1
        self.running = True
        
        # 等待结果队列
        self.waiting_list = {}
        
        self.server_socket = 0
        self.client_sockets = []
        
        self.client_map = {}
        
    
    def submit(self, task, timeout=10, *args, **kwagrs):
        result_queue = queue.Queue()
        
        task = worktask.WorkTask(self.task_id, args, kwagrs)
        self.task_queue.put((task, result_queue))
        self.task_id += 1
        
        ret, result = result_queue.get(timeout)
        if ret == task.TaskRetCode.Success:
            return result
        else:
            return "timeout"
        
    
    def run(self):
        while self.running:
            #首先处理任务队列
            while self.task_queue:
                task, result_queue = self.task_queue.get()
                
                ret_code = task.exec()
                if ret_code == worktask.TaskStage.Finish:
                    #任务已经完成则通知调用线程
                    result_queue.put(task.get_result())
                elif ret_code == worktask.TaskStage.Wating_Result:
                    #任务未完成继续等待网络收包
                    self.waiting_queue.put[task.task_id] = result_queue
                    
            #处理网络收包
            all_sockets = [self.server_socket] + self.client_sockets
            readable, _, excptional = select.select(all_sockets, [], [], None)
            
            for socket in readable:
                if self.server_socket == socket:
                    try:
                        new_socket = self.server_socket.accept()
                        self.client_sockets.append(new_socket)
                        self.client_map[new_socket] = Client()
                    except Exception as e:
                        pass
                else:
                    if socket not in self.client_map:
                        continue
                    
                    client = self.client_map[socket]
                    if not client:
                        self.client_map.pop(socket, None)
                    
                    data = socket.recve(8192)
                    if not data:
                        #客户端已经断开
                        self.client_map.pop(socket, None)
                        socket.close()
                        continue
                        
                    client.buffer += data
                    try:
                        response = json.loads(client.buffer.decode("utf-8"))
                    except Exception as e:
                        pass