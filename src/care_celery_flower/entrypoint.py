"""Start Celery Flower for Care (DB/Redis readiness + flower process)."""

from __future__ import annotations

import logging
import os
import sys
import tempfile
import time
from pathlib import Path

logger = logging.getLogger("care_celery_flower")

MAX_RETRIES = 30
RETRY_DELAY_SECONDS = 1


def _wait_for_postgres() -> None:
    import psycopg

    user = os.environ["POSTGRES_USER"]
    password = os.environ["POSTGRES_PASSWORD"]
    host = os.environ["POSTGRES_HOST"]
    port = os.environ.get("POSTGRES_PORT", "5432")
    database = os.environ["POSTGRES_DB"]

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with psycopg.connect(
                user=user,
                password=password,
                host=host,
                port=port,
                dbname=database,
            ):
                pass
            logger.info("PostgreSQL is available")
            return
        except psycopg.OperationalError as exc:
            if attempt >= MAX_RETRIES:
                raise RuntimeError(
                    "Failed to connect to PostgreSQL after "
                    f"{MAX_RETRIES} attempts"
                ) from exc
            logger.info("Waiting for PostgreSQL to become available...")
            time.sleep(RETRY_DELAY_SECONDS)


def _wait_for_redis() -> None:
    import redis

    redis_url = os.environ["REDIS_URL"]
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            redis.Redis.from_url(redis_url).ping()
            logger.info("Redis is available")
            return
        except (redis.exceptions.ConnectionError, redis.exceptions.ResponseError) as exc:
            if attempt >= MAX_RETRIES:
                raise RuntimeError(
                    f"Failed to connect to Redis after {MAX_RETRIES} attempts"
                ) from exc
            logger.info("Waiting for Redis to become available...")
            time.sleep(RETRY_DELAY_SECONDS)


def _looks_like_care_home(path: Path) -> bool:
    return (path / "manage.py").is_file() and (path / "config").is_dir()


def _find_care_home() -> Path:
    candidates: list[Path] = []

    for env_key in ("APP_HOME", "CARE_HOME"):
        value = os.environ.get(env_key)
        if value:
            candidates.append(Path(value).expanduser())

    candidates.append(Path("/app"))
    candidates.append(Path.cwd())

    cwd = Path.cwd().resolve()
    candidates.extend(cwd.parents)

    for entry in sys.path:
        if entry:
            candidates.append(Path(entry))

    seen: set[Path] = set()
    for candidate in candidates:
        try:
            path = candidate.expanduser().resolve(strict=False)
        except OSError:
            continue
        if path in seen:
            continue
        seen.add(path)
        if _looks_like_care_home(path):
            return path

    raise RuntimeError(
        "Could not locate the Care project root (expected manage.py and config/). "
        "Set APP_HOME or CARE_HOME, or run start-flower from the Care directory."
    )


def _ensure_care_on_path() -> Path:
    """Console scripts may not start with Care on sys.path or as cwd."""
    care_home = _find_care_home()
    os.chdir(care_home)
    care_home_str = str(care_home)
    if care_home_str not in sys.path:
        sys.path.insert(0, care_home_str)
    return care_home


def _setup_django() -> None:
    _ensure_care_on_path()
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.deployment")
    import django

    django.setup()


def _write_runtime_markers() -> None:
    """Best-effort markers for Care image healthchecks (`/tmp`); no-op if unwritable."""
    for tmp in (Path("/tmp"), Path(tempfile.gettempdir())):
        try:
            (tmp / "healthy").write_text("true", encoding="utf-8")
            (tmp / "container-role").write_text("celery-beat", encoding="utf-8")
            return
        except OSError:
            continue


def _flower_argv() -> list[str]:
    from care_celery_flower.settings import plugin_settings

    args = [
        "celery",
        "--app=config.celery_app",
        "flower",
        f"--port={plugin_settings.FLOWER_PORT}",
        "--address=0.0.0.0",
    ]
    if plugin_settings.FLOWER_BASIC_AUTH:
        args.append(f"--basic-auth={plugin_settings.FLOWER_BASIC_AUTH}")
    if plugin_settings.FLOWER_URL_PREFIX:
        args.append(f"--url-prefix={plugin_settings.FLOWER_URL_PREFIX}")
    args.extend(sys.argv[1:])
    return args


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [INFO] [care_celery_flower] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    _write_runtime_markers()
    _wait_for_postgres()
    _wait_for_redis()
    _setup_django()

    args = _flower_argv()
    os.execvp(args[0], args)


if __name__ == "__main__":
    main()
