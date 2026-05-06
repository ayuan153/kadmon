from kadmon.agent.recovery import LoopDetector


def test_no_loop_with_varied_actions():
    ld = LoopDetector(threshold=3)
    assert not ld.record_action('read', {'path': 'a.py'})
    assert not ld.record_action('write', {'path': 'b.py'})
    assert not ld.record_action('read', {'path': 'c.py'})


def test_loop_detected_same_action():
    ld = LoopDetector(threshold=3)
    assert not ld.record_action('read', {'path': 'a.py'})
    assert not ld.record_action('read', {'path': 'a.py'})
    assert ld.record_action('read', {'path': 'a.py'})


def test_no_loop_same_tool_different_args():
    ld = LoopDetector(threshold=3)
    assert not ld.record_action('read', {'path': 'a.py'})
    assert not ld.record_action('read', {'path': 'b.py'})
    assert not ld.record_action('read', {'path': 'c.py'})


def test_error_loop_detected():
    ld = LoopDetector(threshold=3)
    assert not ld.record_error('FileNotFoundError: x.py')
    assert not ld.record_error('FileNotFoundError: x.py')
    assert ld.record_error('FileNotFoundError: x.py')


def test_no_error_loop_with_varied_errors():
    ld = LoopDetector(threshold=3)
    assert not ld.record_error('error A')
    assert not ld.record_error('error B')
    assert not ld.record_error('error C')


def test_reset_clears_state():
    ld = LoopDetector(threshold=3)
    ld.record_action('read', {'path': 'a.py'})
    ld.record_action('read', {'path': 'a.py'})
    ld.reset()
    # After reset, should not detect loop
    assert not ld.record_action('read', {'path': 'a.py'})


def test_recovery_message_not_empty():
    ld = LoopDetector()
    msg = ld.get_recovery_message()
    assert 'STOP' in msg
    assert 'different strategy' in msg
