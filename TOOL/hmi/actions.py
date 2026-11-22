"""阶段 3（S3-DEMO v2/v3）动作参数封装、上位机侧动作状态跟踪器与剧本编排引擎."""

from dataclasses import dataclass
import math
import time
from typing import List, Optional, Tuple

import protocol_ext as proto


@dataclass
class ScriptStep:
    action_id: int
    param: int
    label: str


@dataclass
class ActionTracker:
    state: str = "IDLE"  # IDLE / RUNNING / DONE / TIMEOUT / ABORTED
    action_id: int = 0
    param: int = 0
    label: str = "无动作"
    start_time: float = 0.0
    start_x_m: float = 0.0
    start_y_m: float = 0.0
    start_yaw_deg: float = 0.0
    progress_pct: float = 0.0
    detail_text: str = "就绪"
    seen_running_on_mcu: bool = False

    def start(
        self,
        action_id: int,
        param: int,
        label: str,
        tlm: Optional[proto.TelemetryExt] = None,
    ) -> None:
        self.action_id = action_id
        self.param = param
        self.label = label
        self.start_time = time.monotonic()
        self.seen_running_on_mcu = False
        if tlm is not None:
            self.start_x_m = tlm.x_m
            self.start_y_m = tlm.y_m
            self.start_yaw_deg = tlm.imu_yaw_deg if tlm.imu_ok else tlm.odom_yaw_deg
        else:
            self.start_x_m = 0.0
            self.start_y_m = 0.0
            self.start_yaw_deg = 0.0

        if (
            action_id in (proto.ACTION_STOP, proto.ACTION_RESET_ODOM)
            or (action_id in (proto.ACTION_MOVE_MM, proto.ACTION_TURN_01D) and param == 0)
        ):
            self.state = "DONE"
            self.progress_pct = 100.0
            self.detail_text = f"{label} -> 已完成"
        else:
            self.state = "RUNNING"
            self.progress_pct = 0.0
            self.detail_text = f"正在执行: {label}"

    def abort(self, reason: str = "被新指令或急停打断") -> Optional[str]:
        if self.state == "RUNNING":
            self.state = "ABORTED"
            self.detail_text = f"已打断 ({self.label}): {reason}"
            return self.detail_text
        return None

    def update_from_telemetry(self, tlm: proto.TelemetryExt) -> Optional[tuple]:
        """根据遥测更新进度与完成状态，返回状态变更日志 (level, msg) 或 None。"""
        if self.state != "RUNNING":
            return None

        elapsed = time.monotonic() - self.start_time
        if tlm.action_running:
            self.seen_running_on_mcu = True

        # 计算实时进度
        if self.action_id == proto.ACTION_MOVE_MM:
            target_m = max(abs(self.param) / 1000.0, 1e-3)
            dx = tlm.x_m - self.start_x_m
            dy = tlm.y_m - self.start_y_m
            dist_m = math.hypot(dx, dy)
            self.progress_pct = min(100.0, (dist_m / target_m) * 100.0)
            self.detail_text = (
                f"{self.label} | 已走 {dist_m*1000.0:.0f}/{abs(self.param)} mm "
                f"({self.progress_pct:.0f}%, {elapsed:.1f}s)"
            )
        elif self.action_id in (proto.ACTION_TURN_01D, proto.ACTION_UTURN_180):
            target_deg = 180.0 if self.action_id == proto.ACTION_UTURN_180 else max(abs(self.param) * 0.1, 0.1)
            cur_yaw = tlm.imu_yaw_deg if tlm.imu_ok else tlm.odom_yaw_deg
            dyaw = (cur_yaw - self.start_yaw_deg + 180.0) % 360.0 - 180.0
            self.progress_pct = min(100.0, (abs(dyaw) / target_deg) * 100.0)
            self.detail_text = (
                f"{self.label} | 已转 {dyaw:+.1f}° / 目标 {(180.0 if self.action_id == proto.ACTION_UTURN_180 else self.param*0.1):+.1f}° "
                f"({self.progress_pct:.0f}%, {elapsed:.1f}s)"
            )

        # 检查 STM32 报告的完成或超时标志
        if tlm.action_timeout or elapsed > 10.5:
            self.state = "TIMEOUT"
            self.detail_text = f"动作超时停车 (>10s): {self.label}"
            return ("ERR", self.detail_text)

        if tlm.action_done or (self.seen_running_on_mcu and not tlm.action_running and elapsed > 0.25):
            self.state = "DONE"
            self.progress_pct = 100.0
            self.detail_text = f"动作到位完成: {self.label} (耗时 {elapsed:.2f}s)"
            return ("OK", self.detail_text)

        if tlm.timed_out:
            self.state = "ABORTED"
            self.detail_text = f"400ms 通信超时强停，动作中止: {self.label}"
            return ("WARN", self.detail_text)

        return None


class ActionScriptSequencer:
    """S3-DEMO v3 动作剧本编排器（队列增删、预设剧本、双步点对点导航、收到 DONE 停顿 0.3s 发下一步、两层打断）。"""

    def __init__(self, settle_delay_s: float = 0.30) -> None:
        self.steps: List[ScriptStep] = []
        self.active: bool = False
        self.current_index: int = -1
        self.script_name: str = "自定义队列"
        self.settle_delay_s: float = settle_delay_s
        self._waiting_settle: bool = False
        self._settle_deadline: float = 0.0

    def load_steps(self, steps: List[ScriptStep], name: str = "自定义队列") -> None:
        self.steps = list(steps)
        self.script_name = name
        self.active = False
        self.current_index = -1
        self._waiting_settle = False

    def add_step(self, action_id: int, param: int, label: str) -> None:
        self.steps.append(ScriptStep(action_id=action_id, param=param, label=label))

    def remove_step(self, index: int) -> None:
        if 0 <= index < len(self.steps) and not self.active:
            del self.steps[index]

    def clear(self) -> bool:
        """清空队列并中止编排（返回此前是否处于激活状态）。"""
        was_active = self.active
        self.steps.clear()
        self.active = False
        self.current_index = -1
        self._waiting_settle = False
        return was_active

    def abort_running(self) -> bool:
        """停止正在执行的剧本并清空剩余待发队列（纠正 3：上位机侧第一层打断）。"""
        was_active = self.active
        self.active = False
        self.current_index = -1
        self._waiting_settle = False
        self.steps.clear()
        return was_active

    def start_sequence(self) -> Optional[Tuple[int, int, ScriptStep]]:
        """启动队列，返回第一步 (index, total, step) 或 None。"""
        if not self.steps:
            self.active = False
            return None
        self.active = True
        self.current_index = 0
        self._waiting_settle = False
        return (0, len(self.steps), self.steps[0])

    def notify_step_done(self, now_s: Optional[float] = None) -> Optional[str]:
        """当 tracker 检测到当前步 DONE 时调用，进入 0.3s 停稳等待或宣告全部完成。"""
        if not self.active:
            return None
        t_now = time.monotonic() if now_s is None else now_s
        if self.current_index + 1 >= len(self.steps):
            self.active = False
            done_name = self.script_name
            total = len(self.steps)
            self.current_index = -1
            self._waiting_settle = False
            return f"🎉 剧本『{done_name}』全部 {total} 步执行完成！"
        self._waiting_settle = True
        self._settle_deadline = t_now + self.settle_delay_s
        return None

    def poll_next_step(self, now_s: Optional[float] = None) -> Optional[Tuple[int, int, ScriptStep]]:
        """在定时器或遥测回调中轮询：若 0.3s 停稳时间到，返回下一步 (index, total, step)。"""
        if not self.active or not self._waiting_settle:
            return None
        t_now = time.monotonic() if now_s is None else now_s
        if t_now >= self._settle_deadline:
            self._waiting_settle = False
            self.current_index += 1
            if 0 <= self.current_index < len(self.steps):
                return (self.current_index, len(self.steps), self.steps[self.current_index])
            self.active = False
            self.current_index = -1
        return None


def make_move_payload(dist_mm: int) -> tuple:
    clamped = max(-30000, min(30000, int(dist_mm)))
    direction = "前进" if clamped >= 0 else "后退"
    label = f"{direction} {abs(clamped)} mm"
    return proto.ACTION_MOVE_MM, clamped, proto.pack_cmd_action(proto.ACTION_MOVE_MM, clamped), label


def make_turn_payload(angle_deg: float) -> tuple:
    param_01d = max(-3600, min(3600, int(round(angle_deg * 10.0))))
    direction = "左转(CCW)" if param_01d >= 0 else "右转(CW)"
    label = f"{direction} {abs(param_01d)*0.1:.1f}°"
    return proto.ACTION_TURN_01D, param_01d, proto.pack_cmd_action(proto.ACTION_TURN_01D, param_01d), label


def make_stop_action_payload() -> tuple:
    return proto.ACTION_STOP, 0, proto.pack_cmd_action(proto.ACTION_STOP, 0), "动作停车(0x03)"


def make_uturn_payload() -> tuple:
    return proto.ACTION_UTURN_180, 1800, proto.pack_cmd_action(proto.ACTION_UTURN_180, 1800), "掉头 180°(0x04)"


def make_reset_odom_payload() -> tuple:
    return proto.ACTION_RESET_ODOM, 0, proto.pack_cmd_action(proto.ACTION_RESET_ODOM, 0), "里程计归零(0x06)"


def get_preset_script(preset_key: str) -> Tuple[str, List[ScriptStep]]:
    """返回三大花式预设剧本：(剧本名称, 步骤列表)。"""
    if preset_key == "square":
        steps = []
        for i in range(4):
            steps.append(ScriptStep(proto.ACTION_MOVE_MM, 1000, f"[边{i+1}] 前进 1000 mm"))
            steps.append(ScriptStep(proto.ACTION_TURN_01D, 900, f"[角{i+1}] 左转(CCW) 90.0°"))
        return ("正方形巡逻 (1m×4)", steps)
    if preset_key == "shuttle":
        return (
            "2m 折返跑",
            [
                ScriptStep(proto.ACTION_MOVE_MM, 2000, "[去程] 前进 2000 mm"),
                ScriptStep(proto.ACTION_UTURN_180, 1800, "[折返] 掉头 180°"),
                ScriptStep(proto.ACTION_MOVE_MM, 2000, "[回程] 前进 2000 mm"),
                ScriptStep(proto.ACTION_UTURN_180, 1800, "[归位] 掉头 180°"),
            ],
        )
    if preset_key == "dance":
        return (
            "左右摇摆舞",
            [
                ScriptStep(proto.ACTION_TURN_01D, 300, "[舞步1] 左转(CCW) 30.0°"),
                ScriptStep(proto.ACTION_TURN_01D, -600, "[舞步2] 右转(CW) 60.0°"),
                ScriptStep(proto.ACTION_TURN_01D, 600, "[舞步3] 左转(CCW) 60.0°"),
                ScriptStep(proto.ACTION_TURN_01D, -300, "[舞步4] 右转(CW) 30.0°"),
            ],
        )
    return ("空剧本", [])


def build_point_nav_steps(
    cur_x_m: float,
    cur_y_m: float,
    cur_yaw_deg: float,
    target_x_m: float,
    target_y_m: float,
) -> Tuple[List[ScriptStep], float, int]:
    """构建双击地图指点导航两步串行动作：先转向对准 -> 再直行到达（演示级导航，落点误差约 5cm 量级）。"""
    dx = target_x_m - cur_x_m
    dy = target_y_m - cur_y_m
    dist_m = math.hypot(dx, dy)
    dist_mm = max(0, min(15000, int(round(dist_m * 1000.0))))

    if dist_mm < 20:
        return ([], 0.0, dist_mm)

    target_yaw_deg = math.degrees(math.atan2(dy, dx))
    dyaw_deg = (target_yaw_deg - cur_yaw_deg + 180.0) % 360.0 - 180.0
    turn_01d = int(round(dyaw_deg * 10.0))

    steps: List[ScriptStep] = []
    if abs(turn_01d) >= 10:  # >= 1.0° 才执行转向步
        dir_str = "左转(CCW)" if turn_01d >= 0 else "右转(CW)"
        steps.append(
            ScriptStep(
                proto.ACTION_TURN_01D,
                turn_01d,
                f"[指点导航-1] {dir_str} {abs(turn_01d)*0.1:.1f}° 对准目标",
            )
        )
    steps.append(
        ScriptStep(
            proto.ACTION_MOVE_MM,
            dist_mm,
            f"[指点导航-2] 直行 {dist_mm} mm 到 ({target_x_m:+.2f}, {target_y_m:+.2f})m",
        )
    )
    return (steps, dyaw_deg, dist_mm)
