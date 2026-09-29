"""Offline shell/fixture tests; run on Linux/WSL. Never touches phone paths."""
from pathlib import Path
import os
import re
import sqlite3
import subprocess
import tempfile
import unittest


TEMPLATE = Path(__file__).with_name('collect-dolby.sh.in').read_text(encoding='utf-8')


class DatabaseCollectorTests(unittest.TestCase):
    def test_shell_syntax(self):
        subprocess.run(['sh', '-n'], input=TEMPLATE, text=True, check=True)

    def run_fixture(self, state):
        with tempfile.TemporaryDirectory(prefix='dolby-db-test-') as name:
            root = Path(name)
            data = root / 'data/vendor/dolby'
            data.mkdir(parents=True)
            work = root / 'work'
            report = work / 'report'
            report.mkdir(parents=True)
            (work / 'seen').touch()
            db = data / 'dax_sqlite3.db'
            if state == 'regular':
                with sqlite3.connect(db) as conn:
                    conn.execute('CREATE TABLE test (value TEXT)')
                    conn.execute("INSERT INTO test VALUES ('fixture')")
                (data / 'dax_sqlite3.db-wal').write_bytes(b'wal fixture')
                (data / 'dax_sqlite3.db-shm').write_bytes(b'shm fixture')
                (data / 'dax_sqlite3.db-journal').write_bytes(b'journal fixture')
            elif state == 'symlink_file':
                outside = root / 'outside'
                outside.write_bytes(b'must not collect')
                db.symlink_to(outside)
            elif state == 'symlink_dir':
                data.rmdir()
                outside = root / 'outside'
                outside.mkdir()
                (outside / 'dax_sqlite3.db').write_bytes(b'must not collect')
                data.symlink_to(outside, target_is_directory=True)
            before = {p.name: p.read_bytes() for p in data.iterdir() if p.is_file() and not p.is_symlink()}
            # Extract only our function definitions; do not execute Android entrypoint.
            helpers = TEMPLATE[TEMPLATE.index('capture() {'):TEMPLATE.index('snapshot() {')]
            functions = TEMPLATE[TEMPLATE.index('database_metadata() {'):TEMPLATE.index("printf 'Dolby one-shot diagnostics")]
            code = helpers + functions
            code = re.sub(r'/data(?=/|\b)', str(root / 'data'), code)
            env = os.environ | {'R': str(report), 'W': str(work), 'M': str(root / 'module')}
            script = '''
                total=0; count=0
                bounded() { shift; "$@"; }
                pidof() { return 1; }
                logcat() { echo 'fixture log'; }
            ''' + code + '\ncollect_database\n'
            subprocess.run(['sh'], input=script, text=True, env=env, check=True, capture_output=True)
            self.assertTrue((report / 'database/metadata-before.txt').exists())
            self.assertTrue((report / 'database/metadata-after.txt').exists())
            self.assertIn('NOT a transactional', (report / 'database/README.txt').read_text())
            if state == 'regular':
                for filename, content in before.items():
                    self.assertEqual(content, (report / 'database/files' / filename).read_bytes())
                    self.assertEqual(content, (data / filename).read_bytes())
            else:
                self.assertFalse((report / 'database/files/dax_sqlite3.db').exists())
            if state == 'absent':
                self.assertIn('MISSING ', (report / 'database/metadata-before.txt').read_text())
            if state == 'symlink_file':
                self.assertIn('LINK ', (report / 'files-skipped.txt').read_text())
            if state == 'symlink_dir':
                self.assertIn('SYMLINK_DIRECTORY', (report / 'database/metadata-before.txt').read_text())

    def test_regular_database_and_sidecars(self):
        self.run_fixture('regular')

    def test_missing_database(self):
        self.run_fixture('absent')

    def test_symlink_file_is_not_copied(self):
        self.run_fixture('symlink_file')

    def test_symlink_directory_is_not_copied(self):
        self.run_fixture('symlink_dir')


if __name__ == '__main__':
    unittest.main()
