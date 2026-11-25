"""Minimal reader for HDF5 datasets stored with the Blosc2 filter (id 32026),
LZ4 codec, using only numpy and pyarrow. Scratch tool for inspection."""
import struct
import numpy as np
import pyarrow as pa

_lz4 = pa.Codec("lz4_raw")


def _bitunshuffle(buf, ts):
    a = np.frombuffer(buf, np.uint8)
    n = len(a) // ts
    n8 = n - n % 8
    out = a.copy()
    if n8:
        rows = a[: n8 * ts].reshape(ts, 8, n8 // 8)
        bits = np.unpackbits(rows, axis=-1, bitorder="little")
        by = np.packbits(bits.transpose(2, 0, 1), axis=-1, bitorder="little")
        out[: n8 * ts] = by.reshape(-1)
    return out.tobytes()


def _unshuffle(buf, ts):
    a = np.frombuffer(buf, np.uint8)
    n = len(a) // ts
    out = a.copy()
    out[: n * ts] = a[: n * ts].reshape(ts, n).T.reshape(-1)
    return out.tobytes()


def decode_chunk(c, info=None):
    flags, ts = c[2], c[3]
    nbytes, blocksize, cbytes = struct.unpack_from("<III", c, 4)
    ext = bool(flags & 0x1) and bool(flags & 0x4)
    hdr = 32 if ext else 16
    filters = list(c[16:22]) if ext else [1 if flags & 0x1 else (2 if flags & 0x4 else 0)]
    b2flags = c[31] if ext else 0
    special = (b2flags >> 4) & 0x7
    codec = (flags >> 5) & 0x7
    if info is not None:
        info.update(flags=flags, ts=ts, nbytes=nbytes, blocksize=blocksize, cbytes=cbytes,
                    ext=ext, filters=filters, special=special, codec=codec,
                    dont_split=bool(flags & 0x10), memcpyed=bool(flags & 0x2))
    if special == 1:
        return bytes(nbytes)
    if special == 2:
        dt = np.float64 if ts == 8 else np.float32
        return np.full(nbytes // ts, np.nan, dt).tobytes()
    if special == 3:
        return (c[hdr:hdr + ts] * (nbytes // ts))
    if flags & 0x2:
        return bytes(c[hdr:hdr + nbytes])
    if codec != 1:
        raise NotImplementedError(f"codec {codec}")
    nblocks = -(-nbytes // blocksize)
    bstarts = struct.unpack_from(f"<{nblocks}i", c, hdr)
    out = bytearray()
    for j in range(nblocks):
        bsize = min(blocksize, nbytes - j * blocksize)
        leftover = bsize != blocksize
        nstreams = ts if (not (flags & 0x10) and not leftover) else 1
        ne = bsize // nstreams
        pos = bstarts[j]
        blk = bytearray()
        for _ in range(nstreams):
            (cs,) = struct.unpack_from("<i", c, pos)
            pos += 4
            if cs == 0:
                blk += bytes(ne)
            elif cs < 0:
                token = c[pos]; pos += 1
                if not token & 0x1:
                    raise ValueError("unsupported run token")
                blk += bytes([(-cs) & 0xFF]) * ne
            elif cs == ne:
                blk += c[pos:pos + ne]; pos += ne
            else:
                blk += _lz4.decompress(bytes(c[pos:pos + cs]), decompressed_size=ne).to_pybytes(); pos += cs
        b = bytes(blk)
        for fcode in reversed(filters):
            if fcode == 1:
                b = _unshuffle(b, ts)
            elif fcode == 2:
                b = _bitunshuffle(b, ts)
            elif fcode not in (0,):
                raise NotImplementedError(f"filter {fcode}")
        out += b
    return bytes(out)


def _decode_frame(raw, itemsize, info=None):
    """Decode a Blosc2 contiguous frame (possibly many chunks) into bytes."""
    hsize = int.from_bytes(raw[11:15], "big")
    usize = int.from_bytes(raw[30:38], "big")
    csize = int.from_bytes(raw[39:47], "big")
    chunksize = int.from_bytes(raw[58:62], "big")
    nchunks = -(-usize // chunksize) if chunksize else 0
    offs = np.frombuffer(decode_chunk(raw[hsize + csize:]), "<i8")[:nchunks]
    if info is not None:
        info.update(frame=True, frame_nchunks=nchunks, frame_usize=usize, frame_chunksize=chunksize)
    out = []
    for k, off in enumerate(offs):
        n = min(chunksize, usize - k * chunksize)
        if off < 0:
            kind = (int(off) >> 56) & 0x7
            if info is not None:
                info["special_frame"] = kind
            if kind == 1:
                out.append(bytes(n))
            elif kind == 2:
                out.append(np.full(n // itemsize, np.nan, f"<f{itemsize}").tobytes())
            else:
                raise NotImplementedError(f"special frame chunk kind {kind}")
        else:
            b = decode_chunk(raw[hsize + int(off):], info)
            if len(b) != n:
                raise ValueError(f"chunk {k}: decoded {len(b)} bytes, expected {n}")
            out.append(b)
    return b"".join(out)


def read_dataset(ds, info=None):
    """Read a 1-d h5py dataset stored with the Blosc2 filter, chunk by chunk."""
    parts = []
    nchunk = ds.id.get_num_chunks()
    for i in range(nchunk):
        ci = ds.id.get_chunk_info(i)
        _, raw = ds.id.read_direct_chunk(ci.chunk_offset)
        raw = bytes(raw)
        if raw[1:9] == b"\xa8b2frame":
            parts.append(_decode_frame(raw, ds.dtype.itemsize, info))
        else:
            parts.append(decode_chunk(raw, info))
    if info is not None:
        info["h5_chunks"] = nchunk
    return np.frombuffer(b"".join(parts), ds.dtype)[: ds.size].reshape(ds.shape)


def read_rows(ds, lo, hi):
    """Read rows [lo, hi) of a 1-d Blosc2-filtered dataset, touching only the HDF5 chunks that overlap."""
    csz = ds.chunks[0]
    out = []
    for k in range(lo // csz, min(-(-hi // csz), -(-ds.shape[0] // csz))):
        _, raw = ds.id.read_direct_chunk((k * csz,))
        raw = bytes(raw)
        b = _decode_frame(raw, ds.dtype.itemsize) if raw[1:9] == b"\xa8b2frame" else decode_chunk(raw)
        n = min(csz, ds.shape[0] - k * csz)
        a = np.frombuffer(b, ds.dtype)[:n]
        out.append(a[max(lo - k * csz, 0): max(min(hi - k * csz, n), 0)])
    return np.concatenate(out) if out else np.empty(0, ds.dtype)
