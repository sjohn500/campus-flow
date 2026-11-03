import asyncio
import os
import pty
import sys
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

app = FastAPI(title="CampusFlow Web Terminal")
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse(request, "index.html")

@app.websocket("/ws/terminal")
async def terminal_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    # Spawn a pseudo-terminal running sys.executable -u tickets.py (unbuffered)
    pid, fd = pty.fork()
    if pid == 0:
        # Child process: set terminal environment and run tickets.py unbuffered using venv python
        os.environ["TERM"] = "xterm-256color"
        os.execlp(sys.executable, sys.executable, "-u", "tickets.py")
    else:
        loop = asyncio.get_running_loop()

        # Background thread reader for PTY output
        async def pty_to_websocket():
            try:
                while True:
                    output = await loop.run_in_executor(None, os.read, fd, 4096)
                    if not output:
                        break
                    await websocket.send_text(output.decode("utf-8", errors="ignore"))
            except Exception as e:
                print(f"[PTY Read Error]: {e}")

        # Background writer for WebSocket keystrokes
        async def websocket_to_pty():
            try:
                while True:
                    data = await websocket.receive_text()
                    if data:
                        await loop.run_in_executor(None, os.write, fd, data.encode("utf-8"))
            except WebSocketDisconnect:
                print("[WebSocket] Client disconnected normally.")
            except Exception as e:
                print(f"[WebSocket Write Error]: {e}")

        # Run both directions concurrently
        task1 = asyncio.create_task(pty_to_websocket())
        task2 = asyncio.create_task(websocket_to_pty())

        await asyncio.wait(
            [task1, task2],
            return_when=asyncio.FIRST_COMPLETED
        )

        # Cleanup tasks and process
        task1.cancel()
        task2.cancel()
        try:
            os.kill(pid, 9)
        except ProcessLookupError:
            pass