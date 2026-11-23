import uvicorn

from app.monitoring.bootstrap import create_application


app = create_application()


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=False)
