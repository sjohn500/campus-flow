from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import pty
import os
import select

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
        # Parent process: bridge WebSocket data with PTY file descriptor
        try:
            while True:
                # Check if there is data to read from the PTY process
                rlist, _, _ = select.select([fd], [], [], 0.05)
                if fd in rlist:
                    output = os.read(fd, 1024)
                    if not output:
                        break
                    try:
                        await websocket.send_text(output.decode("utf-8", errors="ignore"))
                    except Exception:
                        break # Exit loop cleanly if socket is closing/closed
                
                # Check if browser sent any keystrokes non-blocking
                try:
                    data = await websocket.receive_text()
                    os.write(fd, data.encode("utf-8"))
                except Exception:
                    pass
                    
        except WebSocketDisconnect:
            pass
        finally:
            try:
                os.kill(pid, 9)
            except ProcessLookupError:
                pass