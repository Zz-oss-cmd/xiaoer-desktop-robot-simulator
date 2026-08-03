from __future__ import annotations

import argparse
import socket
import struct
import time

from robot_sim.gateway import decode_status_frame
from robot_sim.protocol import Command, ProtocolFrame, StreamParser, encode_frame


def receive_status_frames(connection: socket.socket, expected: int) -> list[ProtocolFrame]:
    parser = StreamParser()
    frames: list[ProtocolFrame] = []
    deadline = time.monotonic() + 2.0
    while len(frames) < expected and time.monotonic() < deadline:
        data = connection.recv(512)
        if not data:
            break
        frames.extend(parser.feed(data, time.monotonic_ns() // 1_000_000))
    return frames


def main() -> None:
    parser = argparse.ArgumentParser(description="小二TCP协议联调客户端")
    parser.add_argument("--host", default="127.0.0.1", help="虚拟设备地址")
    parser.add_argument("--port", type=int, default=8765, help="虚拟设备端口")
    args = parser.parse_args()

    heartbeat = encode_frame(ProtocolFrame(Command.HEARTBEAT, 1))
    sensor_payload = struct.pack("<HHhH", 385, 826, 274, 650)
    sensor = encode_frame(ProtocolFrame(Command.SENSOR_DATA, 2, sensor_payload))
    patrol = encode_frame(ProtocolFrame(Command.CONTROL, 3, b"\x02"))

    with socket.create_connection((args.host, args.port), timeout=2.0) as connection:
        connection.settimeout(2.0)
        connection.sendall(heartbeat[:4])
        connection.sendall(heartbeat[4:] + sensor + patrol)
        responses = receive_status_frames(connection, 3)

    print(f"已发送3帧，收到{len(responses)}帧设备状态响应。")
    for frame in responses:
        status = decode_status_frame(frame)
        print(
            f"  序号={frame.sequence}，状态={status.state.value}，"
            f"电量={status.battery_pct:.1f}%，温度={status.temperature_c:.1f}℃，"
            f"队列={status.queue_size}"
        )
    if len(responses) != 3:
        raise SystemExit("联调失败：设备状态响应数量不正确。")
    print("TCP协议联调成功。")


if __name__ == "__main__":
    main()
