from pathlib import Path

import pytest

from whale_cli.storage.session_store import SessionStore


def test_delete_session_removes_messages_and_hides_the_latest_index_record(tmp_path):
    store = SessionStore(str(tmp_path / ".whale_cli"))
    deleted_id = store.create_session(title="删除我")
    retained_id = store.create_session(title="保留我")
    store.append_message(deleted_id, {"role": "user", "content": "temporary"})

    assert store.delete_session(deleted_id) is True
    assert store.get_session_info(deleted_id) is None
    assert store.load_messages(deleted_id) == []
    assert not (Path(store.sessions_dir) / f"{deleted_id}.jsonl").exists()
    assert [session.session_id for session in store.list_sessions()] == [retained_id]
    assert store.delete_session(deleted_id) is False
    with pytest.raises(ValueError, match="invalid session id"):
        store.delete_session("../../index")
