import asyncio
import os
import pty
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

app = FastAPI(title="CampusFlow Web Terminal")
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.websocket("/ws/terminal")
async def terminal_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    # Spawn a pseudo-terminal running python3 -u tickets.py (unbuffered)
    pid, fd = pty.fork()
    if pid == 0:
        # Child process: set terminal environment and run tickets.py unbuffered
        os.environ["TERM"] = "xterm-256color"
        os.execlp("python3", "python3", "-u", "tickets.py")
    else:
        loop = asyncio.get_running_loop()

        # Background thread reader for PTY output
        async def pty_to_websocket():
            try:
                while True:
                    # run_in_executor safely runs blocking os.read in a background thread
                    output = await loop.run_in_executor(None, os.read, fd, 4096)
                    if not output:
                        break
                    await websocket.send_text(output.decode("utf-8", errors="ignore"))
            except Exception:
                pass

        # Background writer for WebSocket keystrokes
        async def websocket_to_pty():
            try:
                while True:
                    data = await websocket.receive_text()
                    await loop.run_in_executor(None, os.write, fd, data.encode("utf-8"))
            except WebSocketDisconnect:
                pass
            except Exception:
                pass

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