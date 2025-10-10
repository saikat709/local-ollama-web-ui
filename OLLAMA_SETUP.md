## Local Ollama Setup Commands

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama --version
```

```bash
ollama pull llama3.1:8b
ollama run llama3.1
ollama run llama3.1 "sdk"
```

```bash
sudo systemctl status ollama 
# or, if inactive:
sudo systemctl start ollama
```
 
```bash
# Create a systemd override for the Ollama service
sudo systemctl edit ollama
```

### In the editor, add:
```bash
[Service]
Environment="OLLAMA_HOST=0.0.0.0:11434"
```
 
### Save, then:
```bash
sudo systemctl daemon-reload
sudo systemctl restart ollama
```

### Get Host IP
```bash
ip a
```
The line starting with inet has the ip.
 
### Test
```bash
curl http://HOST_IP:11434/api/tags
curl http://HOST_IP:11434/api/generate -d '{
  "model": "llama3.1",
  "prompt": "Say hello from the LAN!",
  "stream": false
}'
```
 
### Custom Cmmand
#### windows
```bash
function ask { param([string]$q) (Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/generate" -Method POST -ContentType "application/json" -Body (@{model="llama3.1"; prompt=$q; stream=$false} | ConvertTo-Json)).response }
```
 
#### Ubuntu
```bash
echo 'ask() { curl -s -X POST http://127.0.0.1:11434/api/generate \
  -H "Content-Type: application/json" \
  -d "{\"model\":\"llama3.1\",\"prompt\":\"$*\",\"stream\":false}" \
  | jq -r .response; }' >> ~/.bashrc
```
 
### remove
```bash
sudo rm -rf /usr/local/bin/ollama
rm -rf ~/.ollama
```