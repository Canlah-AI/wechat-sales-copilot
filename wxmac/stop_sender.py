"""Stop the outreach sender between two messages, never in the middle of one.

Usage: python3 -m wxmac.stop_sender
Takes the UI lock first (the sender holds it while it types and sends), then stops the PID the sender wrote to
<data dir>/outreach/sender.pid, after checking that this PID really is the sender. Never kills by name.
"""
import os, signal, subprocess, sys, time

from .wx_outreach import PID
from .wx_send import UILock


def main() -> int:
    if not PID.exists():
        print("no sender.pid: the sender is not running")
        return 1
    pid = int(PID.read_text().strip())
    cmd = subprocess.run(["ps", "-p", str(pid), "-o", "command="], capture_output=True, text=True).stdout.strip()
    if "wx_outreach send" not in cmd:
        print(f"PID {pid} is not the sender ({cmd or 'not running'}); removing the stale pid file")
        PID.unlink()
        return 1
    with UILock():
        os.kill(pid, signal.SIGTERM)
        for _ in range(20):
            if subprocess.run(["ps", "-p", str(pid)], capture_output=True).returncode:
                break
            time.sleep(0.5)
    PID.unlink(missing_ok=True)
    print(f"stopped sender PID {pid}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
