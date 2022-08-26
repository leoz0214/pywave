"""
Utility functions for the package.
"""
import tempfile


def create_temp_file(data: bytes = None) -> tempfile._TemporaryFileWrapper:
    # Creates a temporary file, writes data to it,
    # and returns it to be accessed later. Must be closed later.
    file = tempfile.TemporaryFile()
    if data is not None:
        file.write(data)
        file.seek(0)
    return file