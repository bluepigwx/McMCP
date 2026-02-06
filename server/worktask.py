import enum


class TaskStage(enum.Enum):
    Init = 0
    Wating_Result = 1
    Finish = 2
    

class TaskRetCode(enum.Enum):
    Success = 0
    Failed = 1
    Timeout = 2


class WorkTask:
    
    STOP_TASK_ID = 1
    WORK_TASK_ID_BEGIN = 100
    
    def __init__(self, task_id, func, command):
        self.command = command
        self.task_id = task_id
        self.func = func
        self.stage = TaskStage.Init
        
        self.result = None
        
    def exec(self):
        pass
    
    def get_result(self):
        return self.result
        