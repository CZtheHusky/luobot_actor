from luobot_actor import LuobotActor
from argparse import ArgumentParser

parser = ArgumentParser()
parser.add_argument('--robot-id', default=0, type=int)

if __name__ == "__main__":
    args = parser.parse_args()
    actor = LuobotActor(robot_id=args.robot_id)  # robot_id对应不同的机器人
    actor.run()
