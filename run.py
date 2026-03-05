"""Project entry point."""
import shutil
from app import create_app

# Try to activate static-ffmpeg if installed via pip
try:
    import static_ffmpeg
    static_ffmpeg.add_paths()
except ImportError:
    pass

application = create_app()

if __name__ == "__main__":
    if not shutil.which("ffmpeg"):
        print("\n⚠️  ffmpeg not found! Audio transcoding will be skipped.")
        print("   Install via pip:    pip install static-ffmpeg")
        print("   Or system package:")
        print("     macOS:   brew install ffmpeg")
        print("     Ubuntu:  sudo apt install ffmpeg")
        print("     Windows: choco install ffmpeg")
        print()
    application.run(debug=True, host="127.0.0.1", port=8080)
