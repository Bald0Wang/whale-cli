from pathlib import Path

from whale_cli.agents import load_agent_spec, render_system_prompt
from whale_cli.skill.discovery import SkillRoot, discover_skills, format_skills_for_prompt, read_skill_text


def _write_skill(root: Path, name: str, description: str, body: str = "body"):
    d = root / name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n\n# {name}\n\n{body}\n",
        encoding="utf-8",
    )


def test_discover_skills_keeps_highest_priority(tmp_path):
    project = tmp_path / "project"
    user = tmp_path / "user"
    _write_skill(user, "bug-fix", "user version")
    _write_skill(project, "bug-fix", "project version")
    _write_skill(project, "review", "project review")

    skills = discover_skills([SkillRoot(project, "project"), SkillRoot(user, "user")])
    by_name = {s.name: s for s in skills}
    assert by_name["bug-fix"].description == "project version"
    assert by_name["bug-fix"].scope == "project"
    assert "review" in by_name
    assert "project version" in format_skills_for_prompt(skills)
    assert "project version" in read_skill_text("bug-fix", [SkillRoot(project, "project"), SkillRoot(user, "user")])


def test_agent_spec_and_template_render(tmp_path):
    agent_dir = tmp_path / "agent"
    agent_dir.mkdir()
    (agent_dir / "agent.yaml").write_text(
        "name: test\nsystem_prompt: system.md\ntools:\n  - Bash\n  - ReadFile\n",
        encoding="utf-8",
    )
    (agent_dir / "system.md").write_text("Hello {{ name }} with {{ tools }}", encoding="utf-8")
    spec = load_agent_spec(agent_dir / "agent.yaml")
    assert spec.name == "test"
    assert spec.tools == ["Bash", "ReadFile"]
    assert render_system_prompt(spec, {"name": "Whale", "tools": "Bash"}) == "Hello Whale with Bash\n"
