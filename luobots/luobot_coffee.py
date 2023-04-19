#!/usr/bin/env python3

import os
import json
import rospy
from group_ctrl.srv import Cmd
import time


class Luobot:
    def __init__(self):
        rospy.init_node('Test')
        self.cmd = rospy.ServiceProxy('/core_command', Cmd)
        self.mapping = {"normal": "coffee", "specialty": "tetiaocoffee", "iced": "icecoffee"}

    def initialize(self, order_id=0, coffee_type='normal'):
        order_id %= 3
        coffee_type = self.mapping[coffee_type]
        order_id += 1
        data = {
            'cmd': 'show',
            'param': {
                'group': 1,
                'actionlist': 'begin',
                'noworder': coffee_type + str(order_id)
            }
        }
        rtn = self.cmd(json.dumps(data))
        result = json.loads(rtn.result)
        return result

    def pre_pouring_stage(self, order_id=0, coffee_type='normal'):
        order_id %= 3
        coffee_type = self.mapping[coffee_type]
        order_id += 1
        data = {
            'cmd': 'show',
            'param': {
                'group': 1,
                'actionlist': 'step201',
                'noworder': coffee_type + str(order_id)
            }
        }
        rtn = self.cmd(json.dumps(data))
        result = json.loads(rtn.result)
        return result

    def pouring_water(self, order_id=0, coffee_type='normal', method=None):
        order_id %= 3
        coffee_type = self.mapping[coffee_type]
        method = self.mapping[method] if method is not None else coffee_type
        order_id += 1
        data = {
            'cmd': 'show',
            'param': {
                'group': 1,
                'actionlist': 'step202',
                'noworder': method + str(order_id)
            }
        }
        rtn = self.cmd(json.dumps(data))
        result = json.loads(rtn.result)
        return result

    def serve_coffee(self, order_id=0, coffee_type='normal', method=None):
        order_id %= 3
        coffee_type = self.mapping[coffee_type]
        method = self.mapping[method] if method is not None else coffee_type
        order_id += 1
        data = {
            'cmd': 'show',
            'param': {
                'group': 1,
                'actionlist': 'step203',
                'noworder': method + str(order_id)
            }
        }
        rtn = self.cmd(json.dumps(data))
        result = json.loads(rtn.result)
        return result

    def wash_dripper_filter(self, order_id=0, coffee_type='normal'):
        order_id %= 3
        coffee_type = self.mapping[coffee_type]
        order_id += 1
        data = {
            'cmd': 'show',
            'param': {
                'group': 1,
                'actionlist': 'step204',
                'noworder': coffee_type + str(order_id)
            }
        }
        rtn = self.cmd(json.dumps(data))
        result = json.loads(rtn.result)
        return result


if __name__ == "__main__":
    robot = Luobot()
    print(robot.initialize())
    time.sleep(2)
    print(robot.pre_pouring_stage())
    time.sleep(2)
    print(robot.pouring_water())
    time.sleep(2)
    print(robot.serve_coffee())
    time.sleep(2)
    print(robot.wash_dripper_filter())
