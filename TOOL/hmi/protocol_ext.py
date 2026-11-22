"""阶段 3（S3-DEMO v2/v3）协议扩展层：定义 TYPE 0x05 CMD_ACTION（含 0x06 里程计归零）与原始帧工具编解码（不修改 ../protocol.py）."""

from dataclasses import dataclass
import os
import struct
import sys
from typing import Optional

# 动态引入上级目录的 protocol.py（保持原文件只读不改）
_PARENT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PARENT_DIR not in sys.path:
    sys.path.insert(0, _PARENT_DIR)

import protocol as base_proto  # noqa: E402

# 复用基础常量
FRAME_HEADER = base_proto.FRAME_HEADER
FRAME_TAIL = base_proto.FRAME_TAIL
FRAME_OVERHEAD = base_proto.FRAME_OVERHEAD
FRAME_MIN_LEN = base_proto.FRAME_MIN_LEN

TYPE_CMD_POLL = base_proto.TYPE_CMD_POLL
TYPE_CMD_VEL = base_proto.TYPE_CMD_VEL
TYPE_CMD_STOP = base_proto.TYPE_CMD_STOP
TYPE_CMD_MODE = base_proto.TYPE_CMD_MODE
TYPE_CMD_ACTION = 0x05
TYPE_TELEMETRY = base_proto.TYPE_TELEMETRY

LEN_CMD_ACTION = 3

# 动作 ID 定义（与 STM32 comm_actions.h 严格对齐）
ACTION_MOVE_MM = 0x01     # 前进/后退 (mm, int16, 负=后退，v3 带梯形加减速)
ACTION_TURN_01D = 0x02    # 左转/右转 (0.1°, int16, 正=CCW 左转, 负=CW 右转)
ACTION_STOP = 0x03        # 动作停车
ACTION_UTURN_180 = 0x04   # 掉头 180°
ACTION_HOME_RSVD = 0x05   # 0x05 回起点预留（保持预留不动）
ACTION_RESET_ODOM = 0x06  # 0x06 远程里程计归零（X/Y/OdomYaw 清零 + IMU 航向零点重锁存）

ACTION_NAMES = {
    ACTION_MOVE_MM: "直行距离(mm)",
    ACTION_TURN_01D: "定点转向(0.1°)",
    ACTION_STOP: "动作停车",
    ACTION_UTURN_180: "掉头180°",
    ACTION_RESET_ODOM: "里程计归零(0x06)",
}

TYPE_NAMES = {
    TYPE_CMD_POLL: "CMD_POLL(0x01)",
    TYPE_CMD_VEL: "CMD_VEL(0x02)",
    TYPE_CMD_STOP: "CMD_STOP(0x03)",
    TYPE_CMD_MODE: "CMD_MODE(0x04)",
    TYPE_CMD_ACTION: "CMD_ACTION(0x05)",
    TYPE_TELEMETRY: "TELEMETRY(0x10)",
}

EXT_EXPECTED_DATA_LEN = dict(base_proto.EXPECTED_DATA_LEN)
EXT_EXPECTED_DATA_LEN[TYPE_CMD_ACTION] = LEN_CMD_ACTION


@dataclass
class TelemetryExt:
    rpm: tuple
    pwm: tuple
    x_m: float
    y_m: float
    odom_yaw_deg: float
    imu_yaw_deg: float
    status: int
    imu_ok: bool
    timed_out: bool
    heading_active: bool
    cmd_rejected: bool
    action_running: bool
    action_done: bool
    action_timeout: bool
    fusion_mode: int
    drop_count: int
    timeout_count: int


def crc8(data: bytes) -> int:
    return base_proto.crc8(data)


def pack_cmd_vel(vx_mps: float, omega_rads: float) -> bytes:
    return base_proto.pack_cmd_vel(vx_mps, omega_rads)


def pack_cmd_mode(fusion_mode: int) -> bytes:
    return base_proto.pack_cmd_mode(fusion_mode)


def pack_cmd_action(action_id: int, param: int = 0) -> bytes:
    """打包 CMD_ACTION (3B)：action_id(uint8) + param(int16 小端)。"""
    aid = action_id & 0xFF
    p_clamped = max(-32768, min(32767, int(round(param))))
    return struct.pack("<Bh", aid, p_clamped)


def unpack_cmd_action(data: bytes) -> Optional[tuple]:
    if len(data) != LEN_CMD_ACTION:
        return None
    aid, param = struct.unpack("<Bh", data)
    return aid, param


def build_frame_ext(msg_type: int, seq: int, data: bytes = b"") -> bytes:
    """支持 TYPE 0x05 CMD_ACTION 的定长校验组帧函数。"""
    if msg_type in base_proto.EXPECTED_DATA_LEN:
        return base_proto.build_frame(msg_type, seq, data)
    if msg_type not in EXT_EXPECTED_DATA_LEN:
        raise ValueError(f"不支持的帧类型: 0x{msg_type:02X}")

    exp_len = EXT_EXPECTED_DATA_LEN[msg_type]
    if len(data) != exp_len:
        raise ValueError(
            f"TYPE 0x{msg_type:02X} 载荷长度应为 {exp_len}B，实际为 {len(data)}B"
        )

    body = bytes((msg_type & 0xFF, seq & 0xFF)) + data
    c = crc8(body)
    return FRAME_HEADER + body + bytes((c,)) + FRAME_TAIL


def build_raw_frame(msg_type: int, seq: int, data: bytes = b"") -> bytes:
    """原始帧工具组帧：允许任意自定义 TYPE/SEQ/DATA 并自动计算 CRC8 与头尾。"""
    body = bytes((msg_type & 0xFF, seq & 0xFF)) + bytes(data)
    c = crc8(body)
    return FRAME_HEADER + body + bytes((c,)) + FRAME_TAIL


def parse_frame_ext(raw: bytes) -> Optional[base_proto.ParsedFrame]:
    """支持 TYPE 0x05 与 TELEMETRY 的完整单帧解析。"""
    if len(raw) < FRAME_MIN_LEN:
        return None
    if raw[:2] != FRAME_HEADER or raw[-2:] != FRAME_TAIL:
        return None

    msg_type = raw[2]
    seq = raw[3]
    data = raw[4:-3]
    if msg_type in EXT_EXPECTED_DATA_LEN:
        if len(data) != EXT_EXPECTED_DATA_LEN[msg_type]:
            return None

    crc_rx = raw[-3]
    crc_calc = crc8(raw[2:-3])
    if crc_rx != crc_calc:
        return None

    return base_proto.ParsedFrame(msg_type=msg_type, seq=seq, data=data, crc8=crc_rx)


def extract_frame_from_buffer_ext(buf: bytearray) -> Optional[base_proto.ParsedFrame]:
    """从流式字节缓冲中提取一帧（兼容 0x01~0x05 及 0x10）。"""
    while len(buf) >= FRAME_MIN_LEN:
        if buf[0] != FRAME_HEADER[0]:
            del buf[0]
            continue
        if buf[1] != FRAME_HEADER[1]:
            del buf[0]
            continue

        msg_type = buf[2]
        if msg_type not in EXT_EXPECTED_DATA_LEN:
            del buf[0]
            continue

        total_len = FRAME_OVERHEAD + EXT_EXPECTED_DATA_LEN[msg_type]
        if len(buf) < total_len:
            return None

        candidate = bytes(buf[:total_len])
        parsed = parse_frame_ext(candidate)
        if parsed is not None:
            del buf[:total_len]
            return parsed

        del buf[0]

    return None


def unpack_telemetry_ext(data: bytes) -> Optional[TelemetryExt]:
    """解包 26B TELEMETRY，包含 status 高位动作状态位（bit4=RUNNING, bit5=DONE, bit6=TIMEOUT）。"""
    base_tlm = base_proto.unpack_telemetry(data)
    if base_tlm is None:
        return None

    st = base_tlm.status
    return TelemetryExt(
        rpm=base_tlm.rpm,
        pwm=base_tlm.pwm,
        x_m=base_tlm.x_m,
        y_m=base_tlm.y_m,
        odom_yaw_deg=base_tlm.odom_yaw_deg,
        imu_yaw_deg=base_tlm.imu_yaw_deg,
        status=st,
        imu_ok=base_tlm.imu_ok,
        timed_out=base_tlm.timed_out,
        heading_active=base_tlm.heading_active,
        cmd_rejected=base_tlm.cmd_rejected,
        action_running=bool(st & 0x10),
        action_done=bool(st & 0x20),
        action_timeout=bool(st & 0x40),
        fusion_mode=base_tlm.fusion_mode,
        drop_count=base_tlm.drop_count,
        timeout_count=base_tlm.timeout_count,
    )


def format_frame_breakdown(raw: bytes) -> str:
    """将原始帧拆解为人类可读的协议解析详情（供原始帧工具面板展示）。"""
    if not raw:
        return "(空数据)"
    hex_str = raw.hex(" ").upper()
    if len(raw) < FRAME_MIN_LEN:
        return f"HEX: {hex_str}\n[错误] 长度不足 {FRAME_MIN_LEN} 字节 ({len(raw)}B)"

    hdr_ok = raw[:2] == FRAME_HEADER
    tail_ok = raw[-2:] == FRAME_TAIL
    msg_type = raw[2]
    seq = raw[3]
    data = raw[4:-3]
    crc_rx = raw[-3]
    crc_calc = crc8(raw[2:-3])
    crc_ok = crc_rx == crc_calc
    type_name = TYPE_NAMES.get(msg_type, f"UNKNOWN(0x{msg_type:02X})")

    lines = [
        f"HEX ({len(raw)}B): {hex_str}",
        f"帧头: {'OK (AA 55)' if hdr_ok else 'ERR'} | TYPE: {type_name} | SEQ: {seq} (0x{seq:02X})",
        f"DATA ({len(data)}B): {data.hex(' ').upper() if data else '(无)'}",
        f"CRC8: 收到=0x{crc_rx:02X} 计算=0x{crc_calc:02X} [{'OK' if crc_ok else 'ERR'}] | 帧尾: {'OK (0D 0A)' if tail_ok else 'ERR'}",
    ]

    if hdr_ok and tail_ok and crc_ok:
        if msg_type == TYPE_TELEMETRY:
            tlm = unpack_telemetry_ext(data)
            if tlm is not None:
                act_str = (
                    "RUNNING"
                    if tlm.action_running
                    else ("DONE" if tlm.action_done else ("ACT_TIMEOUT" if tlm.action_timeout else "IDLE"))
                )
                lines.append(
                    f"遥测解析: RPM={list(tlm.rpm)} PWM%={list(tlm.pwm)} "
                    f"X={tlm.x_m:+.3f}m Y={tlm.y_m:+.3f}m OdomYaw={tlm.odom_yaw_deg:+.2f}° ImuYaw={tlm.imu_yaw_deg:+.2f}°"
                )
                lines.append(
                    f"状态位: 0x{tlm.status:02X} (IMU={'OK' if tlm.imu_ok else 'NO'}, "
                    f"400ms超时={tlm.timed_out}, 航向环={tlm.heading_active}, 动作={act_str}) | "
                    f"fusion={tlm.fusion_mode} drop={tlm.drop_count} timeout={tlm.timeout_count}"
                )
        elif msg_type == TYPE_CMD_ACTION and len(data) == LEN_CMD_ACTION:
            aid, param = unpack_cmd_action(data)
            aname = ACTION_NAMES.get(aid, f"0x{aid:02X}")
            lines.append(f"动作解析: action_id=0x{aid:02X} ({aname}), param={param}")
        elif msg_type == TYPE_CMD_VEL and len(data) == 4:
            vx_mm, w_mrad = struct.unpack("<hh", data)
            lines.append(f"速度解析: vx={vx_mm} mm/s ({vx_mm/1000:.3f} m/s), omega={w_mrad} mrad/s ({w_mrad/1000:.3f} rad/s)")

    return "\n".join(lines)


def self_test_ext() -> dict:
    base_res = base_proto.self_test()
    # 1) 测试 CMD_ACTION(0x01, 1300) 组帧与解包
    act_payload = pack_cmd_action(ACTION_MOVE_MM, 1300)
    assert act_payload == bytes.fromhex("01 14 05"), f"pack_cmd_action 错误: {act_payload.hex()}"
    act_frame = build_frame_ext(TYPE_CMD_ACTION, 7, act_payload)
    parsed = parse_frame_ext(act_frame)
    assert parsed is not None and parsed.msg_type == TYPE_CMD_ACTION and parsed.seq == 7
    aid, param = unpack_cmd_action(parsed.data)
    assert aid == ACTION_MOVE_MM and param == 1300
    base_res["cmd_action_1300_hex"] = act_frame.hex(" ").upper()

    # 2) 测试 S3-DEMO v3 新增 CMD_ACTION(0x06, 0) 远程里程计归零帧 (10B)
    rst_payload = pack_cmd_action(ACTION_RESET_ODOM, 0)
    assert rst_payload == bytes.fromhex("06 00 00"), f"0x06 payload 错误: {rst_payload.hex()}"
    rst_frame = build_frame_ext(TYPE_CMD_ACTION, 1, rst_payload)
    parsed_rst = parse_frame_ext(rst_frame)
    assert parsed_rst is not None and parsed_rst.msg_type == TYPE_CMD_ACTION
    r_aid, r_param = unpack_cmd_action(parsed_rst.data)
    assert r_aid == ACTION_RESET_ODOM and r_param == 0
    base_res["cmd_action_reset_odom_hex"] = rst_frame.hex(" ").upper()
    return base_res


if __name__ == "__main__":
    res = self_test_ext()
    print("protocol_ext.py 自检通过:", res)
