from whale_cli.context import find_project_root, load_agents_md


def test_load_agents_md_merges_root_to_leaf(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    leaf = root / "pkg" / "api"
    leaf.mkdir(parents=True)
    (root / ".git").mkdir()
    (root / "AGENTS.md").write_text("root rule", encoding="utf-8")
    (leaf / "AGENTS.md").write_text("leaf rule", encoding="utf-8")
    monkeypatch.chdir(leaf)

    assert find_project_root() == root
    merged = load_agents_md()
    assert "root rule" in merged
    assert "leaf rule" in merged
    assert merged.index("root rule") < merged.index("leaf rule")


def test_load_agents_md_leaf_first_budget(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    leaf = root / "pkg"
    leaf.mkdir(parents=True)
    (root / ".git").mkdir()
    (root / "AGENTS.md").write_text("root " * 100, encoding="utf-8")
    (leaf / "AGENTS.md").write_text("leaf-important", encoding="utf-8")
    monkeypatch.chdir(leaf)

    merged = load_agents_md(max_bytes=800)
    assert "leaf-important" in merged
