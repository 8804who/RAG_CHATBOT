class BaseAppException(Exception):
    def __init__(self, message: str, code_path: str, status_code: int = 400):
        self.message = message
        self.code_path = code_path
        self.status_code = status_code
        super().__init__(message)