import multiprocessing
import os
import sys
import traceback
from multiprocessing.connection import Connection
from luobots.luobot_coffee import Luobot
import signal
import re
import requests
import json
import time
from typing import Optional
from jose import jwt
from datetime import datetime, timedelta

SECRET_KEY = "dc393487a84ddf9da61fe0180ef230cf0642ecbc5d678a1589ef2e26b35fce9c"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 8

def remove_dupe(inst_list):
    unique_items = {}
    result = []
    for item in inst_list:
        if item not in unique_items:
            unique_items[item] = True
            result.append(item)
    return result

instruction_list = [
    "initialize",
    "pre_pouring_stage",
    "pouring_water",
    "serve_coffee",
    "wash_dripper_filter"
]


def inst_validation(inst):
    '''
    判断单条python指令是否合法
    args:
        inst: api返回的单条python指令
    return:
        idx: 指令合法，给出流程内id，None: 指令不合法
    '''
    for idx, prefix in enumerate(instruction_list):
        if prefix in inst:
            return idx
    return None

def system_thread(conn_main: Connection, conn_exec: Connection):
    current_order = None
    last_finished = None
    order_list = None
    last_exec_idx = None
    luobot_done = True
    luobot_vacant = True
    stop_sign = False
    last_command = None
    closing = False
    def system_gen():
        # print(self.current_type)
        current_order_list = None
        if current_order is not None:
            assert order_list is not None
            current_type = None
            border_idx = 4
            list_str = "订单队列："
            current_order_list = []
            for order_idx, order in enumerate(order_list):
                if int(order[0]) == int(current_order):
                    current_type = order[1]
                    list_str += f"[{order[0]}，{order[1]}]，"
                    border_idx = order_idx
                    current_order_list.append(order)
                elif order_idx > border_idx:
                    list_str += f"[{order[0]}，{order[1]}]，"
                    current_order_list.append(order)
            ret_msg = list_str[:-1] + "\n"
            ret_msg += f"当前订单id：{current_order}；"
            assert current_type is not None
            ret_msg += f"当前订单咖啡类型：{current_type}；"
            assert last_exec_idx is not None
            idx = last_exec_idx + 1
            ret_msg += f"当前订单剩余流程："
            for i in range(idx, len(instruction_list)):
                ret_msg += (instruction_list[i] + "，")
            ret_msg = ret_msg[:-1]
        else:
            ret_msg = f"订单队列：无\n当前订单id：无；当前订单咖啡类型：无；当前订单剩余流程：无"
        return ret_msg, current_order_list
    while True:
        if closing:
            if luobot_vacant:
                conn_exec.send([1])
                if conn_exec.recv() == "closed":
                    print("\nLuobot executor closed.")
                    conn_main.send(True)
                    break
        if conn_main.poll(0.1) and not closing:
            data = conn_main.recv()
            # print("conn main recv: ", data)
            if data[0] == 1:
                system_info, order_list = system_gen()
                print("system info:", system_info)
                conn_main.send(system_info)
                stop_sign = True
                if luobot_done:
                    conn_main.send(True)
                    stop_sign = False
            elif data[0] == 0:
                stop_sign = False
                luobot_done = False
                command = data[1]
                pattern_2 = r"# 订单(\d+)[:：]\s*(.*?)\n"
                order_list = re.findall(pattern_2, command)
                order_list = remove_dupe(order_list)
                # if len(new_inst_order_list) > 3:
                #     conn_main.send(False)
                #     conn_exec.send([0, "user", last_command])
                # else:
                conn_main.send(True)
                print("\nuser inst:", command)
                conn_exec.send([0, "user", command])
                luobot_vacant = False
            elif data[0] == 2:  # close
                print("\nClosing luobot system...")
                closing = True
        if conn_exec.poll(0.1):
            data = conn_exec.recv()
            if data[0] == 0:
                if data[1] == "loop":
                    last_exec_idx = data[2]
                    last_finished = data[3]
                    current_order = data[4]
                    luobot_done = False
                    luobot_vacant = False
                elif data[1] == "done":
                    print("\nLast instruction done.")
                    last_finished = None
                    last_exec_idx = None
                    current_order = None
                    luobot_done = True
                    luobot_vacant = True
                    if stop_sign:
                        conn_main.send(True)
                        stop_sign = False
                elif data[1] == "break":
                    last_command = data[2]
                    luobot_vacant = True
                    conn_main.send(True)
                elif data[1] == "continue?":
                    if stop_sign or closing:
                        conn_exec.send(False)
                        stop_sign = False
                    else:
                        conn_exec.send(True)
            elif data[0] == 1:
                error_msg = data[1]
                if not closing:
                    system_info, order_list = system_gen()
                    conn_main.send([1, error_msg, system_info])
                else:
                    luobot_vacant = True




def luobot_executor(conn_system: Connection, actor_type) -> None:
    '''
    机器人服务所在进程
    args:
        conn: 与主进程通信的管道
    return:
        None
    '''
    robot = Luobot()
    # pid = os.getpid()
    last_exec_idx = None
    last_finished = None
    current_order = None
    while True:
        data = conn_system.recv()
        assert isinstance(data, list)
        if data[0] == 0:  # 所收到的信息为机器人指令
            try:
                assert data[1] == "user"
                inst = data[2]  # 提取指令
                inst_list = inst.split("\n")  # 按行分割指令
                break_flag = False  # 指令执行是否被主进程中断
                tmp = []
                for instruction in inst_list:
                    if len(instruction) != 0:
                        tmp.append(instruction)
                inst_list = tmp
                for inst_idx, instruction in enumerate(inst_list):
                    conn_system.send([0, "continue?"])  # 询问主进程是否执行
                    exec_flag = conn_system.recv()
                    if exec_flag:
                        idx = inst_validation(instruction)
                        assert idx is not None
                        if idx == 0 or idx == 4:
                            match = re.search(r'\((\d+)\)', instruction)
                        else:
                            match = re.search(r'\((\d+), ', instruction)
                        if match:
                            current_order = match.group(1)  # 更新当前订单id
                            if idx == 4:
                                last_finished = current_order  # 更新上一个订单id
                                if inst_idx + 1 == len(inst_list):
                                    current_order = None
                                    last_finished = None
                                    last_exec_idx = None
                                else:
                                    match = re.search(r'\((\d+)\)', inst_list[inst_idx + 1])
                                    if match:
                                        current_order = match.group(1)  # 寻找下一个订单id
                                        last_exec_idx = -1
                            else:
                                last_exec_idx = idx
                        conn_system.send([0, "loop", last_exec_idx, last_finished, current_order])
                        # time.sleep(10)
                        with open("/home/orion/catkin_ws/src/CheetahEnableDrink/config/orderlist.yaml", "r") as f:
                            content = f.read()
                            content_list = content.split("\n")
                        order_list_len_before = len(content_list)
                        print(f"\nexecuting: {instruction}")
                        exec(instruction)
                        while True:
                            with open("/home/orion/catkin_ws/src/CheetahEnableDrink/config/orderlist.yaml", "r") as f:
                                content = f.read()
                                content_list = content.split("\n")
                            current_len = len(content_list)
                            if current_len > order_list_len_before:
                                break
                    else:
                        print("\nexec_flag: ", exec_flag)
                        left_commands = [inst_list[i] for i in range(inst_idx, len(inst_list))]
                        command_left = "\n".join(left_commands)
                        break_flag = True
                        break
                if not break_flag:
                    conn_system.send([0, "done"])
                    last_finished = None
                    current_order = None
                    last_exec_idx = None
                else:
                    conn_system.send([0, "break", command_left])
            except Exception as e:
                tb = traceback.format_exc()
                error_msg = f"Exception: {e}\n{tb}"
                print(error_msg)
                conn_system.send([1, error_msg])
        elif data[0] == 1:  # closing
            print("\nClosing luobot executor...")
            conn_system.send("closed")
            break


def listen_to_user(conn: Connection):
    '''
    监听用户输入的进程
    args:
        conn: 与主进程通信的管道
    '''
    sys.stdin = os.fdopen(0, "r")  # 打开标准输入流
    sys.stdout = os.fdopen(1, "w")  # 打开标准输出流
    pid = os.getpid()
    while True:
        # print("user listener receiving")
        if conn.poll(0.1):
            data = conn.recv()
            if data:
                break
        else:
            user_msg = input("User：")
            if len(user_msg) == 0:  # 跳过空指令
                continue
            # print(f"user listener sending: {user_msg}")
            conn.send(user_msg)


def access_token(
    data: dict,
    expires_minutes: Optional[int] = None):
    """
    """
    to_encode = data.copy()
    if expires_minutes:
        expire = datetime.utcnow() + timedelta(minutes=expires_minutes)
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


class LuobotActor:
    def __init__(self, robot_id=0):
        self.robot_id = robot_id
        user_conn_main, user_conn_sub = multiprocessing.Pipe()
        sys_conn_main, sys_conn_sub = multiprocessing.Pipe()
        inter_conn_main, inter_conn_sub = multiprocessing.Pipe()
        self.user_conn_main = user_conn_main
        self.user_conn_sub = user_conn_sub
        self.sys_conn_main = sys_conn_main
        self.sys_conn_sub = sys_conn_sub
        self.inter_conn_main = inter_conn_main
        self.inter_conn_sub = inter_conn_sub
        self.luobot_process = multiprocessing.Process(target=luobot_executor, args=(inter_conn_main, robot_id))  # 机器人服务进程
        self.user_listener = multiprocessing.Process(target=listen_to_user, args=(user_conn_sub,))  # 用户输入监听进程
        self.system_process = multiprocessing.Process(target=system_thread, args=(sys_conn_sub, inter_conn_sub))  # 系统服务进程
        self.luobot_process.start()
        self.user_listener.start()
        self.system_process.start()

    def api_call(self, context, reset_history):
        # url = "http://127.0.0.1:8000/robot"
        url = "http://124.71.161.146:8001/robot"
        payload = json.dumps({
            "context": context,
            "reset_history": reset_history,
            "robot_id": self.robot_id,
        })
        token = access_token({'sub': 'syy'})
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'bearer {token}',
        }
        response = requests.request("POST", url, headers=headers, data=payload)
        rsp_data = response.json()
        if rsp_data["status"] == 200:
            is_code = True
            content = rsp_data["result"]["msg"]
            robot_id = rsp_data["result"]["robot_id"]
        elif rsp_data["status"] == 400:
            is_code = False
            content = rsp_data["message"]
            robot_id = self.robot_id
        else:
            return "未知错误", False, self.robot_id
        return content, is_code, robot_id

    # def response_process(self, user_inst="", reset_history=False):
    def get_response(self, user_inst="", system_info="", reset_history=False):
        '''
        user_inst: 用户输入的指令
        return: user_inst, luobot_done
        指令样例如下：
        """
        订单队列：<0，普通咖啡>，<1, 特调冲泡的冰咖>
        ```
        robot.pre_pouring_stage(order_id=0, coffee_type='normal') # 订单0: 普通咖啡
        robot.pouring_water(order_id=0, coffee_type='normal')
        robot.serve_coffee(order_id=0, coffee_type='normal')
        robot.wash_dripper_filter(order_id=0) # 订单0: 普通咖啡
        robot.initialize(order_id=1) # 订单1：特调冲泡的冰咖
        robot.pre_pouring_stage(order_id=1, coffee_type='iced')
        robot.pouring_water(order_id=1, coffee_type='specialty')
        robot.serve_coffee(order_id=1, coffee_type='specialty')
        robot.wash_dripper_filter(order_id=1) # 订单1: 特调冲泡的冰咖
        ```"""
        '''
        context = [{"role": "user", "content": user_inst}, {"role": "user", "content": system_info}]
        content, is_command, robot_id = self.api_call(context, reset_history)  # 调用后端接口获取指令
        assert robot_id == self.robot_id
        return is_command, content

    def run(self) -> None:
        '''
        主服务进程，管理两个子进程：机器人进程和用户监听进程
        '''
        while True:
            if self.user_conn_main.poll(0.1):
                user_inst = self.user_conn_main.recv()
                if user_inst == "exit":
                    self.close()
                    break
                elif user_inst == "reset history":
                    # print("\nResetting history")
                    is_command, content = self.get_response(reset_history=True)
                else:
                    self.sys_conn_main.send([1])
                    system_info = self.sys_conn_main.recv()
                    is_command, content = self.get_response(user_inst, system_info)
                    stop_success = self.sys_conn_main.recv()
                    if stop_success:
                        if is_command:
                            self.sys_conn_main.send([0, content])
                            command_accepted = self.sys_conn_main.recv()
                            if not command_accepted:
                                print("\nError: 指令未被接受。")
                            else:
                                print("\n指令已被接受。执行中。")
                        else:
                            print("\nError: ", content)
            if self.sys_conn_main.poll(0.1):
                data = self.sys_conn_main.recv()
                # print("sys conn main recv: ", data)
                assert data[0] != 0
                if data[0] == 1:
                    error_msg = data[1]
                    system_info = data[2]
                    print("\nError: ", error_msg)
                    is_command, content = self.get_response(error_msg, system_info)
                    if is_command:
                        self.sys_conn_main.send([0, content])
                    else:
                        print("\nError: ", content)

    def close(self) -> None:
        self.sys_conn_main.send([2])
        sys_sig = self.sys_conn_main.recv()
        if sys_sig:
            print("\nLuobot system closed.")
        self.user_conn_main.send(1)
        os.kill(self.user_listener.pid, signal.SIGTERM)
        self.luobot_process.join()
        self.system_process.join()
        self.user_listener.join()
        print("\nLuobot actor closed")