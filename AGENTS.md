# Repository Guidelines

## Project Structure & Module Organization
- `core/`: configuration and caching (`config_manager.py`, `cache_manager.py`).
- `services/`: high‑level orchestration (`story_video_service.py`).
- `content/`: script generation, scene splitting, prompts, theme extraction.
- `media/`: image/audio generation, cutout, WhisperX alignment.
- `video/`: subtitles, animations, compositing, final render.
- `utils/`: logging, file I/O, i18n, LLM client helpers.
- `tools/`: setup utilities (`load_env.py`, `validate_setup.py`, `configure_apis.py`).
- `config/`: `settings.json`, `themes/`, `prompts/` (do not hardcode secrets).
- `tests/`: unit and e2e helpers (`test_*.py`, `quick_video_test.py`, `end_to_end_test.py`).
- Outputs: `output/` (videos, subtitles, temp files under `output/temp`).

## Build, Test, and Development Commands
- Create env: `python -m venv .venv && source .venv/bin/activate`
- Install: `pip install -r requirements.txt`
- Validate setup: `python tools/validate_setup.py` (FFmpeg, keys, paths)
- Run locally: `python main.py --theme "明朝东厂与西厂的权力斗争" --language zh`
- Unit tests: `pytest -q` (discovers `test_*.py`)
- Quick smoke: `python tests/quick_video_test.py`
- E2E run: `python tests/end_to_end_test.py "标题" zh`

## Coding Style & Naming Conventions
- Follow PEP 8; 4‑space indents; add type hints for new/changed functions.
- Modules/functions: `snake_case`; classes: `CamelCase`; constants: `UPPER_SNAKE`.
- Keep side effects out of imports; use `if __name__ == "__main__":` for scripts.
- Use `utils.logger.setup_logging()` for logs; avoid prints in library code.
- File placement: business logic in `content/`, `media/`, `video/`; orchestration in `services/`.

## Testing Guidelines
- Frameworks: `pytest`, `pytest-asyncio` for async flows.
- Name tests `test_*.py` and functions `test_*`; keep them hermetic (no network) by stubbing service clients.
- Add unit tests for core processors (subtitle, scene split, compositing parameters).
- Before PR, run: `pytest -q` and `python tests/quick_video_test.py`. Use E2E for major changes.

## Commit & Pull Request Guidelines
- Commits: short, imperative summaries; optional emoji + scope, e.g. `🎬 video: fix subtitle timing`.
- PRs must include: purpose, linked issues, affected modules, config changes, and before/after media paths under `output/`.
- Checklist: tests pass, no secrets in diff, updated docs when behavior/config changes.

## Security & Configuration Tips
- Store keys in `.env` (see `.env.example`); never commit secrets. Load via `tools/load_env.py`.
- Validate environment with `python tools/validate_setup.py` after changes to `requirements.txt` or `config/`.
- Large artifacts stay in `output/`; do not track in Git.

