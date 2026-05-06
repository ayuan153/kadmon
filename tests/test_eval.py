from kadmon.eval.harness import EvalResult, EvalSummary, SWEBenchRunner


def test_eval_result_dataclass():
    r = EvalResult(instance_id='test-123', patch='diff', resolved=True, tokens_used=500)
    assert r.instance_id == 'test-123'
    assert r.patch == 'diff'
    assert r.resolved is True
    assert r.tokens_used == 500
    assert r.error == ''
    assert r.duration_seconds == 0


def test_eval_summary_resolve_rate():
    s = EvalSummary(total=10, resolved=3)
    assert s.resolve_rate == 0.3

    empty = EvalSummary(total=0, resolved=0)
    assert empty.resolve_rate == 0


def test_format_task():
    runner = SWEBenchRunner()
    instance = {
        'instance_id': 'repo__issue__1',
        'problem_statement': 'Something is broken',
        'hints_text': 'Check the config',
        'repo': 'org/repo',
        'base_commit': 'abc123',
    }
    task = runner._format_task(instance)
    assert 'Something is broken' in task
    assert 'Check the config' in task
