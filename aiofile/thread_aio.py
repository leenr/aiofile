import asyncio
import os
from collections import defaultdict
from threading import Lock


IO_READ = 0
IO_WRITE = 1
IO_NOP = 2


_LOCKS = defaultdict(Lock)


class ThreadedAIOOperation:
    __slots__ = ('__fd', '__offset', '__nbytes', '__reqprio', '__opcode',
                 '__buffer', '__loop', '__state', '__lock')

    def __init__(self, opcode: int, fd: int, offset: int, nbytes: int, reqprio: int,
                 loop: asyncio.AbstractEventLoop):

        if opcode not in (IO_READ, IO_WRITE, IO_NOP):
            raise ValueError('Invalid state')

        self.__loop = loop
        self.__fd = fd
        self.__offset = offset
        self.__nbytes = nbytes
        self.__reqprio = reqprio
        self.__opcode = opcode
        self.__buffer = b''
        self.__state = None
        self.__lock = _LOCKS[self.__fd]

    @property
    def buffer(self):
        return self.__buffer

    @buffer.setter
    def buffer(self, data: bytes):
        self.__buffer = data

    def _execute(self):
        with self.__lock:
            os.lseek(self.__fd, self.__offset, os.SEEK_SET)

            if self.opcode == IO_READ:
                return os.read(self.__fd, self.__nbytes)
            elif self.opcode == IO_WRITE:
                return os.write(self.__fd, self.__buffer)
            elif self.opcode == IO_NOP:
                return os.fsync(self.__fd)

            _LOCKS.pop(self.__fd)

    def __iter__(self):
        if self.__state is not None:
            raise RuntimeError('Invalid state')

        self.__state = False
        result = yield from self.__loop.run_in_executor(None, self._execute)
        self.__state = True
        return result

    def __await__(self):
        return self.__iter__()

    def done(self) -> bool:
        return self.__state is True

    def is_running(self) -> bool:
        return self.__state is False

    def close(self):
        pass

    @property
    def opcode(self):
        return self.__opcode

    @property
    def opcode_str(self):
        if self.opcode == IO_READ:
            return 'IO_READ'
        elif self.opcode == IO_WRITE:
            return 'IO_WRITE'
        elif self.opcode == IO_NOP:
            return 'IO_NOP'

    @property
    def fileno(self):
        return self.__fd

    @property
    def offset(self):
        return self.__offset

    @property
    def nbytes(self):
        return self.__nbytes

    @property
    def reqprio(self):
        return self.__reqprio

    def __repr__(self):
        return "<AIOThreadOperation[{!r}, fd={}, offset={}, nbytes={}, reqprio={}]>".format(
            self.opcode_str,
            self.fileno,
            self.offset,
            self.nbytes,
            self.reqprio,
        )