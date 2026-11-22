"""阶段 3（S3-DEMO v2/v3）QThread 半双工串口通信线程与车端闭环仿真器（含梯形加减速与 0x06 里程计归零）."""

from datetime import datetime
import math
import queue
import struct
import time
from typing import Optional

try:
    from PySide6.QtCore import QThread, Signal
except ImportError:
    from PyQt6.QtCore import QThread, pyqtSignal as Signal  # type: ignore

import serial
import serial.tools.list_ports

import protocol_ext as proto


def list_serial_ports() -> list:
    ports = [p.device for p in serial.tools.list_ports.comports()]
    if not ports:
        return ["COM6", "COM3"]
    return ports


class MockStm32Simulator:
    """内置 STM32 车端闭环仿真器（完全复现 S3-DEMO v3 协议、梯形加减速、0x06 归零与单一司机状态机）。"""

    def __init__(self) -> None:
        self.x_m = 0.0
        self.y_m = 0.0
        self.imu_yaw_deg = 0.0
        self.odom_yaw_deg = 0.0
        self.vx = 0.0
        self.omega = 0.0
        self.fusion_mode = 1
        self.drop_count = 0
        self.timeout_count = 0
        self.last_seq: Optional[int] = None
        self.last_t = time.monotonic()

        # 动作状态机: IDLE=0, RUNNING=1, DONE=2, TIMEOUT=3, ABORTED=4
        self.act_state = 0
        self.act_id = 0
        self.act_param = 0
        self.act_start_t = 0.0
        self.act_elapsed_s = 0.0
        self.act_start_x = 0.0
        self.act_start_y = 0.0
        self.act_start_yaw = 0.0
        self.act_target_yaw = 0.0

    def _abort_action(self) -> None:
        if self.act_state == 1:
            self.vx = 0.0
            self.omega = 0.0
            self.act_state = 4
        elif self.act_state != 4:
            self.act_state = 0
        self.act_id = 0

    def _force_stop(self) -> None:
        self._abort_action()
        self.vx = 0.0
        self.omega = 0.0

    @staticmethod
    def _compute_trapezoid_speed(elapsed_s: float, rem_mm: float, target_mm: float) -> float:
        """与 STM32 comm_actions.c 严格对齐的直行梯形速度规划（含 <400mm 短距离保护）。"""
        v_start = 0.08
        v_cruise = 0.25
        v_crawl = 0.07
        ramp_ms = 250.0
        slow_mm = 150.0

        if target_mm < 400.0:
            if v_cruise > 0.14:
                v_cruise = 0.14
            if ramp_ms > 100.0:
                ramp_ms = 100.0
            half_mm = 0.5 * target_mm
            if slow_mm > half_mm:
                slow_mm = half_mm

        elapsed_ms = elapsed_s * 1000.0
        if elapsed_ms < ramp_ms:
            ratio_up = max(0.0, min(1.0, elapsed_ms / ramp_ms))
            v_ramp = v_start + (v_cruise - v_start) * ratio_up
        else:
            v_ramp = v_cruise

        if slow_mm > 1.0 and rem_mm < slow_mm:
            ratio_down = max(0.0, min(1.0, rem_mm / slow_mm))
            v_decel = v_crawl + (v_cruise - v_crawl) * ratio_down
        else:
            v_decel = v_cruise

        v_cmd = min(v_ramp, v_decel)
        return max(v_crawl, min(v_cruise, v_cmd))

    def step_physics(self) -> None:
        now = time.monotonic()
        dt = min(max(now - self.last_t, 0.001), 0.25)
        self.last_t = now

        if (
            (now - self.act_start_t) > 0.40
            and self.last_seq is not None
            and (now - getattr(self, "_last_rx_t", now)) > 0.40
        ):
            if not getattr(self, "_timed_out_latched", False):
                self._timed_out_latched = True
                self.timeout_count += 1
                self._force_stop()

        if self.act_state == 1:
            self.act_elapsed_s += dt
            elapsed = self.act_elapsed_s
            if elapsed >= 10.0:
                self._force_stop()
                self.act_state = 3
            elif self.act_id == proto.ACTION_MOVE_MM:
                target_mm = float(abs(self.act_param))
                dist_mm = math.hypot(self.x_m - self.act_start_x, self.y_m - self.act_start_y) * 1000.0
                if dist_mm >= target_mm:
                    self._force_stop()
                    self.act_state = 2
                else:
                    rem_mm = max(0.0, target_mm - dist_mm)
                    spd = self._compute_trapezoid_speed(elapsed, rem_mm, target_mm)
                    self.vx = spd if self.act_param > 0 else -spd
                    self.omega = 0.0
            elif self.act_id in (proto.ACTION_TURN_01D, proto.ACTION_UTURN_180):
                err = (self.act_target_yaw - self.imu_yaw_deg + 180.0) % 360.0 - 180.0
                if abs(err) <= 0.46:
                    self._force_stop()
                    self.act_state = 2
                else:
                    w = max(-1.0, min(1.0, (err * math.pi / 180.0) * 1.4))
                    if abs(w) < 0.08:
                        w = 0.08 if err > 0 else -0.08
                    self.omega = w
                    self.vx = 0.0

        yaw_rad = math.radians(self.imu_yaw_deg)
        self.x_m += self.vx * math.cos(yaw_rad) * dt
        self.y_m += self.vx * math.sin(yaw_rad) * dt
        dyaw_deg = math.degrees(self.omega * dt)
        self.imu_yaw_deg = (self.imu_yaw_deg + dyaw_deg + 180.0) % 360.0 - 180.0
        self.odom_yaw_deg = (
            self.imu_yaw_deg
            if self.fusion_mode == 1
            else (self.odom_yaw_deg + dyaw_deg * 0.96 + 180.0) % 360.0 - 180.0
        )

    def handle_frame(self, raw: bytes) -> Optional[bytes]:
        self.step_physics()
        parsed = proto.parse_frame_ext(raw)
        if parsed is None:
            return None

        self._last_rx_t = time.monotonic()
        self._timed_out_latched = False

        if self.last_seq is not None:
            delta = (parsed.seq - self.last_seq) & 0xFF
            if delta > 1:
                self.drop_count = min(65535, self.drop_count + delta - 1)
        self.last_seq = parsed.seq

        mtype = parsed.msg_type
        if mtype == proto.TYPE_CMD_STOP:
            self._force_stop()
        elif mtype != proto.TYPE_CMD_POLL:
            # ★ 单一司机规则：非 POLL 指令先 Abort 当前动作
            self._abort_action()
            if mtype == proto.TYPE_CMD_VEL and len(parsed.data) == 4:
                vx_mm, w_mrad = struct.unpack("<hh", parsed.data)
                self.vx = vx_mm / 1000.0
                self.omega = w_mrad / 1000.0
            elif mtype == proto.TYPE_CMD_MODE and len(parsed.data) == 1:
                self.fusion_mode = 1 if parsed.data[0] else 0
            elif mtype == proto.TYPE_CMD_ACTION and len(parsed.data) == 3:
                aid, param = proto.unpack_cmd_action(parsed.data)
                if aid == proto.ACTION_RESET_ODOM:
                    # W2: 0x06 里程计归零
                    self._force_stop()
                    self.x_m = 0.0
                    self.y_m = 0.0
                    self.imu_yaw_deg = 0.0
                    self.odom_yaw_deg = 0.0
                    self.act_id = aid
                    self.act_param = 0
                    self.act_state = 2
                elif aid == proto.ACTION_STOP or (
                    aid in (proto.ACTION_MOVE_MM, proto.ACTION_TURN_01D) and param == 0
                ):
                    self._force_stop()
                    self.act_id = aid
                    self.act_param = 0
                    self.act_state = 2
                elif aid == proto.ACTION_MOVE_MM:
                    self.act_id = aid
                    self.act_param = param
                    self.act_start_t = time.monotonic()
                    self.act_elapsed_s = 0.0
                    self.act_start_x = self.x_m
                    self.act_start_y = self.y_m
                    self.vx = 0.08 if param > 0 else -0.08
                    self.omega = 0.0
                    self.act_state = 1
                elif aid in (proto.ACTION_TURN_01D, proto.ACTION_UTURN_180):
                    eff = 1800 if aid == proto.ACTION_UTURN_180 else param
                    self.act_id = aid
                    self.act_param = eff
                    self.act_start_t = time.monotonic()
                    self.act_elapsed_s = 0.0
                    self.act_start_yaw = self.imu_yaw_deg
                    self.act_target_yaw = (self.imu_yaw_deg + eff * 0.1 + 180.0) % 360.0 - 180.0
                    self.act_state = 1

        left_mps = self.vx - self.omega * 0.3703 * 0.5
        right_mps = self.vx + self.omega * 0.3703 * 0.5
        l_rpm = int(round(left_mps * 287.6))
        r_rpm = int(round(right_mps * 287.6))
        l_pwm = max(-100, min(100, int(round(l_rpm / 3.2))))
        r_pwm = max(-100, min(100, int(round(r_rpm / 3.2))))

        status = (
            0x01
            | (0x04 if self.act_state == 1 else 0x00)
            | (0x10 if self.act_state == 1 else 0x00)
            | (0x20 if self.act_state == 2 else 0x00)
            | (0x40 if self.act_state == 3 else 0x00)
        )
        tlm_payload = struct.pack(
            "<4h4b4h2B2H",
            l_rpm, r_rpm, l_rpm, r_rpm,
            l_pwm, r_pwm, l_pwm, r_pwm,
            max(-32768, min(32767, int(round(self.x_m * 1000.0)))),
            max(-32768, min(32767, int(round(self.y_m * 1000.0)))),
            max(-32768, min(32767, int(round(self.odom_yaw_deg * 100.0)))),
            max(-32768, min(32767, int(round(self.imu_yaw_deg * 100.0)))),
            status,
            self.fusion_mode,
            self.drop_count,
            self.timeout_count,
        )
        return proto.build_frame_ext(proto.TYPE_TELEMETRY, parsed.seq, tlm_payload)


class SerialLinkWorker(QThread):
    """后台半双工串口收发线程：严格遵守发一帧 -> 等回帧 -> 下一周期，绝不阻塞 GUI 主线程。"""

    sig_telemetry = Signal(object, dict)             # (TelemetryExt, stats_dict)
    sig_raw_frame = Signal(str, str, bytes, str, bool)  # (dir, time_str, raw_bytes, breakdown, is_manual)
    sig_log = Signal(str, str)                       # (level, message)
    sig_link_state = Signal(bool, str)               # (connected, description)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.port_name = "COM6"
        self.baudrate = 9600
        self.read_timeout_s = 0.26
        self.period_s = 0.05
        self.use_mock = False

        self._running = False
        self._cmd_queue: "queue.Queue[tuple]" = queue.Queue()
        self._active_mode = "POLL"
        self._hold_vx = 0.0
        self._hold_omega = 0.0
        self._pause_until = 0.0

    def configure(self, port_name: str, baudrate: int = 9600, use_mock: bool = False) -> None:
        self.port_name = port_name
        self.baudrate = baudrate
        self.use_mock = use_mock

    def stop_link(self) -> None:
        self._running = False

    def enqueue_stop(self, reason: str = "用户触发急停 (CMD_STOP)") -> None:
        """最高优先级：清空待发队列，立即下发 CMD_STOP 并切回 POLL。"""
        self._active_mode = "POLL"
        self._hold_vx = 0.0
        self._hold_omega = 0.0
        while not self._cmd_queue.empty():
            try:
                self._cmd_queue.get_nowait()
            except queue.Empty:
                break
        self._cmd_queue.put((proto.TYPE_CMD_STOP, b"", None, True, reason))

    def enqueue_action(self, action_id: int, param: int, label: str) -> None:
        """下发参数化动作 CMD_ACTION(0x05)，随后自动以 CMD_POLL 维持 400ms 心跳。"""
        self._active_mode = "POLL"
        self._hold_vx = 0.0
        self._hold_omega = 0.0
        payload = proto.pack_cmd_action(action_id, param)
        self._cmd_queue.put(
            (proto.TYPE_CMD_ACTION, payload, None, True, f"下发动作 CMD_ACTION: {label} (id=0x{action_id:02X}, param={param})")
        )

    def enqueue_velocity(self, vx_mps: float, omega_rads: float, silent: bool = False) -> None:
        """下发速度指令 CMD_VEL(0x02) 并保持速度心跳（若 vx=0 且 omega=0 则发送一帧零速后恢复 POLL）。"""
        self._hold_vx = vx_mps
        self._hold_omega = omega_rads
        if abs(vx_mps) < 1e-4 and abs(omega_rads) < 1e-4:
            self._active_mode = "POLL"
        else:
            self._active_mode = f"VEL({vx_mps:+.2f},{omega_rads:+.2f})"
        payload = proto.pack_cmd_vel(vx_mps, omega_rads)
        log_msg = (
            ""
            if silent
            else f"下发速度 CMD_VEL: vx={vx_mps:+.2f} m/s, ω={omega_rads:+.2f} rad/s"
        )
        self._cmd_queue.put(
            (proto.TYPE_CMD_VEL, payload, None, not silent, log_msg)
        )

    def enqueue_mode(self, fusion_mode: int) -> None:
        """下发融合模式切换 CMD_MODE(0x04)（按单一司机规则打断当前动作）。"""
        self._active_mode = "POLL"
        self._hold_vx = 0.0
        self._hold_omega = 0.0
        payload = proto.pack_cmd_mode(fusion_mode)
        m_str = "IMU主融合(1)" if fusion_mode else "纯编码器(0)"
        self._cmd_queue.put(
            (proto.TYPE_CMD_MODE, payload, None, True, f"下发模式 CMD_MODE: {m_str}")
        )

    def enqueue_raw_frame(self, msg_type: int, seq_override: Optional[int], data: bytes) -> None:
        """从原始帧工具页发送自定义帧。"""
        self._cmd_queue.put(
            (
                msg_type,
                bytes(data),
                seq_override,
                True,
                f"[原始帧工具] 发送 TYPE=0x{msg_type:02X} DATA={data.hex(' ').upper() if data else '(空)'}",
            )
        )

    def trigger_timeout_test(self, pause_s: float = 0.80) -> None:
        """暂停发帧 0.80s 以测试 STM32 400ms 通信超时强制停车。"""
        self._active_mode = "POLL"
        self._hold_vx = 0.0
        self._hold_omega = 0.0
        self._pause_until = time.monotonic() + pause_s
        self.sig_log.emit("WARN", f"暂停发帧 {pause_s:.2f}s，测试 STM32 400ms 断连超时停车...")

    def run(self) -> None:
        self._running = True
        ser: Optional[serial.Serial] = None
        mock_sim = MockStm32Simulator() if self.use_mock else None

        if self.use_mock:
            self.sig_link_state.emit(True, "MOCK 仿真车端")
            self.sig_log.emit("OK", "已启动内置 STM32 车端闭环仿真器 (Mock Mode v3: 支持梯形加减速与 0x06 归零)")
        else:
            try:
                ser = serial.Serial(
                    port=self.port_name,
                    baudrate=self.baudrate,
                    bytesize=serial.EIGHTBITS,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE,
                    timeout=0.02,
                    write_timeout=0.5,
                    rtscts=False,
                    dsrdtr=False,
                )
                ser.reset_input_buffer()
                self.sig_link_state.emit(True, f"{self.port_name} @ {self.baudrate}")
                self.sig_log.emit("OK", f"串口已连接: {self.port_name} @ {self.baudrate} 8N1")
            except Exception as exc:
                self.sig_link_state.emit(False, f"{self.port_name} 打开失败")
                self.sig_log.emit("ERR", f"串口打开失败 ({self.port_name}): {exc}")
                self._running = False
                return

        seq = 0
        stats = {
            "tx": 0,
            "rx": 0,
            "local_timeout": 0,
            "rtt_ms": 0.0,
            "avg_rtt_ms": 0.0,
            "rtt_sum_ms": 0.0,
            "hz": 0.0,
            "loss_pct": 0.0,
            "mode": "POLL",
            "t_start": time.monotonic(),
        }

        try:
            while self._running:
                now = time.monotonic()
                if now < self._pause_until:
                    if mock_sim is not None:
                        mock_sim.step_physics()
                    time.sleep(0.02)
                    continue

                cycle_start = time.monotonic()
                is_manual = False
                seq_override = None

                if not self._cmd_queue.empty():
                    msg_type, payload, seq_override, is_manual, log_msg = self._cmd_queue.get_nowait()
                    if log_msg:
                        self.sig_log.emit("INFO", log_msg)
                elif self._active_mode.startswith("VEL("):
                    msg_type = proto.TYPE_CMD_VEL
                    payload = proto.pack_cmd_vel(self._hold_vx, self._hold_omega)
                else:
                    msg_type = proto.TYPE_CMD_POLL
                    payload = b""

                use_seq = (seq_override & 0xFF) if seq_override is not None else seq
                tx_frame = proto.build_raw_frame(msg_type, use_seq, payload)
                ts_str = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                self.sig_raw_frame.emit(
                    "TX", ts_str, tx_frame, proto.format_frame_breakdown(tx_frame), is_manual
                )

                t0 = time.monotonic()
                rx_raw: Optional[bytes] = None
                parsed_tlm: Optional[proto.TelemetryExt] = None

                if mock_sim is not None:
                    time.sleep(0.025)
                    rx_raw = mock_sim.handle_frame(tx_frame)
                    if rx_raw is not None:
                        p = proto.parse_frame_ext(rx_raw)
                        if p is not None and p.msg_type == proto.TYPE_TELEMETRY:
                            parsed_tlm = proto.unpack_telemetry_ext(p.data)
                elif ser is not None:
                    try:
                        ser.write(tx_frame)
                        ser.flush()
                        rx_buf = bytearray()
                        deadline = t0 + self.read_timeout_s
                        while time.monotonic() < deadline and self._running:
                            waiting = ser.in_waiting
                            chunk = ser.read(waiting if waiting > 0 else 1)
                            if chunk:
                                rx_buf.extend(chunk)
                                p = proto.extract_frame_from_buffer_ext(rx_buf)
                                if p is not None and p.msg_type == proto.TYPE_TELEMETRY:
                                    rx_raw = proto.build_frame_ext(p.msg_type, p.seq, p.data)
                                    parsed_tlm = proto.unpack_telemetry_ext(p.data)
                                    break
                    except serial.SerialException as exc:
                        self.sig_log.emit("ERR", f"串口读写异常: {exc}")
                        time.sleep(0.1)

                rtt_ms = (time.monotonic() - t0) * 1000.0
                stats["tx"] += 1
                stats["mode"] = self._active_mode

                if parsed_tlm is not None and rx_raw is not None:
                    stats["rx"] += 1
                    stats["rtt_ms"] = rtt_ms
                    stats["rtt_sum_ms"] += rtt_ms
                    stats["avg_rtt_ms"] = stats["rtt_sum_ms"] / stats["rx"]
                    rx_ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                    self.sig_raw_frame.emit(
                        "RX", rx_ts, rx_raw, proto.format_frame_breakdown(rx_raw), is_manual
                    )
                else:
                    stats["local_timeout"] += 1
                    if is_manual:
                        self.sig_log.emit("WARN", f"指令 SEQ={use_seq} 等待回包超时 ({self.read_timeout_s*1000:.0f}ms)")

                tx_cnt = stats["tx"]
                rx_cnt = stats["rx"]
                stats["loss_pct"] = ((tx_cnt - rx_cnt) / tx_cnt * 100.0) if tx_cnt > 0 else 0.0
                elapsed_total = max(time.monotonic() - stats["t_start"], 1e-3)
                stats["hz"] = tx_cnt / elapsed_total

                if parsed_tlm is not None:
                    self.sig_telemetry.emit(parsed_tlm, dict(stats))

                if seq_override is None:
                    seq = (seq + 1) & 0xFF

                cycle_elapsed = time.monotonic() - cycle_start
                if cycle_elapsed < self.period_s:
                    time.sleep(self.period_s - cycle_elapsed)

        finally:
            if ser is not None and ser.is_open:
                try:
                    stop_f = proto.build_frame_ext(proto.TYPE_CMD_STOP, seq, b"")
                    ser.write(stop_f)
                    ser.flush()
                except Exception:
                    pass
                ser.close()
            self.sig_link_state.emit(False, "已断开")
            self.sig_log.emit("INFO", "通信链路已安全关闭")
