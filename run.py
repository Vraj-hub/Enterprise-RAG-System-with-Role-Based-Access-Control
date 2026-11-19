"""Start the server without needing uvicorn.exe (useful when Windows blocks .exe launchers).

Run:  python run.py
Host/port come from APP_HOST / APP_PORT in .env (default 127.0.0.1:8080).
"""
import uvicorn

from app import config

if __name__ == "__main__":
    uvicorn.run("app.main:app", host=config.APP_HOST, port=config.APP_PORT, reload=True)
