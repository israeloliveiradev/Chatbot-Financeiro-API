import subprocess
result = subprocess.run(
    ["docker", "logs", "chatbot_app", "--tail", "500"],
    capture_output=True, text=True, encoding="utf-8", errors="replace"
)
lines = (result.stdout + result.stderr).split("\n")
keywords = ["ERROR", "error", "Erro", "Traceback", "Exception", "audio", "registrar", "aporte", "tool", "Gemini", "gemini", "dispatch"]
filtered = [l for l in lines if any(k in l for k in keywords)]
print("\n".join(filtered[-150:]))
