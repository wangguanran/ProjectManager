from src.execution_textual import _format_execution_sub_title, _should_exit_on_enter


def test_success_subtitle_prompts_for_enter_when_confirmation_required():
    assert (
        _format_execution_sub_title("success", 1.23, awaiting_exit_confirmation=True)
        == "Completed in 1.23s; press Enter to exit"
    )


def test_success_subtitle_without_confirmation_keeps_plain_summary():
    assert _format_execution_sub_title("success", 1.23) == "Completed in 1.23s"


def test_failure_subtitle_remains_failure_summary():
    assert _format_execution_sub_title("failed", 1.23) == "Failed after 1.23s"


def test_enter_only_exits_after_successful_completion_is_acknowledged():
    assert _should_exit_on_enter(awaiting_exit_confirmation=True, worker_is_alive=False) is True
    assert _should_exit_on_enter(awaiting_exit_confirmation=True, worker_is_alive=True) is False
    assert _should_exit_on_enter(awaiting_exit_confirmation=False, worker_is_alive=False) is False
