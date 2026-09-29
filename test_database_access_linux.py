"""Run the exact generated module DB preparation block on isolated fixtures."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

GATE = Path(__file__).with_name('assets').joinpath('ksu/boot/gate.sh').read_text(encoding='utf-8')
BLOCK = GATE.split('# BEGIN DOLBY DATABASE ACCESS', 1)[1].split('# END DOLBY DATABASE ACCESS', 1)[0]


class DatabaseAccessTests(unittest.TestCase):
    def run_case(self, kind):
        with tempfile.TemporaryDirectory(prefix='dolby-access-') as tmp:
            root = Path(tmp)
            folder = root / 'dolby'
            folder.mkdir()
            target = folder / 'dax_sqlite3.db'
            if kind == 'directory':
                target.mkdir()
            elif kind in ('symlink', 'hardlink'):
                outside = root / 'outside'
                outside.write_bytes(b'untouched')
                target.symlink_to(outside) if kind == 'symlink' else os.link(outside, target)
            elif kind == 'directory_symlink':
                folder.rmdir()
                outside = root / 'outside'
                outside.mkdir()
                folder.symlink_to(outside, target_is_directory=True)
            elif kind != 'missing':
                for suffix in ('', '-wal', '-shm', '-journal'):
                    p = folder / ('dax_sqlite3.db' + suffix)
                    p.write_bytes(('original-content' + suffix).encode())
                    p.chmod(0o666)
            unrelated = root / 'unrelated'
            unrelated.write_bytes(b'unchanged')
            before = {p: p.read_bytes() for p in folder.iterdir() if p.is_file()}
            # Ownership and SELinux are intercepted: no root privileges required,
            # but real chmod executes only under TemporaryDirectory.
            prelude = '''
                fail() { echo "$*" >&2; exit 23; }
                chown() { printf 'chown %s %s\n' "$1" "$2" >> "$TRACE"; }
                chcon() { printf 'chcon %s %s\n' "$1" "$2" >> "$TRACE"; }
            '''
            script = prelude + BLOCK.replace('/data/vendor/dolby', str(folder))
            trace = root / 'trace'
            run = subprocess.run(['sh'], input=script, text=True, capture_output=True,
                                 env=os.environ | {'TRACE': str(trace)})
            if kind in ('symlink', 'hardlink', 'directory', 'directory_symlink'):
                self.assertEqual(run.returncode, 23, run.stderr)
                self.assertFalse(trace.exists(), 'Invalid paths must fail before mutations')
            else:
                self.assertEqual(run.returncode, 0, run.stderr)
                self.assertEqual(folder.stat().st_mode & 0o777, 0o770)
                if kind == 'missing':
                    self.assertFalse(target.exists(), 'Do not create an empty DB')
                else:
                    for p, content in before.items():
                        self.assertEqual(p.read_bytes(), content)
                        self.assertEqual(p.stat().st_mode & 0o777, 0o600)
                        self.assertIn('chown 1013:1013 ' + str(p), trace.read_text())
            self.assertEqual(unrelated.read_bytes(), b'unchanged')

    def test_regular_with_sidecars(self): self.run_case('regular')
    def test_no_database_is_created(self): self.run_case('missing')
    def test_symlink_rejected(self): self.run_case('symlink')
    def test_hardlink_rejected(self): self.run_case('hardlink')
    def test_directory_file_rejected(self): self.run_case('directory')
    def test_directory_symlink_rejected(self): self.run_case('directory_symlink')


if __name__ == '__main__':
    unittest.main()
