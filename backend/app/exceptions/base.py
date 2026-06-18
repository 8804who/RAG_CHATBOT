class BaseAppException(Exception):
    status_code: int
    response_message: str

    def __init__(self, message: str, code_path: str):
        self.message = message
        self.code_path = code_path
        super().__init__(message)