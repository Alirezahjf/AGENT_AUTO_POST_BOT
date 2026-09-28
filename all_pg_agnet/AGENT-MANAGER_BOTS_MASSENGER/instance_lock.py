"""Single-instance guard for bot.py.

Two bot.py processes polling the same Bale token split the updates between them. Each
process keeps its own in-memory ``user_states`` (multi-step forms such as a new support
ticket), so consecutive steps of one user land in different processes and the form
breaks at random.

The guard holds an exclusive, non-blocking ``fcntl.flock`` on ``bot.lock`` next to bot.py
for the whole process lifetime. The kernel drops the lock when the process dies (even on
``kill -9``), so a leftover file never blocks a restart. bot.pid is deliberately NOT the
lock: start.sh / safe_deploy_e192.sh ``rm -f`` it, which would hand a fresh inode (and a
free lock) to a second process.

Older bot.py versions do not take the lock, so after acquiring it we also scan /proc for
an older process running this same bot.py (first deploy over duplicates left behind).
"""
import errno
import fcntl
import os
import time

LOCK_FILE_NAME = "bot.lock"
PID_FILE_NAME = "bot.pid"


def _read_pid_from_fd(fd):
    try:
        os.lseek(fd, 0, os.SEEK_SET)
        raw = os.read(fd, 64).decode("ascii", "ignore").strip()
        return int(raw) if raw.isdigit() else None
    except OSError:
        return None


class InstanceLock:
    """Exclusive process lock on a file; ``acquire`` never blocks."""

    def __init__(self, path):
        self.path = str(path)
        self._fd = None

    @property
    def held(self):
        return self._fd is not None

    def acquire(self):
        """Returns (True, None) when this process now owns the lock, else (False, holder_pid)."""
        for _ in range(5):
            fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o644)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                holder = _read_pid_from_fd(fd)
                os.close(fd)
                if exc.errno in (errno.EAGAIN, errno.EACCES, errno.EWOULDBLOCK):
                    return False, holder
                raise
            # The file may have been unlinked/replaced between open() and flock(): only a lock
            # on the inode that is currently at self.path excludes anybody.
            try:
                same_file = os.path.samestat(os.fstat(fd), os.stat(self.path))
            except FileNotFoundError:
                same_file = False
            if not same_file:
                os.close(fd)
                continue
            os.ftruncate(fd, 0)
            os.write(fd, f"{os.getpid()}\n".encode("ascii"))
            self._fd = fd
            return True, None
        raise RuntimeError(f"could not lock {self.path}: the file keeps being replaced")

    def release(self):
        if self._fd is None:
            return
        try:
            fcntl.flock(self._fd, fcntl.LOCK_UN)
        finally:
            os.close(self._fd)
            self._fd = None


# ---------------------------------------------------------------- /proc helpers

def _proc_start_ticks(pid, proc_root="/proc"):
    """Process start time (clock ticks since boot) from /proc/<pid>/stat, or None."""
    try:
        with open(f"{proc_root}/{pid}/stat", "rb") as fh:
            data = fh.read().decode("ascii", "ignore")
        fields = data.rsplit(")", 1)[1].split()
        if fields[0] == "Z":  # zombie: already dead
            return None
        return int(fields[19])  # field 22 of stat; fields[] starts at field 3
    except (OSError, IndexError, ValueError):
        return None


def _proc_script(pid, proc_root="/proc"):
    """Absolute path of the bot.py a python process runs, else None."""
    try:
        with open(f"{proc_root}/{pid}/cmdline", "rb") as fh:
            argv = [a.decode("utf-8", "replace") for a in fh.read().split(b"\0") if a]
    except OSError:
        return None
    if not argv or "python" not in os.path.basename(argv[0]):
        return None
    script = next((a for a in argv[1:] if os.path.basename(a) == "bot.py"), None)
    if not script:
        return None
    if not os.path.isabs(script):
        try:
            script = os.path.join(os.readlink(f"{proc_root}/{pid}/cwd"), script)
        except OSError:
            return None
    return os.path.realpath(script)


def find_older_instances(script_path, own_pid=None, proc_root="/proc"):
    """PIDs of live processes that run this same bot.py and started before us.

    Newer processes are ignored on purpose: they lose the flock race and exit by
    themselves, and counting them could make two simultaneous starts refuse each other.
    """
    script_path = os.path.realpath(script_path)
    own_pid = own_pid or os.getpid()
    own_start = _proc_start_ticks(own_pid, proc_root)
    found = []
    try:
        entries = os.listdir(proc_root)
    except OSError:
        return found
    for entry in entries:
        if not entry.isdigit() or int(entry) == own_pid:
            continue
        pid = int(entry)
        if _proc_script(pid, proc_root) != script_path:
            continue
        start = _proc_start_ticks(pid, proc_root)
        if start is None:
            continue
        if own_start is not None and (start, pid) > (own_start, own_pid):
            continue
        found.append(pid)
    return sorted(found)


def _pid_runs_script(pid, script_path, proc_root="/proc"):
    return bool(pid) and _proc_script(pid, proc_root) == os.path.realpath(script_path)


def _restore_pid_file(pid_path, holder_pid, own_pid, wait_seconds=2.0):
    """If a launcher just wrote OUR (dying) pid into bot.pid, point it back at the holder.

    start.sh / safe_deploy write ``$!`` right after launching, possibly a moment after we
    got here, so wait briefly for that write. Any other content is left untouched.
    """
    deadline = time.monotonic() + wait_seconds
    content = None
    while True:
        try:
            with open(pid_path, "r", encoding="ascii", errors="ignore") as fh:
                content = fh.read().strip()
        except FileNotFoundError:
            content = ""
        except OSError:
            return False
        if content == str(own_pid) or time.monotonic() >= deadline:
            break
        time.sleep(0.1)
    if content not in ("", str(own_pid)):
        return False
    try:
        with open(pid_path, "w", encoding="ascii") as fh:
            fh.write(f"{holder_pid}\n")
        return True
    except OSError:
        return False


def ensure_single_instance(script_path, log, proc_root="/proc", restore_wait=2.0):
    """Acquire the bot lock; on conflict log a clear reason and return None (caller exits)."""
    script_path = os.path.realpath(script_path)
    bot_dir = os.path.dirname(script_path)
    lock = InstanceLock(os.path.join(bot_dir, LOCK_FILE_NAME))
    own_pid = os.getpid()

    acquired, holder = lock.acquire()
    if not acquired:
        log.error(
            f"⛔ [single-instance] bot.py already running (PID {holder or '?'}, holds {LOCK_FILE_NAME}). "
            f"This duplicate (PID {own_pid}) exits now so that only one process polls the Bale token. "
            f"یک نمونهٔ ربات از قبل در حال اجراست؛ این نمونهٔ تکراری بسته شد. "
            f"برای ری‌استارت: اول همان PID {holder or '?'} را متوقف کن، بعد دوباره اجرا کن.")
        if holder and _pid_runs_script(holder, script_path, proc_root):
            if _restore_pid_file(os.path.join(bot_dir, PID_FILE_NAME), holder, own_pid, restore_wait):
                log.error(f"⛔ [single-instance] {PID_FILE_NAME} points to the running instance again: {holder}")
        return None

    older = find_older_instances(script_path, own_pid, proc_root)
    if older:
        pids = " ".join(str(p) for p in older)
        log.error(
            f"⛔ [single-instance] older bot.py process(es) without the lock are still polling: PID {pids}. "
            f"This process (PID {own_pid}) will NOT start a second poller. "
            f"پروسهٔ قدیمی bot.py هنوز روشن است (PID {pids}). فقط یک نمونه باید بماند: "
            f"پروسه‌های اضافه را با  kill <PID>  ببند (نه pkill) و بعد ربات را دوباره اجرا کن.")
        lock.release()
        return None

    log.info(f"🔒 [single-instance] lock acquired: {LOCK_FILE_NAME} (PID {own_pid})")
    return lock
