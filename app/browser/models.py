from enum import Enum


class SessionState(str, Enum):
    '''
        会话状态 枚举类
    '''
    CREATED = "created"
    STARTING = "starting"
    READY = "ready"
    CLOSED = "closed"
    ERROR = "error"