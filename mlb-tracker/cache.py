import json
import os
import tempfile
import config


def _path(filename):
    return os.path.join(config.CACHE_DIR, filename)


def _schedule_filename():
    return f"{_cache_prefix()}_schedule_{config.CURRENT_SEASON}.json"


def _summary_filename():
    return f"{_cache_prefix()}_summary.json"


def _cache_prefix():
    return config.TEAM_ABBR.lower()


def _legacy_dodgers_filename(filename):
    if config.TEAM_ID != 119:
        return None

    if filename == _schedule_filename():
        return f"dodgers_schedule_{config.CURRENT_SEASON}.json"

    if filename == _summary_filename():
        return "dodgers_summary.json"

    return None


def read_schedule():
    return _read(_schedule_filename())


def write_schedule(data):
    _write(_schedule_filename(), data)


def read_summary():
    return _read(_summary_filename())


def write_summary(data):
    _write(_summary_filename(), data)


def _read(filename):
    path = _path(filename)
    if not os.path.exists(path):
        legacy = _legacy_dodgers_filename(filename)
        if not legacy or legacy == filename:
            return None
        path = _path(legacy)
        if not os.path.exists(path):
            return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _write(filename, data):
    os.makedirs(config.CACHE_DIR, exist_ok=True)
    path = _path(filename)
    tmp_fd, tmp_path = tempfile.mkstemp(dir=config.CACHE_DIR, suffix=".tmp")
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
