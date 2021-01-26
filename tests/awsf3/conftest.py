import sys
import io


upload_test_bucket = 'tibanna-output'


class CaptureOut:
    """Context manager for capturing stdout, since capsys somehow didn't work"""
    def __init__(self):
        pass

    def get_captured_out(self):
        return self.captured_stdout.getvalue()

    def __enter__(self):
        self.old_stdout = sys.stdout
        self.captured_stdout = io.StringIO()
        sys.stdout = self.captured_stdout

    def __exit__(self, type, value, tb):
        sys.stdout = self.old_stdout
