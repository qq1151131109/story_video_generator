# GEMINI.md

## Project Overview

This project is a "Story Video Generator" that automatically creates short videos from a given theme or story title. It is a Python-based application with a modular architecture that leverages various AI services for content generation, media creation, and video composition.

The main technologies used are:

*   **Python**: The core programming language.
*   **FFmpeg**: For video processing and composition.
*   **AI Services**:
    *   **LLMs (Large Language Models)**: DeepSeek-V3, OpenRouter/GPT-4, and OpenRouter/Claude for script generation, scene splitting, and character analysis.
    *   **Image Generation**: Gemini 2.5 Flash, RunningHub, OpenAI DALL-E 3, and Stability AI for generating images for scenes and characters.
    *   **Audio Generation**: MiniMax, Azure TTS, ElevenLabs, and OpenAI TTS for text-to-speech conversion.
*   **Asyncio**: For concurrent and asynchronous processing of tasks.

The architecture is divided into three main pipelines:

1.  **Content Pipeline**: Generates the script, splits it into scenes, and analyzes the characters.
2.  **Media Pipeline**: Generates images and audio for each scene and character.
3.  **Video Pipeline**: Composes the final video by combining the generated media, adding subtitles and animations.

The project also includes features like a caching system to avoid redundant API calls, fault tolerance with multiple API providers, and detailed logging for monitoring and debugging.

## Building and Running

### Prerequisites

*   Python 3.8+
*   FFmpeg

### Installation

1.  Install the required Python packages:

    ```bash
    pip install -r requirements.txt
    ```

2.  Set up the environment variables by creating a `.env` file from the example:

    ```bash
    cp .env.example .env
    ```

    Then, edit the `.env` file to add your API keys.

### Running the Application

*   **Generate a single story:**

    ```bash
    python main.py --theme "The story of the Trojan War" --language en
    ```

*   **Batch generate stories from a text file:**

    ```bash
    python main.py --batch themes.txt --language en --concurrent 2
    ```

*   **Batch generate stories from a JSON file:**

    ```bash
    python main.py --json my_stories.json
    ```

*   **Run in test mode:**

    ```bash
    python main.py --test
    ```

*   **Run in interactive mode:**

    ```bash
    python main.py
    ```

### Testing

The project uses `pytest` for testing. To run the tests, you can use the following command:

```bash
pytest
```

## Development Conventions

*   **Coding Style**: The project follows the PEP 8 style guide for Python code.
*   **Asynchronous Programming**: The project extensively uses `asyncio` for concurrent operations. When adding new features, it is recommended to use `async/await` syntax for I/O-bound tasks.
*   **Modularity**: The codebase is organized into modules with specific responsibilities (e.g., `content`, `media`, `video`). New functionality should be added to the appropriate module.
*   **Configuration**: The project uses a `config/settings.json` file for configuration and a `.env` file for secrets. All configuration should be managed through the `ConfigManager` class.
*   **Logging**: The project uses the `loguru` library for logging. It is recommended to use the logger to record important events and errors.
*   **Internationalization (i18n)**: The project supports multiple languages. Text strings that are displayed to the user should be managed through the i18n system.

## Key Files

*   `main.py`: The entry point of the application, handling command-line arguments and orchestrating the video generation process.
*   `services/story_video_service.py`: The core service that encapsulates the main logic for generating story videos.
*   `config/settings.json`: The main configuration file for the application, defining settings for LLMs, media generation, and video processing.
*   `content/content_pipeline.py`: The pipeline for generating the story content, including the script, scenes, and characters.
*   `media/media_pipeline.py`: The pipeline for generating the media (images and audio) for the story.
*   `video/video_composer.py`: The module responsible for composing the final video using FFmpeg.
*   `requirements.txt`: A list of all the Python dependencies for the project.
*   `JSON_BATCH_FORMAT.md`: Documentation for the JSON format used for batch processing.
*   `INSTALL.md`: Installation instructions for the project.
*   `docs/WORKFLOW_DIAGRAM.md`: A detailed visual representation of the project's architecture and workflow.

## Workflow

The story video generation process is divided into three main stages, as detailed in the `docs/WORKFLOW_DIAGRAM.md` file:

1.  **Content Generation**:
    *   The `ContentPipeline` takes a theme, language, and style as input.
    *   It first checks the cache for existing content.
    *   If not found in the cache, it uses an LLM to generate a script.
    *   The script is then split into scenes, and the characters are analyzed.
    *   The generated content is stored in the cache for future use.

2.  **Media Generation**:
    *   The `MediaPipeline` receives the generated content (scenes and characters).
    *   It generates images for each scene and character using various image generation APIs.
    *   It also generates audio for each scene using text-to-speech APIs.
    *   The generated media is cached to avoid redundant API calls.

3.  **Video Composition**:
    *   The `VideoComposer` takes the generated media (images and audio) as input.
    *   It uses `SubtitleProcessor` to create subtitles and `AnimationProcessor` to add animations.
    *   Finally, it uses FFmpeg to combine everything into a single MP4 video file.
