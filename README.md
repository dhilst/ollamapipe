(AI generated)
# 🧠 Command-Ollama Bridge

This Python tool bridges the input/output of a command-line program with an [Ollama](https://ollama.com) large language model (LLM), enabling real-time bidirectional communication between a program and an AI assistant.

---

## ✨ Features

- ✅ Pipes **stdout** of a running command-line process to an Ollama LLM.
- ✅ Sends Ollama's response back to the **stdin** of the process.
- ✅ Designed for interactive or reactive CLI applications.
- ✅ Graceful shutdown with `exit` from the user.
- ✅ Streaming output support with end-of-prompt delimiter.

---

## 📦 Requirements

- Python 3.8+
- [`ollama`](https://pypi.org/project/ollama/) Python package
- An Ollama model installed locally (e.g. `llama3`, `mistral`, etc.)

Install dependencies:

```bash
pip install ollama
```

Make sure your desired model is pulled with:

```bash
ollama pull llama3
```

---

## 🚀 Usage

```bash
python bridge.py --model llama3 --end-of-prompt "THE END OF PROMPT" -- python -u your_script.py
```

### Arguments

| Argument | Description |
|----------|-------------|
| `--model` | (Optional) The Ollama model to use. Default: `llama3` |
| `--end-of-prompt` | The string that marks the end of the command's output block |
| `command` | The command to run. Example: `python -u my_script.py` |

**Example:**

```bash
python bridge.py --model llama3 --end-of-prompt "END" -- python -u interactive_bot.py
```

---

## 🧠 Behavior

1. The subprocess is started and its `stdout` is monitored.
2. Each output block (ending with `--end-of-prompt`) is passed to the LLM.
3. The LLM responds, and the response is fed back into the subprocess's `stdin`.
4. You can type `exit` in the terminal to terminate the bridge gracefully.

---

## 🛠️ Structure

| Function | Role |
|---------|------|
| `read_stream` | Reads command output (until end marker) into queue |
| `write_stream` | Sends LLM responses from queue into command's `stdin` |
| `ollama_processor` | Handles interaction with the Ollama LLM |
| `handle_user_input` | Listens for manual `exit` command to shut down |
| `main` | Coordinates process, tasks, and I/O loops |

---

## 🧪 Use Cases

- Autonomous CLI agents controlled by an LLM.
- Auto-formatters or code transformers reacting to console output.
- Text-based game bots or terminal assistants.

---

## 🧯 Exiting Gracefully

Type:

```bash
exit
```

The program will:
- Send shutdown signals to queues.
- Close subprocess I/O.
- Terminate the running process if needed.

---

## 📝 License

MIT License. Feel free to use and adapt.

---

## 🤝 Contributions

Pull requests and issues are welcome! This project is a building block for AI-driven CLI automation.
