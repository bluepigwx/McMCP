import enum


class TaskStage(enum.Enum):
    Wating_Result = 1
    Finish = 2
    

class TaskRetCode(enum.Enum):
    Success = 0
    Failed = 1


class WorkTask:
    def __init__(self, task_id, func, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.task_id = task_id
        self.func = func
        self.stage = TaskStage.Init
        
        self.result = None
        
    def exec(self):
        pass
    
    def get_result(self):
        return self.result
        