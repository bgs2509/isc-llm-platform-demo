#!/usr/bin/env python3
"""TCP relay: <listen host>:<listen port> -> 127.0.0.1:<target port>.

Why: the vLLM server qwen38-lil listens on the host loopback only (network mode host),
the kind cluster lives in the Docker network 172.23.0.0/16 and cannot reach host loopback.
The relay listens on the kind network gateway address and passes bytes both ways,
so streaming (server-sent events) works unchanged. No request content is read or stored.
Usage: model_forward.py 172.23.0.1 18310 127.0.0.1 18300
"""
import asyncio, sys

async def pump(reader, writer):
    try:
        while data := await reader.read(65536):
            writer.write(data)
            await writer.drain()
    except (ConnectionError, asyncio.CancelledError):
        pass
    finally:
        try:
            writer.close()
        except Exception:
            pass

async def handle(client_r, client_w, thost, tport):
    try:
        up_r, up_w = await asyncio.open_connection(thost, tport)
    except OSError:
        client_w.close()
        return
    await asyncio.gather(pump(client_r, up_w), pump(up_r, client_w))

async def main(lh, lp, th, tp):
    server = await asyncio.start_server(lambda r, w: handle(r, w, th, tp), lh, lp)
    async with server:
        await server.serve_forever()

if __name__ == "__main__":
    lh, lp, th, tp = sys.argv[1], int(sys.argv[2]), sys.argv[3], int(sys.argv[4])
    asyncio.run(main(lh, lp, th, tp))
