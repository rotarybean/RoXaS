# export_gguf.ps1 - merged HF model -> GGUF f16 -> Q4_K_M. Run from the repo root in PowerShell.
# usage: powershell -File software/tools/export_gguf.ps1 data/derived/lora_run1/merged2 data/derived/gguf
param([string]$Model, [string]$Out)
New-Item -ItemType Directory -Force $Out | Out-Null
if (-not (Test-Path "$Out/llama.cpp")) { git clone --depth 1 https://github.com/ggml-org/llama.cpp "$Out/llama.cpp" }
pip install -q -r "$Out/llama.cpp/requirements/requirements-convert_hf_to_gguf.txt"
python "$Out/llama.cpp/convert_hf_to_gguf.py" $Model --outfile "$Out/roxas-f16.gguf" --outtype f16
# quantizing needs the llama-quantize binary: download the Windows release zip from
# https://github.com/ggml-org/llama.cpp/releases (llama-*-bin-win-cpu-x64.zip), unzip to $Out/bin
& "$Out/bin/llama-quantize.exe" "$Out/roxas-f16.gguf" "$Out/roxas-Q4_K_M.gguf" Q4_K_M
Get-Item "$Out/*.gguf" | Select-Object Name, Length
