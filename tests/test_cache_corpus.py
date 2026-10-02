"""Checks against the locally cached demo docket. Skipped when the cache has not been built."""
import pytest

from regintel_mcp import config
from regintel_mcp.client import RegsGovClient
from regintel_mcp.service import Service

pytestmark = pytest.mark.skipif(not config.CACHE_DB.exists(), reason="no local cache")


class NoNetwork(RegsGovClient):
    def get(self, *a, **k):
        raise AssertionError("network call on a cache hit")

    def download(self, *a, **k):
        raise AssertionError("download on a cache hit")


def test_rerun_is_cache_only():
    s = Service(client=NoNetwork())
    if not s.con.execute("SELECT 1 FROM comments WHERE docket_id='FDA-2020-D-2307' LIMIT 1").fetchone():
        pytest.skip("demo docket not cached")
    r = s.build_corpus("FDA-2020-D-2307")
    assert r["complete"] and r["n_comments"] == 60
    assert s.list_comments("FDA-2020-D-2307")["n_returned"] == 60
