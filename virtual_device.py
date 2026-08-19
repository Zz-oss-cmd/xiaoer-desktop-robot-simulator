from __future__ import annotations

import argparse
import time
from dataclasses import replace

from robot_sim.config import VirtualDeviceConfig
from robot_sim.controller import RobotController
from robot_sim.tcp_transport import RobotTcpServer


def main() -> None:
    parser = argparse.ArgumentParser(description="小二机器人TCP虚拟设备")
    parser.add_argument("--config", help="JSON 配置文件路径")
    parser.add_argument("--host", help="监听地址（覆盖配置文件）")
    parser.add_argument("--port", type=int, help="监听端口（覆盖配置文件）")
    args = parser.parse_args()

    try:
        config = (
            VirtualDeviceConfig.load(args.config)
            if args.config
            else VirtualDeviceConfig()
        )
        overrides = {}
        if args.host is not None:
            overrides["host"] = args.host
        if args.port is not None:
            overrides["port"] = args.port
        if overrides:
            config = replace(config, **overrides)
    except ValueError as exc:
        parser.error(str(exc))

    controller = RobotController(
        lambda level, message: print(f"[{level}] {message}", flush=True),
        max_queue_size=config.max_queue_size,
    )
    with RobotTcpServer(
        controller,
        config.host,
        config.port,
        link_timeout_ms=config.link_timeout_ms,
        receive_size=config.receive_size,
        poll_interval_s=config.poll_interval_s,
        max_connections=config.max_connections,
    ) as server:
        host, port = server.address
        print(f"小二TCP虚拟设备已启动：{host}:{port}", flush=True)
        print("按 Ctrl+C 停止。", flush=True)
        try:
            while True:
                server.tick(0.1)
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\n正在停止虚拟设备……", flush=True)


if __name__ == "__main__":
    main()
