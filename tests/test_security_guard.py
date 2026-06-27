"""Security guard (scripts/security_guard.py) — each rule CATCHES a real risk, clean
lines pass, the inline suppressions (# nosec: / # sql-safe:) work, and the live repo
scans clean (no false positives, no tracked secrets).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "security_guard", Path(__file__).resolve().parent.parent / "scripts" / "security_guard.py"
)
sg = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(sg)


def test_rule1_dangerous_calls_caught():
    assert sg._rule1_danger("result = eval(user_input)")
    assert sg._rule1_danger("exec(payload)")
    assert sg._rule1_danger("os.system(cmd)")
    assert sg._rule1_danger("subprocess.run(cmd, shell=True)")
    assert sg._rule1_danger("data = pickle.loads(blob)")
    assert sg._rule1_danger("mod = __import__(name)")
    assert sg._rule1_danger("cfg = yaml.load(f)")  # no safe Loader


def test_rule1_clean_lines_and_suppression():
    assert not sg._rule1_danger("def eval(n: int = 40) -> None:")  # a definition, not a call
    assert not sg._rule1_danger(
        "# run the answer+judge eval (TSU-42)"
    )  # prose: 'eval (' has a space
    assert not sg._rule1_danger("help='LLM for --eval (answers)'")  # help-string prose
    assert not sg._rule1_danger("cfg = yaml.load(f, Loader=yaml.SafeLoader)")  # safe loader
    assert not sg._rule1_danger("cfg = yaml.safe_load(f)")
    assert not sg._rule1_danger(
        "os.system(cmd)  # nosec: fixed literal, no user input"
    )  # suppressed


def test_rule2_hardcoded_secret_caught():
    assert sg._rule2_secret('API_KEY = "sk-abcdef0123456789abcd"')
    assert sg._rule2_secret('password = "hunter2hunter2hunter2"')
    assert sg._rule2_secret("auth_token = 'tok_live_0123456789abcdef'")
    assert sg._rule2_secret("key = 'ghp_0123456789abcdefghijABCDEFG'")


def test_rule2_clean_lines():
    assert not sg._rule2_secret("token: str = os.getenv('TROVEX_WRITE_TOKEN', '')")
    assert not sg._rule2_secret('write_token: str = ""')  # empty default
    assert not sg._rule2_secret("token = settings.resolve_write_token()")  # a call, not a literal
    assert not sg._rule2_secret('WRITE_TOKEN_FILE = ".write_token"')  # a filename, excluded
    assert not sg._rule2_secret('api_key = "<your-key-here>"')  # placeholder


def test_rule3_raw_sql_interpolation_caught():
    assert sg._rule3_sql('cur.execute(f"SELECT * FROM docs WHERE id = {doc_id}")')
    assert sg._rule3_sql('db.executescript(f"DROP TABLE {name}")')
    assert sg._rule3_sql('cur.execute("SELECT * FROM t WHERE x = %s" % val)')
    assert sg._rule3_sql('cur.execute("... {}".format(v))')


def test_rule3_clean_and_suppression():
    assert not sg._rule3_sql(
        'cur.execute("SELECT * FROM docs WHERE id = ?", (doc_id,))'
    )  # parameterized
    # a vetted structural splice (a column/where-clause, never a value) is marked inline
    assert not sg._rule3_sql(
        'conn.execute(f"ALTER TABLE docs ADD COLUMN {col} TEXT")  # sql-safe: fixed literal'
    )


def test_live_repo_scans_clean():
    """The guard must pass on the current backend surfaces — zero false positives."""
    assert sg.scan() == []


def test_no_secret_files_tracked():
    """No credential file (.env / *.pem / .write_token …) is committed to the repo."""
    assert sg.tracked_secret_files() == []
