Here is the complete Markdown file for your `README.md`. You can copy this entire block and paste it directly into your project's `README.md` file!

```markdown
# CampusFlow IT Support CLI 🚀

**CampusFlow** is a high-resilience, terminal-based IT support ticketing and diagnostics assistant designed for campus environments. It features an interactive CLI interface with an automated multi-tier AI analysis engine, atomic file storage, and seamless web-based PTY deployment via WebSockets.

---

## 🏗️ System Architecture & Multi-Tier AI Cascade

To guarantee **zero downtime** and robust reliability, CampusFlow uses a cascading fallback architecture for analyzing support tickets:


```

[ User Ticket Input ]
│
▼
┌─────────────────────────────────┐
│ Tier 1: Google Gemini (Primary) │ ──(Success)──► [ Return Analysis ]
└────────────────┬────────────────┘
│ (Fails / 429 / 5xx / Timeout)
▼
┌─────────────────────────────────┐
│ Tier 2: OpenRouter (Secondary)  │ ──(Success)──► [ Return Analysis ]
└────────────────┬────────────────┘
│ (Fails / Missing Key)
▼
┌─────────────────────────────────┐
│ Tier 3: Heuristic Local Engine  │ ─────────────► [ Return Analysis ]
└─────────────────────────────────┘

```

*   **Tier 1 (Google Gemini):** Configurable model (`gemini-3.8-flash` by default) with automatic exponential backoff retries on rate limits (`429`) and server errors (`5xx`).
*   **Tier 2 (OpenRouter):** Secondary cloud model fallback for redundancy.
*   **Tier 3 (Heuristic Local Engine):** Fully offline keyword-matching rules engine that instantly categorizes common network, authentication, and hardware issues if cloud providers time out or lack API keys.

---

## ✨ Key Features

*   **Robust PTY & TTY Safety:** Hardened terminal input handlers designed specifically to prevent stream locking in web-based Xterm.js/WebSocket environments.
*   **Atomic & Locked Storage:** Thread-safe `tickets.json` storage utilizing file locks (`fcntl`) and atomic temporary file swaps to prevent corruption. Corruption-tolerant auto-quarantine isolates unreadable data safely.
*   **Strict JSON Validation:** AI responses are strictly parsed, sanitized, and validated against allowed categories, urgency levels (`Low`, `Medium`, `High`), and troubleshooting steps.
*   **Control Character Sanitization:** Strips out terminal escape injections and control characters from both user input and model outputs before rendering.

---

## 🛠️ Installation & Local Development

### Prerequisites
*   Python 3.8+
*   `requests` library

### Setup Steps
1. Clone the repository and navigate into the project directory:
   ```bash
   git clone [https://github.com/your-username/campus-flow.git](https://github.com/your-username/campus-flow.git)
   cd campus-flow

```

2. Install dependencies:
```bash
pip install requests uvicorn fastapi

```


3. (Optional) Create a `.env` file in the root directory for your API keys:
```env
GEMINI_API_KEY=your_gemini_api_key_here
OPENROUTER_API_KEY=your_openrouter_api_key_here

```


4. Run the application locally:
```bash
python tickets.py

```


*Or launch the web terminal server:*
```bash
uvicorn main:app --reload

```



---

## ⚙️ Environment Variables

| Variable | Description | Default |
| --- | --- | --- |
| `GEMINI_API_KEY` or `GOOGLE_API_KEY` | Primary API key for Google Gemini | *None* |
| `OPENROUTER_API_KEY` | Secondary API key for OpenRouter | *None* |
| `GEMINI_MODEL` | Gemini model identifier | `gemini-3.8-flash` |
| `OPENROUTER_MODEL` | OpenRouter model identifier | `openrouter/free` |
| `AI_READ_TIMEOUT` | Timeout in seconds for AI provider requests | `20` |
| `TICKETS_FILE` | Filename path for ticket persistence | `tickets.json` |

---

## ☁️ Deployment on Render

CampusFlow includes a web wrapper (`main:app`) that exposes an interactive Xterm.js terminal over WebSockets.

1. Create a new **Web Service** on [Render](https://dashboard.render.com/).
2. Connect your GitHub repository.
3. Set the **Build Command**:
```bash
pip install -r requirements.txt

```


4. Set the **Start Command**:
```bash
uvicorn main:app --host 0.0.0.0 --port $PORT

```


5. Navigate to the **Environment** tab on Render and add your API keys (`GEMINI_API_KEY` and/or `OPENROUTER_API_KEY`).
6. Click **Deploy Changes**!

```

<ElicitationsGroup message="If you need help saving or staging the file:">
  <Elicitation label="How to create README.md" query="How do I create and save the README.md file in my local repository?"/>
  <Elicitation label="How to push to GitHub" query="What are the git commands to commit and push my new README file?"/>
</ElicitationsGroup>

<FollowUp label="Want me to show you how to add badges (build status, license) to the top of your README?" query="Yes, show me how to add build status and license badges to my README.md."/>

```
