from trezorutils import (  # noqa: F401
    BITCOIN_ONLY,
    EMULATOR,
    GITREV,
    MODEL,
    VERSION_MAJOR,
    VERSION_MINOR,
    VERSION_PATCH,
    consteq,
    halt,
    memcpy,
)

import gc
import sys

DISABLE_ANIMATION = 0

if __debug__:
    if EMULATOR:
        import uos

        DISABLE_ANIMATION = int(uos.getenv("TREZOR_DISABLE_ANIMATION") or "0")
        LOG_MEMORY = int(uos.getenv("TREZOR_LOG_MEMORY") or "0")
    else:
        LOG_MEMORY = 0

if False:
    from typing import (
        Any,
        Iterable,
        Iterator,
        Optional,
        Protocol,
        Sequence,
        TypeVar,
        Union,
    )


def unimport_begin() -> Iterable[str]:
    return set(sys.modules)


def unimport_end(mods: Iterable[str]) -> None:
    for mod in sys.modules:
        if mod not in mods:
            # remove reference from sys.modules
            del sys.modules[mod]
            # remove reference from the parent module
            i = mod.rfind(".")
            if i < 0:
                continue
            path = mod[:i]
            name = mod[i + 1 :]
            try:
                delattr(sys.modules[path], name)
            except KeyError:
                # either path is not present in sys.modules, or module is not
                # referenced from the parent package. both is fine.
                pass
    # collect removed modules
    gc.collect()


def ensure(cond: bool, msg: str = None) -> None:
    if not cond:
        if msg is None:
            raise AssertionError
        else:
            raise AssertionError(msg)


if False:
    Chunkable = TypeVar("Chunkable", str, Sequence[Any])


def chunks(items: Chunkable, size: int) -> Iterator[Chunkable]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


if False:

    class HashContext(Protocol):
        def update(self, buf: bytes) -> None:
            ...

        def digest(self) -> bytes:
            ...

    class Writer(Protocol):
        def append(self, b: int) -> None:
            ...

        def extend(self, buf: bytes) -> None:
            ...


class HashWriter:
    def __init__(self, ctx: HashContext) -> None:
        self.ctx = ctx
        self.buf = bytearray(1)  # used in append()

    def append(self, b: int) -> None:
        self.buf[0] = b
        self.ctx.update(self.buf)

    def extend(self, buf: bytes) -> None:
        self.ctx.update(buf)

    def write(self, buf: bytes) -> None:  # alias for extend()
        self.ctx.update(buf)

    async def awrite(self, buf: bytes) -> int:  # AsyncWriter interface
        self.ctx.update(buf)
        return len(buf)

    def get_digest(self) -> bytes:
        return self.ctx.digest()


if False:
    BufferType = Union[bytearray, memoryview]


class BufferWriter:
    """Seekable and writeable view into a buffer."""

    def __init__(self, buffer: BufferType) -> None:
        self.buffer = buffer
        self.offset = 0

    def seek(self, offset: int) -> None:
        """Set current offset to `offset`.

        If negative, set to zero. If longer than the buffer, set to end of buffer.
        """
        offset = min(offset, len(self.buffer))
        offset = max(offset, 0)
        self.offset = offset

    def write(self, src: bytes) -> int:
        """Write exactly `len(src)` bytes into buffer, or raise EOFError.

        Returns number of bytes written.
        """
        buffer = self.buffer
        offset = self.offset
        if len(src) > len(buffer) - offset:
            raise EOFError
        nwrite = memcpy(buffer, offset, src, 0)
        self.offset += nwrite
        return nwrite


class BufferReader:
    """Seekable and readable view into a buffer."""

    def __init__(self, buffer: bytes) -> None:
        self.buffer = buffer
        self.offset = 0

    def seek(self, offset: int) -> None:
        """Set current offset to `offset`.

        If negative, set to zero. If longer than the buffer, set to end of buffer.
        """
        offset = min(offset, len(self.buffer))
        offset = max(offset, 0)
        self.offset = offset

    def readinto(self, dst: BufferType) -> int:
        """Read exactly `len(dst)` bytes into `dst`, or raise EOFError.

        Returns number of bytes read.
        """
        buffer = self.buffer
        offset = self.offset
        if len(dst) > len(buffer) - offset:
            raise EOFError
        nread = memcpy(dst, 0, buffer, offset)
        self.offset += nread
        return nread

    def read(self, length: Optional[int] = None) -> bytes:
        """Read and return exactly `length` bytes, or raise EOFError.

        If `length` is unspecified, reads all remaining data.

        Note that this method makes a copy of the data. To avoid allocation, use
        `readinto()`.
        """
        if length is None:
            ret = self.buffer[self.offset :]
            self.offset = len(self.buffer)
        elif length < 0:
            raise ValueError
        elif length <= self.remaining_count():
            ret = self.buffer[self.offset : self.offset + length]
            self.offset += length
        else:
            raise EOFError
        return ret

    def remaining_count(self) -> int:
        """Return the number of bytes remaining for reading."""
        return len(self.buffer) - self.offset

    def peek(self) -> int:
        """Peek the ordinal value of the next byte to be read."""
        if self.offset >= len(self.buffer):
            raise EOFError
        return self.buffer[self.offset]

    def get(self) -> int:
        """Read exactly one byte and return its ordinal value."""
        if self.offset >= len(self.buffer):
            raise EOFError
        byte = self.buffer[self.offset]
        self.offset += 1
        return byte


def obj_eq(l: object, r: object) -> bool:
    """
    Compares object contents, supports __slots__.
    """
    if l.__class__ is not r.__class__:
        return False
    if not hasattr(l, "__slots__"):
        return l.__dict__ == r.__dict__
    if l.__slots__ is not r.__slots__:
        return False
    for slot in l.__slots__:
        if getattr(l, slot, None) != getattr(r, slot, None):
            return False
    return True


def obj_repr(o: object) -> str:
    """
    Returns a string representation of object, supports __slots__.
    """
    if hasattr(o, "__slots__"):
        d = {attr: getattr(o, attr, None) for attr in o.__slots__}
    else:
        d = o.__dict__
    return "<%s: %s>" % (o.__class__.__name__, d)


def truncate_utf8(string: str, max_bytes: int) -> str:
    """Truncate the codepoints of a string so that its UTF-8 encoding is at most `max_bytes` in length."""
    data = string.encode()
    if len(data) <= max_bytes:
        return string

    # Find the starting position of the last codepoint in data[0 : max_bytes + 1].
    i = max_bytes
    while i >= 0 and data[i] & 0xC0 == 0x80:
        i -= 1

    return data[:i].decode()


def is_empty_iterator(i: Iterator) -> bool:
    try:
        next(i)
    except StopIteration:
        return True
    else:
        return False