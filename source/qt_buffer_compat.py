"""Compatibility helpers for Qt buffer wrappers across PySide versions."""


def buffer_slice(obj, size):
    """Return a `size`-limited bytes-like view for Qt buffers.

    Legacy wrappers expose `.asarray(size)`. Modern wrappers are usually
    compatible with `memoryview(...)` directly.
    """
    if hasattr(obj, "asarray"):
        return obj.asarray(size)

    view = obj if isinstance(obj, memoryview) else memoryview(obj)
    return view[:size]


def qimage_bits_to_bytes(img, total):
    """Extract raw bytes from ``img.bits()`` using version-compatible access."""
    return bytes(buffer_slice(img.bits(), total))

