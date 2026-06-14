"""In-process Inspect eval runner tests."""

from __future__ import annotations

from types import SimpleNamespace

import inspect_ai
import pytest

from goldenmcp_eval_runner import inspect_runner


def test_inspect_task_spec():
    assert inspect_runner.inspect_task_spec("lifi", "quote") == "lifi_quote"
    assert inspect_runner.inspect_task_spec("jupiter", "positions") == "jupiter_positions"
    # 1inch isn't a valid Python identifier prefix; it registers as oneinch_*.
    assert inspect_runner.inspect_task_spec("1inch", "quote") == "oneinch_quote"
    assert inspect_runner.inspect_task_spec("1inch", "swap") == "oneinch_swap"


def _eval_log_namespace(
    *,
    status: str,
    location: str = "",
    error: object | None = None,
    log_data: dict | None = None,
) -> SimpleNamespace:
    data = log_data or {"status": status, "samples": []}

    def model_dump(*, mode: str = "json") -> dict:
        assert mode == "json"
        return data

    return SimpleNamespace(
        status=status,
        location=location,
        error=error,
        model_dump=model_dump,
    )


def test_run_inspect_eval_returns_log_from_eval_location(monkeypatch, tmp_path):
    log_file = tmp_path / "logs" / "2026-06-13T12-00-00_lifi-quote.json"
    log_file.parent.mkdir(parents=True)
    log_file.write_bytes(b'{"status":"success","samples":[]}')
    expected_log_data = {"status": "success", "samples": [], "version": 2}

    captured: dict = {}

    def fake_eval(**kwargs):
        captured.update(kwargs)
        return [
            _eval_log_namespace(
                status="success",
                location=str(log_file),
                log_data=expected_log_data,
            ),
        ]

    monkeypatch.setattr(inspect_ai, "eval", fake_eval)

    repo_root = tmp_path
    (repo_root / "packages").mkdir()
    (repo_root / "pyproject.toml").write_text("[project]\nname = 'x'\n")

    log_path, log_data, raw = inspect_runner.run_inspect_eval(
        mcp="lifi",
        capability="quote",
        model="together/google/gemma-4-31B-it",
        repo_root=repo_root,
    )

    assert captured["display"] == "none"
    assert captured["model"] == "together/google/gemma-4-31B-it"
    assert captured["tasks"] == "lifi_quote"
    assert log_path == str(log_file)
    assert log_data == {"status": "success", "samples": []}
    assert raw == log_file.read_bytes()


def test_run_inspect_eval_falls_back_for_raw_bytes_when_location_missing(monkeypatch, tmp_path):
    repo_root = tmp_path
    (repo_root / "packages").mkdir()
    (repo_root / "pyproject.toml").write_text("[project]\nname = 'x'\n")
    log_file = repo_root / "logs" / "2026-06-13T12-00-00_lifi-quote.eval"
    log_file.parent.mkdir(parents=True)
    log_file.write_bytes(b'{"status":"success","samples":[]}')
    expected_log_data = {"status": "success", "samples": [{"id": "1"}]}

    monkeypatch.setattr(
        inspect_ai,
        "eval",
        lambda **kwargs: [
            _eval_log_namespace(status="success", location="", log_data=expected_log_data),
        ],
    )

    def fake_find(mcp, capability, *, repo_root):
        return str(log_file), {"status": "from_disk"}, log_file.read_bytes()

    monkeypatch.setattr(inspect_runner, "find_inspect_log_for_benchmark", fake_find)

    log_path, log_data, raw = inspect_runner.run_inspect_eval(
        mcp="lifi",
        capability="quote",
        model="openai/gpt-4o-mini",
        repo_root=repo_root,
    )
    assert log_path == str(log_file)
    assert log_data == expected_log_data
    assert raw == log_file.read_bytes()


def test_run_inspect_eval_raises_on_error_status(monkeypatch, tmp_path):
    repo_root = tmp_path
    (repo_root / "packages").mkdir()
    (repo_root / "pyproject.toml").write_text("[project]\nname = 'x'\n")

    monkeypatch.setattr(
        inspect_ai,
        "eval",
        lambda **kwargs: [
            _eval_log_namespace(
                status="error",
                error=SimpleNamespace(message="boom"),
            ),
        ],
    )

    with pytest.raises(RuntimeError, match="boom"):
        inspect_runner.run_inspect_eval(
            mcp="lifi",
            capability="quote",
            model="openai/gpt-4o-mini",
            repo_root=repo_root,
        )


@pytest.mark.parametrize("status", ["cancelled", "started", "unknown"])
def test_run_inspect_eval_raises_on_non_success_status(monkeypatch, tmp_path, status):
    repo_root = tmp_path
    (repo_root / "packages").mkdir()
    (repo_root / "pyproject.toml").write_text("[project]\nname = 'x'\n")

    monkeypatch.setattr(
        inspect_ai,
        "eval",
        lambda **kwargs: [_eval_log_namespace(status=status)],
    )

    with pytest.raises(RuntimeError, match=status):
        inspect_runner.run_inspect_eval(
            mcp="lifi",
            capability="quote",
            model="openai/gpt-4o-mini",
            repo_root=repo_root,
        )


def test_run_inspect_eval_passes_time_limit_to_eval(monkeypatch, tmp_path):
    """time_limit is forwarded to inspect_ai.eval; omitted when None/<=0."""
    log_file = tmp_path / "logs" / "2026-06-13T12-00-00_lifi-quote.json"
    log_file.parent.mkdir(parents=True)
    log_file.write_bytes(b'{"status":"success","samples":[]}')

    captured: dict = {}

    def fake_eval(**kwargs):
        captured.clear()
        captured.update(kwargs)
        return [_eval_log_namespace(status="success", location=str(log_file))]

    monkeypatch.setattr(inspect_ai, "eval", fake_eval)
    repo_root = tmp_path
    (repo_root / "packages").mkdir()
    (repo_root / "pyproject.toml").write_text("[project]\nname = 'x'\n")

    inspect_runner.run_inspect_eval(
        mcp="lifi", capability="quote", model="m", repo_root=repo_root, time_limit=150
    )
    assert captured["time_limit"] == 150

    inspect_runner.run_inspect_eval(
        mcp="lifi", capability="quote", model="m", repo_root=repo_root, time_limit=None
    )
    assert "time_limit" not in captured

    inspect_runner.run_inspect_eval(
        mcp="lifi", capability="quote", model="m", repo_root=repo_root, time_limit=0
    )
    assert "time_limit" not in captured


def test_main_prints_log_path_json(monkeypatch, tmp_path, capsys):
    """The subprocess CLI prints {"log_path": ...} JSON and returns 0."""
    import json

    monkeypatch.setattr(
        inspect_runner,
        "run_inspect_eval",
        lambda **kwargs: ("/tmp/x_lifi_quote.eval", {"status": "success"}, b"raw"),
    )
    rc = inspect_runner.main(
        ["--mcp", "lifi", "--capability", "quote", "--model", "m", "--repo-root", str(tmp_path)]
    )
    assert rc == 0
    out = capsys.readouterr().out.strip().splitlines()[-1]
    assert json.loads(out)["log_path"] == "/tmp/x_lifi_quote.eval"


def test_main_returns_nonzero_and_stderr_on_failure(monkeypatch, tmp_path, capsys):
    def boom(**kwargs):
        raise RuntimeError("inspect eval failed: kaboom")

    monkeypatch.setattr(inspect_runner, "run_inspect_eval", boom)
    rc = inspect_runner.main(
        ["--mcp", "lifi", "--capability", "quote", "--model", "m", "--repo-root", str(tmp_path)]
    )
    assert rc == 1
    assert "kaboom" in capsys.readouterr().err


def test_resolve_model_routing_anthropic_via_do_proxy():
    routing = inspect_runner.resolve_model_routing(
        "anthropic/anthropic-claude-haiku-4.5",
        anthropic_base_url="https://inference.do-ai.run",
        do_inference_key="do-key-123",
    )
    assert routing["model_base_url"] == "https://inference.do-ai.run"
    assert routing["model_args"] == {"api_key": "do-key-123"}


def test_resolve_model_routing_anthropic_without_do_creds_is_empty():
    # No DO creds → direct Anthropic key path (no extras).
    assert inspect_runner.resolve_model_routing(
        "anthropic/anthropic-claude-haiku-4.5",
        anthropic_base_url="",
        do_inference_key="",
    ) == {}


def test_resolve_model_routing_together_is_empty():
    assert inspect_runner.resolve_model_routing(
        "together/google/gemma-4-31B-it",
        anthropic_base_url="https://inference.do-ai.run",
        do_inference_key="do-key-123",
    ) == {}


def test_main_strips_leaked_anthropic_env_and_routes(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://inference.do-ai.run")
    monkeypatch.setenv("DO_INFERENCE_KEY", "do-key-123")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "leaked")
    monkeypatch.setenv("ANTHROPIC_DEFAULT_HAIKU_MODEL", "leaked-model")

    captured: dict = {}

    def fake_run(**kwargs):
        # Snapshot env + routing as the eval would see them.
        captured["routing"] = kwargs.get("routing")
        captured["env_after"] = {v: __import__("os").environ.get(v) for v in inspect_runner.LEAKABLE_ANTHROPIC_ENV}
        return ("/tmp/x.eval", {"status": "success"}, b"raw")

    monkeypatch.setattr(inspect_runner, "run_inspect_eval", fake_run)
    rc = inspect_runner.main(
        [
            "--mcp", "lifi", "--capability", "quote",
            "--model", "anthropic/anthropic-claude-haiku-4.5",
            "--repo-root", str(tmp_path),
        ]
    )
    assert rc == 0
    # Leaked ambient vars are stripped before the eval...
    assert all(v is None for v in captured["env_after"].values())
    # ...and routing still carries the captured DO proxy values.
    assert captured["routing"]["model_base_url"] == "https://inference.do-ai.run"
    assert captured["routing"]["model_args"] == {"api_key": "do-key-123"}
