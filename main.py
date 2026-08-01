import argparse

from robot_sim.ui import RobotApp


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="小二桌面机器人控制与仿真系统")
    parser.add_argument("--demo", action="store_true", help="运行约1分钟自动演示")
    args = parser.parse_args()
    RobotApp(demo=args.demo).run()
