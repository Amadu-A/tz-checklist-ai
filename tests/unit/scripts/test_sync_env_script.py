# tests/unit/scripts/test_sync_env_script.py

import subprocess
from pathlib import Path


def test_sync_env_adds_missing_values_without_overwriting_secret(
    tmp_path: Path,
) -> None:
    """sync-env должен сохранять существующие секреты."""
    project_root = Path(
        __file__
    ).resolve().parents[3]

    script = (
        project_root
        / "scripts"
        / "sync-env.sh"
    )

    example = (
        tmp_path
        / ".env.example"
    )

    env_file = (
        tmp_path
        / ".env"
    )

    example.write_text(
        (
            "RABBITMQ_PASSWORD=change_me_before_use\n"
            "ANSWER_BATCH_SIZE=6\n"
            "NEW_SETTING=value\n"
        ),
        encoding="utf-8",
    )

    env_file.write_text(
        (
            "RABBITMQ_PASSWORD=real-secret\n"
            "ANSWER_BATCH_SIZE=10\n"
        ),
        encoding="utf-8",
    )

    subprocess.run(
        [
            "bash",
            str(script),
            str(example),
            str(env_file),
        ],
        check=True,
    )

    content = env_file.read_text(
        encoding="utf-8"
    )

    assert (
        "RABBITMQ_PASSWORD=real-secret"
        in content
    )

    assert (
        "ANSWER_BATCH_SIZE=10"
        in content
    )

    assert (
        "NEW_SETTING=value"
        in content
    )

    assert (
        "change_me_before_use"
        not in content
    )
