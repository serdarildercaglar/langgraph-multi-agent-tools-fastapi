"""Start vLLM server with Qwen model."""

import subprocess
import sys

MODEL = "Qwen/Qwen2.5-7B-Instruct-AWQ"
PORT = 8000

cmd = [
    sys.executable, "-m", "vllm.entrypoints.openai.api_server",
    "--model", MODEL,
    "--quantization", "awq",
    "--max-model-len", "4096",
    "--gpu-memory-utilization", "0.9",
    "--trust-remote-code",
    "--host", "0.0.0.0",
    "--port", str(PORT),
    "--enable-auto-tool-choice",
    "--tool-call-parser", "hermes",
]

print(f"Starting vLLM server with {MODEL} on port {PORT}...")
print(f"Command: {' '.join(cmd)}")
print("-" * 50)

subprocess.run(cmd)
