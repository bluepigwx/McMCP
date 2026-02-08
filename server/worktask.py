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
    
    #内部专用taskid
    STOP_TASK_ID = 1
    #外部自增taskid
    WORK_TASK_ID_BEGIN = 100
    
    def __init__(self, task_id, func, context):
        self.context = context
        self.task_id = task_id
        self.func = func
        self.stage = TaskStage.Init
        
        self.context.result = {}
        
    def exec(self):
        return self.func(self.context)
    
    def get_result(self):
        return self.context.result
        