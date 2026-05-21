from app.config import Settings


def test_scheduler_state_list_normalizes_values() -> None:
    settings = Settings(scheduler_races_states=" sp, RJ ,,mg ")

    assert settings.scheduler_state_list == ["SP", "RJ", "MG"]
