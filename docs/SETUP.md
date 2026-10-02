# Beginner setup guide

You need a computer, a web browser, Python, and an OpenRouter account. The app runs on your own computer. Nothing needs to be deployed.

## Easiest option: ask an agent

Use the copy-and-paste prompt in the [README](../README.md). An agent with access to your computer can download this project, check Python, start it, and open the app. It should follow [AGENTS.md](../AGENTS.md).

You do the account and key steps below yourself. You do not need to send the agent your password, payment details, or API key.

## 1. Get an OpenRouter API key

An API key is a private password that lets this app use models through your OpenRouter account. One OpenRouter key works across the models offered here; you do not need separate keys for Claude, OpenAI, Gemini, or the other providers.

1. Open [OpenRouter](https://openrouter.ai/) and create an account, or sign in.
2. Open [API Keys](https://openrouter.ai/settings/keys) in your account settings.
3. Choose **Create Key** and give it a recognizable name, such as `Model Notebook`.
4. Set a small credit/spending limit you are comfortable with, for example $5. A key limit is a spending cap, not a credit purchase. If a reset option is shown, choose no reset for a total cap while trying the app.
5. Create the key and copy it when shown. Treat it like a password. Paste it only into the app's **OpenRouter API key** field. Avoid putting it in chat, screenshots, GitHub, or a source file.

Most of the featured models cost money per request. If your balance cannot cover a request, the app will show a credits error. You can review prices on [OpenRouter's model pages](https://openrouter.ai/models) and add credits yourself at [Credits](https://openrouter.ai/settings/credits). Buying credits and enabling automatic top-ups are your decisions; neither is done by this app or by the setup agent. Free models, when available, are in the other-models section and have their own limits.

OpenRouter recommends setting a limit on each key. See its [authentication guide](https://openrouter.ai/docs/guides/overview/auth/authentication) for current key instructions. If a key is accidentally shared, delete or disable it on the API Keys page and create a replacement.

## 2. Start the app

If your agent already opened the app, skip to step 3. Otherwise:

1. Install Python 3.9 or newer from [python.org](https://www.python.org/downloads/) if you do not have it. On Windows, select the option to add Python to PATH if the installer offers it.
2. On the [GitHub repository](https://github.com/charliec2004/model-notebook), click the green **Code** button, then **Download ZIP**. Extract/unzip the downloaded file.
3. Open Terminal on macOS/Linux, or PowerShell on Windows. Change to the extracted folder. Replace the example path below with its actual location; the right folder contains `server.py`.

   macOS/Linux:

   ```sh
   cd "/path/to/model-notebook-main"
   python3 server.py
   ```

   Windows:

   ```powershell
   cd "C:\path\to\model-notebook-main"
   py server.py
   ```

4. Leave that terminal window open. Open **http://127.0.0.1:8000** in your browser. This address points to your own computer.

No `pip install`, Node.js, or extra packages are needed.

## 3. Ask a question

1. Paste your key into **OpenRouter API key**.
2. Choose a model. The requested model families are grouped first. A **Latest** option follows newer releases automatically; a numbered option is better for repeating an experiment against a specific release.
3. Type a question and click **Run question**. Wait for the answer. Each run makes a new, independent request.
4. The answer appears in the main panel and is saved in the sidebar. Click any saved question to read it again. Keep the same question and change models to compare their answers.
5. Use **Export JSON** to download your collection. This file contains your questions and answers, but no API key. **Remove** deletes a response; **Undo** restores the last removal.

Your saved responses remain in this browser after restarting the app. Clearing browser site data deletes them. The key is cleared on refresh, so paste it again when needed. Export any important results before clearing browser data.

## Stop or restart

In the terminal running the app, press **Ctrl+C** to stop it. Run the same start command later to restart. Reload the browser page after a restart.

## If something goes wrong

| Message or symptom | What to do |
| --- | --- |
| Python command not found | Install Python from the link above, then open a new terminal. On Windows try `py`; on macOS/Linux use `python3`. |
| Can't find `server.py` | Change into the extracted project folder that contains that file. |
| Address already in use | Run `python3 server.py --port 8001` (Windows: `py server.py --port 8001`) and open `http://127.0.0.1:8001`. Different ports have separate saved collections. |
| Browser cannot open the app | Check the terminal is still running and use the exact address it prints. |
| Reload to connect to the local server | Reload the page; the server was probably restarted. |
| API key rejected | Copy the key again without extra spaces, or create a replacement on OpenRouter. Use an OpenRouter key, not a direct provider key. |
| Credits error | Check your OpenRouter balance and the key's limit. Add credits only if you want to pay for requests. |
| Model unavailable or request rejected | Refresh the model list or choose another model. Catalog entries can be unavailable for your account or provider. |
| Request timed out | Wait before trying again. A timed-out request may still cost credits; the app does not retry automatically. |
| Browser storage is unavailable or full | Export JSON before closing the page. New responses are being kept only in memory. |
