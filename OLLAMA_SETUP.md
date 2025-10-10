## Local Ollama Setup Commands

### 1. Install ollama
```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama --version
```

### 2. Pull/download a model from repository
```bash
ollama pull llama3.1:8b
ollama run llama3.1
ollama run llama3.1 "sdk"
```

### 3. Check the status
```bash
sudo systemctl status ollama 
# or, if inactive:
sudo systemctl start ollama
```
 
### 4.1 Lets make it a host server
```bash
# Create a systemd override for the Ollama service
sudo systemctl edit ollama
```

### 4.2 In the editor, add:
```bash
[Service]
Environment="OLLAMA_HOST=0.0.0.0:11434"
```
 
### 4.3 Save, then:
```bash
sudo systemctl daemon-reload
sudo systemctl restart ollama
```

### 5. Get Host IP
```bash
ip a
```
The line starting with inet has the ip.
 
### 6. Test
```bash
curl http://HOST_IP:11434/api/tags
curl http://HOST_IP:11434/api/generate -d '{
  "model": "llama3.1",
  "prompt": "Say hello from the LAN!",
  "stream": false
}'
```
 
### 7. Custom Cmmand
#### 7.1 windows
```bash
function ask { 
  param([string]$q) (
    Invoke-RestMethod 
    -Uri "http://127.0.0.1:11434/api/generate" 
    -Method POST 
    -ContentType "application/json" 
    -Body (@{model="llama3.1"; prompt=$q; stream=$false} | 
    ConvertTo-Json)
    ).response 
  }
```
 
#### 7.2 Ubuntu
```bash
echo 'ask() {           \
  curl -s -X POST http://127.0.0.1:11434/api/generate \
  -H "Content-Type: application/json" \
  -d "{                         \
    \"model\":\"llama3.1\",     \
    \"prompt\":\"$*\",          \
    \"stream\":false}"          \
  | jq -r .response;            \
  }' >> ~/.bashrc
```
 
### 18. Remove
```bash
sudo rm -rf /usr/local/bin/ollama
rm -rf ~/.ollama
```