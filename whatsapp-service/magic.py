# Fake magic module to avoid libmagic dependency in sandbox
# Provides from_buffer with mime detection via simple header checks

def from_buffer(data, mime=False):
    if not data:
        return "application/octet-stream" if mime else "data"
    # Simple mime detection
    if data[:8] == b'\x89PNG\r\n\x1a\n':
        return "image/png" if mime else "PNG image"
    if data[:2] == b'\xff\xd8':
        return "image/jpeg" if mime else "JPEG image"
    if data[:6] in (b'GIF87a', b'GIF89a'):
        return "image/gif" if mime else "GIF image"
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        return "image/webp" if mime else "WEBP image"
    if data[:4] == b'\x00\x00\x00\x18' or data[4:8] == b'ftyp':
        return "video/mp4" if mime else "MP4 video"
    # Default
    return "application/octet-stream" if mime else "data"

def from_file(filename, mime=False):
    try:
        with open(filename, 'rb') as f:
            return from_buffer(f.read(1024), mime=mime)
    except:
        return "application/octet-stream" if mime else "data"
