# Kali Claude Home Lab

Connect Claude Desktop on Windows to a Kali Linux VM via MCP (Model Context Protocol), allowing Claude to run Kali tools and commands through natural language.

---

## Architecture

```
Windows Host (Claude Desktop)
        |
        | Python bridge (paramiko SSH)
        |
Kali Linux VM (192.168.56.3)
```

---

## Requirements

- Windows PC with 16GB RAM minimum
- VirtualBox with Extension Pack
- Kali Linux VM
- Claude Desktop with Claude Pro subscription ($20/month)
- Python 3.11+ on Windows
- paramiko Python library

---

## Setup

### Step 1 — VirtualBox

1. Download and install VirtualBox from **virtualbox.org**
2. Install the VirtualBox Extension Pack from the same page
3. Create a Host-Only Network:
   ```
   File → Tools → Network Manager → Create
   ```
   Note the adapter name (usually `vboxnet0`)

---

### Step 2 — Kali Linux VM

1. Download Kali VM from **kali.org/get-kali/#kali-virtual-machines** (VirtualBox version)
2. Import into VirtualBox:
   ```
   File → Import Appliance → select .ova file
   ```
3. Set network adapters:
   ```
   Settings → Network
   Adapter 1: Host-Only Adapter (vboxnet0)
   Adapter 2: NAT
   ```
4. Boot Kali (login: kali/kali) and run:
   ```bash
   sudo apt update && sudo apt full-upgrade -y
   sudo apt install -y openssh-server
   sudo systemctl enable ssh
   sudo systemctl start ssh
   ip a
   ```
   Note the `192.168.56.x` IP address.

---

### Step 3 — SSH Key Setup

Open Command Prompt on Windows:

```cmd
ssh-keygen -t ed25519 -f C:\Users\USERNAME\.ssh\kali_lab
```

Press Enter twice (no passphrase).

Copy the key to Kali:
```cmd
type C:\Users\USERNAME\.ssh\kali_lab.pub | ssh kali@192.168.56.x "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys"
```

Test:
```cmd
ssh -i C:\Users\USERNAME\.ssh\kali_lab kali@192.168.56.x
```
Should connect with no password prompt.

---

### Step 4 — Install Official Kali MCP Server

In Kali terminal:

```bash
sudo apt update
sudo apt install mcp-kali-server -y
```

**Fix a known bug in the package** — the health check passes a list instead of a string:

```bash
grep -n "which" /usr/share/mcp-kali-server/server.py
sudo nano +LINE_NUMBER /usr/share/mcp-kali-server/server.py
```

Find:
```python
result = execute_command(["which", tool])
```

Change to:
```python
result = execute_command(f"which {tool}")
```

Save: `Ctrl+X` → `Y` → `Enter`

Create auto-start service:

```bash
sudo nano /etc/systemd/system/kali-mcp-api.service
```

Paste:
```ini
[Unit]
Description=Kali MCP API Server
After=network.target

[Service]
ExecStart=/usr/bin/kali-server-mcp --ip 127.0.0.1 --port 5000
Restart=always
User=kali
Environment=PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable kali-mcp-api
sudo systemctl start kali-mcp-api
```

Verify:
```bash
sudo systemctl status kali-mcp-api
curl http://localhost:5000/health
```

Health check should show all tools as `true`.

---

### Step 5 — Python Bridge on Windows

The built-in Windows OpenSSH client has a stdio pipe issue with Claude Desktop. A Python bridge fixes this.

Install paramiko:
```cmd
python -m pip install paramiko
```

Create `C:\Users\USERNAME\kali_bridge.py`:

```python
import sys
import threading
import paramiko

KALI_HOST = "192.168.56.x"   # your Kali IP
KALI_USER = "kali"
KALI_KEY  = r"C:\Users\USERNAME\.ssh\kali_lab"

def stdin_to_remote(chan):
    try:
        while True:
            data = sys.stdin.buffer.read1(4096)
            if not data:
                break
            chan.sendall(data)
    except:
        pass
    finally:
        try:
            chan.shutdown_write()
        except:
            pass

def remote_to_stdout(chan):
    try:
        while True:
            data = chan.recv(4096)
            if not data:
                break
            sys.stdout.buffer.write(data)
            sys.stdout.buffer.flush()
    except:
        pass

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(
    KALI_HOST,
    username=KALI_USER,
    key_filename=KALI_KEY,
    timeout=30,
    banner_timeout=30,
    auth_timeout=30,
    channel_timeout=None
)

transport = client.get_transport()
transport.set_keepalive(30)

chan = transport.open_session()
chan.settimeout(None)
chan.exec_command("mcp-server")

t1 = threading.Thread(target=stdin_to_remote, args=(chan,))
t2 = threading.Thread(target=remote_to_stdout, args=(chan,))

t1.daemon = True
t2.daemon = True

t1.start()
t2.start()

t2.join()
client.close()
```

Replace `192.168.56.x` and `USERNAME` with your actual values.

---

### Step 6 — Claude Desktop

1. Download Claude Desktop from **claude.ai/download**
2. Sign in with your Claude Pro account
3. Press `Win+R` → type `%APPDATA%\Claude`
4. Open `claude_desktop_config.json` and replace everything with:

```json
{
  "mcpServers": {
    "kali-lab": {
      "command": "python",
      "args": [
        "C:\\Users\\USERNAME\\kali_bridge.py"
      ],
      "transport": "stdio"
    }
  }
}
```

Replace `USERNAME` with your actual Windows username.

5. Fully quit Claude Desktop (including system tray) and reopen
6. Go to **Settings → Developer → kali-lab** — should show **running**

---

## Claude Desktop Project Setup

Create a Project in Claude Desktop named **Kali Home Lab** with this system prompt:

```
You have access to a Kali Linux machine via MCP tools in my home lab.

Every time you do anything, structure your response like this:

**What I'm doing:** [one line explaining the action]
**Command:** [exact command being run]
**Output:** [full raw output]
**What this means:** [your interpretation]
**Next step:** [what you're doing next and why]

Wait for my instructions before doing anything.
```

---

## Daily Usage

1. Boot Kali VM — MCP API starts automatically
2. Open Claude Desktop → Kali Home Lab project
3. Start a new chat
4. Give Claude instructions

---

## Adding More MCP Servers

To connect additional VMs or servers, create a bridge script for each and add to the config:

```json
{
  "mcpServers": {
    "kali-lab": {
      "command": "python",
      "args": ["C:\\Users\\USERNAME\\kali_bridge.py"],
      "transport": "stdio"
    },
    "other-vm": {
      "command": "python",
      "args": ["C:\\Users\\USERNAME\\other_bridge.py"],
      "transport": "stdio"
    }
  }
}
```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| MCP shows failed | `sudo systemctl status kali-mcp-api` on Kali |
| SSH won't connect | `ssh -i C:\Users\USERNAME\.ssh\kali_lab kali@192.168.56.x echo ok` |
| Tools show false in health check | Apply the execute_command fix in server.py |
| Request timed out | Make sure kali-mcp-api service is running |
| Kali IP changed after reboot | Run `ip a` in Kali, update `kali_bridge.py` |

---

## Notes

- Claude Pro subscription required — MCP does not work on the free tier
- The Python bridge is required on Windows due to OpenSSH stdio pipe limitations
- The official Kali guide covers macOS only — this README documents the Windows-specific setup
- Keep Kali on Host-Only network to isolate it from your real network

---

## References

- Official Kali MCP blog post: kali.org/blog/kali-llm-claude-desktop
- mcp-kali-server package: pkg.kali.org
- Claude Desktop download: claude.ai/download
- MCP Protocol docs: modelcontextprotocol.io
