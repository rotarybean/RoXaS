# deploy.ps1 - copy the RoXaS service + web console to the Pi. Run from the repo root (rx8-c3m) in PowerShell:
#   powershell -ExecutionPolicy Bypass -File software/service/deploy.ps1            (code + database)
#   powershell -ExecutionPolicy Bypass -File software/service/deploy.ps1 -Images    (also the 26 MB of catalog page pictures, first time only)
# Your hand edits live in ~/roxas/user.sqlite on the Pi. This script never touches that file; the edits are re-applied
# on top of the new roxas.sqlite when the service or web console starts, so restart both after deploying.
param([string]$Pi = "rotarybean@RoXaS-CM5", [switch]$Images)
ssh $Pi "mkdir -p ~/roxas/rag ~/roxas/web"
scp software/service/roxas.py software/service/userdata.py software/service/webui.py "${Pi}:~/roxas/"
scp software/service/web/index.html "${Pi}:~/roxas/web/"
scp software/rag/rag.py software/rag/answer.py software/rag/prompt.py software/rag/embed.py "${Pi}:~/roxas/rag/"
scp data/derived/roxas.sqlite data/derived/doc_emb.npz "${Pi}:~/roxas/"
if ($Images) { scp -r data/derived/verify2/img "${Pi}:~/roxas/" }
