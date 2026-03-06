"""Start vLLM server with Qwen model."""

import subprocess
import sys

MODEL = "QuantTrio/Qwen3.5-9B-AWQ"
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
    "--reasoning-parser", "qwen3",
    "--enable-auto-tool-choice",
    "--tool-call-parser", "qwen3_coder",
]

print(f"Starting vLLM server with {MODEL} on port {PORT}...")
print(f"Command: {' '.join(cmd)}")
print("-" * 50)

subprocess.run(cmd)
