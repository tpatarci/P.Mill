"""Automatic programming language detection for code analysis."""

import structlog
from pygments.lexers import get_lexer_by_name, guess_lexer
from pygments.util import ClassNotFound

logger = structlog.get_logger()

# Mapping from Pygments lexer names to normalized language names
LANGUAGE_MAPPING = {
    "python": "python",
    "python3": "python",
    "py": "python",
    "javascript": "javascript",
    "js": "javascript",
    "typescript": "typescript",
    "ts": "typescript",
    "go": "go",
    "rust": "rust",
    "java": "java",
    "c": "c",
    "cpp": "cpp",
    "c++": "cpp",
    "csharp": "csharp",
    "c#": "csharp",
    "ruby": "ruby",
    "php": "php",
    "swift": "swift",
    "kotlin": "kotlin",
    "scala": "scala",
    "r": "r",
    "sql": "sql",
    "shell": "shell",
    "bash": "shell",
    "powershell": "powershell",
}

# Supported languages for analysis (Phase 1: Python only)
SUPPORTED_LANGUAGES = {"python"}


class LanguageDetector:
    """Automatic programming language detection."""

    @staticmethod
    def detect(code: str, filename: str | None = None) -> str:
        """
        Detect the programming language of the given code.

        Args:
            code: Source code to analyze
            filename: Optional filename for extension-based detection

        Returns:
            Normalized language name (e.g., "python", "javascript")
            Returns "unknown" if detection fails
        """
        if not code or not code.strip():
            logger.warning("language_detection_empty_code")
            return "unknown"

        try:
            # Try filename-based detection first if available
            if filename:
                try:
                    lexer = get_lexer_by_name(filename.split(".")[-1])
                    detected = lexer.name.lower()
                    normalized = LANGUAGE_MAPPING.get(detected, detected)
                    logger.info(
                        "language_detected_by_filename",
                        filename=filename,
                        detected=detected,
                        normalized=normalized,
                    )
                    return normalized
                except ClassNotFound:
                    pass  # Fall through to content-based detection

            # Content-based detection using Pygments
            lexer = guess_lexer(code)
            detected = lexer.name.lower()
            normalized = LANGUAGE_MAPPING.get(detected, detected)

            logger.info(
                "language_detected_by_content",
                detected=detected,
                normalized=normalized,
                confidence="high" if normalized in SUPPORTED_LANGUAGES else "low",
            )

            return normalized

        except Exception as e:
            logger.error(
                "language_detection_failed",
                error=str(e),
                code_preview=code[:100],
            )
            return "unknown"

    @staticmethod
    def is_supported(language: str) -> bool:
        """
        Check if a language is supported for analysis.

        Args:
            language: Language name to check

        Returns:
            True if language is supported, False otherwise
        """
        return language in SUPPORTED_LANGUAGES

    @staticmethod
    def get_supported_languages() -> set[str]:
        """
        Get set of supported languages.

        Returns:
            Set of supported language names
        """
        return SUPPORTED_LANGUAGES.copy()


def detect_language(code: str, filename: str | None = None) -> str:
    """
    Convenience function for language detection.

    Args:
        code: Source code to analyze
        filename: Optional filename for extension-based detection

    Returns:
        Normalized language name or "unknown"
    """
    return LanguageDetector.detect(code, filename)
