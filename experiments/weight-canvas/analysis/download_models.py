from huggingface_hub import snapshot_download
MODELS=[('dllm-hub/Qwen2.5-Coder-0.5B-Instruct-diffusion-mdlm-v0.1','a284e895a6248256baf2f60502e54aba61b24c1a'),('Qwen/Qwen2.5-Coder-0.5B-Instruct','ea3f2471cf1b1f0db85067f1ef93848e38e88c25')]
for repo,rev in MODELS:
 print(snapshot_download(repo,revision=rev,allow_patterns=['*.json','*.jinja','*.txt','*.py','*.safetensors','README.md','LICENSE']))
