# Claude Desktop + Kali Linux - Windows Setup

---

Use Claude Desktop on Windows to control Kali Linux tools over SSH. Claude Desktop connects to the MCP server running on Kali via SSH to execute  tools through natural language

---

## Architecture

```
Windows Host (Claude Desktop)
        |
        | SSH via Python bridge (paramiko)
        |
Kali Linux VM
        |
        | MCP server (mcp-kali-server)
        |
        Kali tools (nmap, gobuster, nikto etc.)
```

---

## Requirements

- Windows PC with 16GB RAM minimum
- VirtualBox with Extension Pack
- Kali Linux VM
- Claude Desktop 
- Python 3.11+ on Windows
- paramiko Python library

---

## Setup

### Step 1 — VirtualBox

1. Download and install VirtualBox from **virtualbox.org**
2. Install the VirtualBox Extension Pack from the same page

3. Check the Host-Only Network:
   ```
   File → Tools → Network
   ```
   VirtualBox usually creates a Host-Only network automatically when installed. You should see one already listed. If the list is empty, click **Create** to add one.

   > **Important:** Select the adapter → click the **DHCP Server** tab → make sure **Enable Server** is ticked. Sometimes DHCP is not enabled by default and your VMs won't get IP addresses without it.

---

### Step 2 — Kali Linux VM

1. Download the Kali Linux VirtualBox image from **kali.org/get-kali/#kali-virtual-machines**

   The download comes as a pre-built VM in a `.7z` archive. Extract it — you will get a `.vdi` file (virtual disk image). Kali is pre-built so you don't need to install it from scratch.

2. Create a new VM using the VDI file:
   ```
   VirtualBox → New
     Name: Kali Linux
     Type: Linux
     Version: Debian 64-bit
     → Next
     RAM: 4096MB (4GB minimum)
     → Next
     Select: Use an existing virtual hard disk file
     → click the folder icon → Add → select the .vdi file
     → Create
   ```

3. Set network adapters:
   ```
   Select Kali VM → Settings → Network

   Adapter 1:
     Attached to: NAT

   Adapter 2:
     tick Enable Network Adapter
     Attached to: Host-Only Adapter
   ```

4. Boot Kali (login: `kali` / `kali`) and run:
   ```bash
   sudo apt update && sudo apt full-upgrade -y
   sudo apt install -y openssh-server
   sudo systemctl enable ssh
   sudo systemctl start ssh
   ip a
   ```
   Note the `192.168.56.x` IP address on the Host-Only adapter — you will need this throughout the setup.

5. **Install tools if missing.** A minimal Kali install may not have all tools pre-installed. If you get warnings about missing tools, run:
   ```bash
   sudo apt install -y nmap gobuster nikto dirb enum4linux hydra john sqlmap wpscan metasploit-framework wordlists
   ```

---

### Step 3 — SSH Key Setup

Open **Command Prompt** on Windows:

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

**Fix a known bug in the package** — the health check passes a list instead of a string which causes tools to show as missing even when installed:

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

### Step 5 — Why We Need a Python Bridge

On Windows, the built-in OpenSSH client behaves differently. When Claude Desktop tries to connect, Windows SSH closes stdin too quickly before Claude can send or receive data. This causes the MCP server to exit immediately every time, regardless of what connection settings you try.

The fix is a small Python script that acts as a bridge. It uses the `paramiko` library to manage the SSH connection properly on Windows — keeping stdin open and forwarding data correctly between Claude Desktop and the Kali MCP server. This is a Windows-only requirement. If you run this setup on macOS or Linux you do not need the bridge.

---

### Step 6 — Install Python and paramiko

1. Download Python from **python.org/downloads** and install it. During installation make sure to tick **Add Python to PATH**.

2. Open **PowerShell** on Windows and verify Python installed:
   ```powershell
   python --version
   ```

3. Install paramiko using PowerShell:
   ```powershell
   python -m pip install paramiko
   ```

---

### Step 7 — Create the Python Bridge Script

Open Notepad and paste the following. Save it as `C:\Users\USERNAME\kali_bridge.py` — when saving make sure to select **All Files** as the file type so it does not save as `.txt`.

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

Replace `192.168.56.x` and `USERNAME` with your actual Kali IP and Windows username.

---

### Step 8 — Claude Desktop

1. Download Claude Desktop from **claude.ai/download**
2. Sign in with your Claude account
3. Press `Win+R` → type `%APPDATA%\Claude` → Enter
4. Open `claude_desktop_config.json` in Notepad and replace everything with:

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

5. Fully quit Claude Desktop (including system tray) and reopen it
6. Go to **Settings → Developer → kali-lab** — should show **running**

---

## Claude Desktop Project Setup

Create a Project in Claude Desktop named **Kali Home Lab** with this example system prompt:

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
| SSH won't connect | Run `ssh -i C:\Users\USERNAME\.ssh\kali_lab kali@192.168.56.x echo ok` in PowerShell |
| Tools show false in health check | Apply the execute_command fix in server.py |
| Request timed out | Make sure kali-mcp-api service is running |
| Kali IP changed after reboot | Run `ip a` in Kali, update `kali_bridge.py` with new IP |
| VMs can't reach each other | Confirm Host-Only adapter is set and DHCP is enabled |

---

## Notes

- The Python bridge is required on Windows due to OpenSSH stdio pipe limitations
- Keep Kali on Host-Only network to isolate it from your real network

---

## References

- [Official Kali MCP blog post](https://www.kali.org/blog/kali-llm-claude-desktop/)
- [mcp-kali-server package](https://www.kali.org/tools/mcp-kali-server/)
- [Claude Desktop download](https://claude.ai/download)
- [MCP Protocol docs](https://modelcontextprotocol.io/docs/getting-started/intro)
