"""File-like object that reads byte ranges over plain HTTPS (no credentials), with a block cache."""
import io
import urllib.request


class RangeFile(io.RawIOBase):
    def __init__(self, url, block=262144):
        self.url, self.block, self.pos, self.cache = url, block, 0, {}
        self.nreq, self.nbytes = 0, 0
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "python-urllib"})
        self.size = int(urllib.request.urlopen(req, timeout=120).headers["Content-Length"])

    def readable(self): return True
    def seekable(self): return True
    def tell(self): return self.pos

    def seek(self, off, whence=0):
        self.pos = off if whence == 0 else (self.pos + off if whence == 1 else self.size + off)
        return self.pos

    def _blk(self, i):
        if i not in self.cache:
            lo, hi = i * self.block, min((i + 1) * self.block, self.size) - 1
            req = urllib.request.Request(self.url, headers={"Range": f"bytes={lo}-{hi}", "User-Agent": "python-urllib"})
            for attempt in range(3):
                try:
                    data = urllib.request.urlopen(req, timeout=120).read()
                    break
                except Exception:
                    if attempt == 2:
                        raise
            self.cache[i] = data; self.nreq += 1; self.nbytes += len(data)
        return self.cache[i]

    def readinto(self, b):
        n = min(len(b), self.size - self.pos)
        if n <= 0:
            return 0
        out = bytearray()
        while len(out) < n:
            p = self.pos + len(out)
            blk = self._blk(p // self.block)
            o = p % self.block
            out += blk[o:o + n - len(out)]
        b[:n] = out; self.pos += n
        return n
