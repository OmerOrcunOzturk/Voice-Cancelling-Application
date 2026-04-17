try:
    import sounddevice  # noqa: F401
except ImportError as exc:
    raise SystemExit(
        "sounddevice kurulu degil. Kurmak icin: pip install sounddevice numpy"
    ) from exc

try:
    import PySide6  # noqa: F401
except ImportError as exc:
    raise SystemExit(
        "PySide6 kurulu degil. Kurmak icin: .\\.venv\\Scripts\\pip.exe install PySide6"
    ) from exc

from filtre_app.app import main


if __name__ == "__main__":
    main()
