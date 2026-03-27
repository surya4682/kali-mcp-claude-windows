import sys
import threading
import paramiko

# -----------------------------------------------
# Update these values before running
# -----------------------------------------------
KALI_HOST = "192.168.56.x"              # Kali VM IP (run `ip a` in Kali to find it)
KALI_USER = "kali"
KALI_KEY  = r"C:\Users\USERNAME\.ssh\kali_lab"  # Path to your private SSH key
# -----------------------------------------------


def stdin_to_remote(chan):
    """Forward local stdin to the remote SSH channel."""
    try:
        while True:
            data = sys.stdin.buffer.read1(4096)
            if not data:
                break
            chan.sendall(data)
    except Exception:
        pass
    finally:
        try:
            chan.shutdown_write()
        except Exception:
            pass


def remote_to_stdout(chan):
    """Forward remote SSH channel output to local stdout."""
    try:
        while True:
            data = chan.recv(4096)
            if not data:
                break
            sys.stdout.buffer.write(data)
            sys.stdout.buffer.flush()
    except Exception:
        pass


# Connect to Kali via SSH
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(
    KALI_HOST,
    username=KALI_USER,
    key_filename=KALI_KEY,
    timeout=30,
    banner_timeout=30,
    auth_timeout=30,
    channel_timeout=None,
)

# Keep the connection alive with periodic keepalives
transport = client.get_transport()
transport.set_keepalive(30)

# Open a session and start the MCP server on Kali
chan = transport.open_session()
chan.settimeout(None)
chan.exec_command("mcp-server")

# Bridge stdin/stdout between Claude Desktop and the remote MCP server
t1 = threading.Thread(target=stdin_to_remote, args=(chan,))
t2 = threading.Thread(target=remote_to_stdout, args=(chan,))

t1.daemon = True
t2.daemon = True

t1.start()
t2.start()

# Wait for the output thread to finish (connection closed or server stopped)
t2.join()
client.close()
