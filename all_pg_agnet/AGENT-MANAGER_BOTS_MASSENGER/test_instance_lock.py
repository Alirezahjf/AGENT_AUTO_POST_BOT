#!/usr/bin/env python3
"""Single-instance guard tests (real processes, temporary directory only).

Every "bot.py" here is a tiny stand-in script inside a temp dir; the real bot, its
bot.lock / bot.pid and the databases are never touched.
"""
import logging
import os
import signal
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import instance_lock  # noqa: E402

HOLDER = textwrap.dedent("""
    import os, sys, time
    sys.path.insert(0, {here!r})
    import instance_lock
    lock = instance_lock.InstanceLock(os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot.lock"))
    ok, _ = lock.acquire()
    print("locked" if ok else "busy", flush=True)
    time.sleep(60)
""")
LEGACY = "import time\nprint('legacy', flush=True)\ntime.sleep(60)\n"  # old bot.py: no lock at all
GUARD = textwrap.dedent("""
    import logging, sys
    sys.path.insert(0, {here!r})
    import instance_lock
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)
    lock = instance_lock.ensure_single_instance({script!r}, logging.getLogger("t"), restore_wait=0.2)
    print("RESULT", "acquired" if lock else "refused", flush=True)
""")


class ListLog:
    def __init__(self):
        self.lines = []

    def info(self, msg):
        self.lines.append(("INFO", msg))

    def error(self, msg):
        self.lines.append(("ERROR", msg))

    def text(self):
        return "\n".join(m for _, m in self.lines)


class InstanceLockTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="instance-lock-test-")
        self.dir = Path(self.tmp.name)
        self.script = self.dir / "bot.py"
        self.procs = []

    def tearDown(self):
        for proc in self.procs:
            if proc.poll() is None:
                proc.kill()
            proc.wait()
            if proc.stdout:
                proc.stdout.close()
        self.tmp.cleanup()

    def start(self, source, name="bot.py"):
        path = self.dir / name
        path.write_text(source, encoding="utf-8")
        proc = subprocess.Popen([sys.executable, name], cwd=str(self.dir),
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        self.procs.append(proc)
        first_line = proc.stdout.readline().strip()
        return proc, first_line

    def run_guard(self):
        code = GUARD.format(here=str(HERE), script=str(self.script))
        out = subprocess.run([sys.executable, "-c", code], cwd=str(self.dir),
                             capture_output=True, text=True, timeout=30)
        return out.stdout

    def test_second_instance_is_refused_while_first_runs(self):
        holder, state = self.start(HOLDER.format(here=str(HERE)))
        self.assertEqual(state, "locked")
        (self.dir / "bot.pid").write_text(f"{os.getpid()}\n")  # launcher already wrote OUR pid
        log = ListLog()
        self.assertIsNone(instance_lock.ensure_single_instance(str(self.script), log, restore_wait=0.2))
        self.assertIn(f"PID {holder.pid}", log.text())
        self.assertIn("exits now", log.text())
        # bot.pid points at the instance that is really running again
        self.assertEqual((self.dir / "bot.pid").read_text().strip(), str(holder.pid))

    def test_lock_is_released_when_the_holder_dies_even_with_kill_9(self):
        holder, state = self.start(HOLDER.format(here=str(HERE)))
        self.assertEqual(state, "locked")
        os.kill(holder.pid, signal.SIGKILL)
        holder.wait()
        log = ListLog()
        lock = instance_lock.ensure_single_instance(str(self.script), log)
        self.assertIsNotNone(lock, log.text())
        self.addCleanup(lock.release)
        self.assertEqual((self.dir / "bot.lock").read_text().strip(), str(os.getpid()))

    def test_stale_lock_file_does_not_block(self):
        (self.dir / "bot.lock").write_text("999999\n")
        lock = instance_lock.ensure_single_instance(str(self.script), ListLog())
        self.assertIsNotNone(lock)
        lock.release()

    def test_other_bot_pid_content_is_not_overwritten(self):
        holder, _ = self.start(HOLDER.format(here=str(HERE)))
        (self.dir / "bot.pid").write_text("424242\n")
        self.assertIsNone(instance_lock.ensure_single_instance(str(self.script), ListLog(), restore_wait=0.2))
        self.assertEqual((self.dir / "bot.pid").read_text().strip(), "424242")

    def test_older_lockless_bot_blocks_a_new_start(self):
        legacy, state = self.start(LEGACY)
        self.assertEqual(state, "legacy")
        out = self.run_guard()
        self.assertIn("RESULT refused", out)
        self.assertIn(f"PID {legacy.pid}", out)
        self.assertIn("kill <PID>", out)
        # the refused process released the lock again
        probe = instance_lock.InstanceLock(self.dir / "bot.lock")
        self.assertEqual(probe.acquire(), (True, None))
        probe.release()

    def test_single_start_acquires(self):
        self.assertIn("RESULT acquired", self.run_guard())

    def test_only_older_same_script_processes_count(self):
        first, _ = self.start(LEGACY)
        time.sleep(0.05)
        second, _ = self.start(LEGACY)
        other_dir = self.dir / "other"
        other_dir.mkdir()
        (other_dir / "bot.py").write_text(LEGACY)
        foreign = subprocess.Popen([sys.executable, "bot.py"], cwd=str(other_dir),
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        self.procs.append(foreign)
        foreign.stdout.readline()
        self.assertEqual(instance_lock.find_older_instances(self.script, own_pid=second.pid), [first.pid])
        self.assertEqual(instance_lock.find_older_instances(self.script, own_pid=first.pid), [])

    def test_lock_file_replaced_under_us_is_retried(self):
        lock = instance_lock.InstanceLock(self.dir / "bot.lock")
        self.assertEqual(lock.acquire(), (True, None))
        lock.release()
        (self.dir / "bot.lock").unlink()
        again = instance_lock.InstanceLock(self.dir / "bot.lock")
        self.assertEqual(again.acquire(), (True, None))
        again.release()


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    unittest.main(verbosity=2)
