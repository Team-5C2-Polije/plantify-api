class ResponseUtil:
    @staticmethod
    def success(message, data=None):
        return {
            "status": "success",
            "message": message,
            "data": data
        }, 200

    @staticmethod
    def error(message, data=None, status_code=400):
        return {
            "status": "error",
            "message": message,
            "data": data
        }, status_code
