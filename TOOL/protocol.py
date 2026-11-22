"""阶段 3（S3-03）HC-12 通信协议纯软件实现（与 STM32 端 comm_protocol.h/c 逐位一致）."""

from dataclasses import dataclass
import struct
from typing import Optional

FRAME_HEADER = b"\xAA\x55"
FRAME_TAIL = b"\x0D\x0A"
FRAME_OVERHEAD = 7
FRAME_MIN_LEN = FRAME_OVERHEAD

CRC8_POLY = 0x07
CRC8_INIT = 0x00
CRC8_XOROUT = 0x00

TYPE_CMD_POLL = 0x01
TYPE_CMD_VEL = 0x02
TYPE_CMD_STOP = 0x03
TYPE_CMD_MODE = 0x04
TYPE_TELEMETRY = 0x10

EXPECTED_DATA_LEN = {
    TYPE_CMD_POLL: 0,
    TYPE_CMD_VEL: 4,
    TYPE_CMD_STOP: 0,
    TYPE_CMD_MODE: 1,
    TYPE_TELEMETRY: 26,
}

COMM_PERIOD_MS = 50


@dataclass
class ParsedFrame:
    msg_type: int
    seq: int
    data: bytes
    crc8: int


@dataclass
class Telemetry:
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
    fusion_mode: int
    drop_count: int
    timeout_count: int


def crc8(data: bytes) -> int:
    """按位计算 CRC8：poly=0x07, init=0x00, refIn=False, refOut=False, xorOut=0x00。"""
    crc = CRC8_INIT
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x80:
                crc = ((crc << 1) ^ CRC8_POLY) & 0xFF
            else:
                crc = (crc << 1) & 0xFF
    return crc ^ CRC8_XOROUT


def build_frame(msg_type: int, seq: int, data: bytes = b"") -> bytes:
    """按 AA 55 | TYPE | SEQ | DATA | CRC8 | 0D 0A 组帧，严格校验 TYPE 与 DATA 定长。"""
    if msg_type not in EXPECTED_DATA_LEN:
        raise ValueError(f"不支持的帧类型: 0x{msg_type:02X}")

    exp_len = EXPECTED_DATA_LEN[msg_type]
    if len(data) != exp_len:
        raise ValueError(
            f"TYPE 0x{msg_type:02X} 载荷长度应为 {exp_len}B，实际为 {len(data)}B"
        )

    seq_u8 = seq & 0xFF
    body = bytes((msg_type & 0xFF, seq_u8)) + data
    crc = crc8(body)
    return FRAME_HEADER + body + bytes((crc,)) + FRAME_TAIL


def parse_frame(raw: bytes) -> Optional[ParsedFrame]:
    """校验完整单帧（头/尾/长度/CRC8），失败返回 None，不抛异常。"""
    if len(raw) < FRAME_MIN_LEN:
        return None
    if raw[:2] != FRAME_HEADER or raw[-2:] != FRAME_TAIL:
        return None

    msg_type = raw[2]
    seq = raw[3]
    if msg_type not in EXPECTED_DATA_LEN:
        return None

    data = raw[4:-3]
    if len(data) != EXPECTED_DATA_LEN[msg_type]:
        return None

    crc_rx = raw[-3]
    crc_calc = crc8(raw[2:-3])
    if crc_rx != crc_calc:
        return None

    return ParsedFrame(msg_type=msg_type, seq=seq, data=data, crc8=crc_rx)


def extract_frame_from_buffer(buf: bytearray) -> Optional[ParsedFrame]:
    """从流式字节缓冲中同步并提取一帧合法报文，自动丢弃无效前导字节。"""
    while len(buf) >= FRAME_MIN_LEN:
        if buf[0] != FRAME_HEADER[0]:
            del buf[0]
            continue
        if buf[1] != FRAME_HEADER[1]:
            del buf[0]
            continue

        msg_type = buf[2]
        if msg_type not in EXPECTED_DATA_LEN:
            del buf[0]
            continue

        total_len = FRAME_OVERHEAD + EXPECTED_DATA_LEN[msg_type]
        if len(buf) < total_len:
            return None

        candidate = bytes(buf[:total_len])
        parsed = parse_frame(candidate)
        if parsed is not None:
            del buf[:total_len]
            return parsed

        del buf[0]

    return None


def _clamp_i16(val: float) -> int:
    iv = int(round(val))
    if iv > 32767:
        return 32767
    if iv < -32768:
        return -32768
    return iv


def pack_cmd_vel(vx_mps: float, omega_rads: float) -> bytes:
    """打包 CMD_VEL (4B)：vx(mm/s) 与 omega(mrad/s) 小端 int16。"""
    vx_mmps = _clamp_i16(vx_mps * 1000.0)
    omega_mradps = _clamp_i16(omega_rads * 1000.0)
    return struct.pack("<hh", vx_mmps, omega_mradps)


def pack_cmd_mode(fusion_mode: int) -> bytes:
    """打包 CMD_MODE (1B)：0=纯编码器，1=IMU 为主融合。"""
    return struct.pack("<B", 1 if fusion_mode else 0)


def unpack_telemetry(data: bytes) -> Optional[Telemetry]:
    """解包 TELEMETRY (26B) 为可读工程单位（m / deg / RPM / %）。"""
    if len(data) != EXPECTED_DATA_LEN[TYPE_TELEMETRY]:
        return None

    fields = struct.unpack("<4h4b4h2B2H", data)
    rpm = fields[0:4]
    pwm = fields[4:8]
    x_mm, y_mm, odom_001deg, imu_001deg = fields[8:12]
    status, fusion_mode, drop_count, timeout_count = fields[12:16]

    return Telemetry(
        rpm=rpm,
        pwm=pwm,
        x_m=x_mm / 1000.0,
        y_m=y_mm / 1000.0,
        odom_yaw_deg=odom_001deg * 0.01,
        imu_yaw_deg=imu_001deg * 0.01,
        status=status,
        imu_ok=bool(status & 0x01),
        timed_out=bool(status & 0x02),
        heading_active=bool(status & 0x04),
        cmd_rejected=bool(status & 0x08),
        fusion_mode=fusion_mode,
        drop_count=drop_count,
        timeout_count=timeout_count,
    )


def self_test() -> dict:
    """校验 CRC8 两标准向量、CMD_STOP 完整帧与 TELEMETRY 编解码一致性。"""
    vec1 = bytes.fromhex("03 01")
    vec2 = bytes.fromhex("02 01 64 00 00 00")
    c1 = crc8(vec1)
    c2 = crc8(vec2)
    if c1 != 0x38:
        raise AssertionError(f"CRC8 向量1错误: 0x{c1:02X} != 0x38")
    if c2 != 0x3D:
        raise AssertionError(f"CRC8 向量2错误: 0x{c2:02X} != 0x3D")

    stop_frame = build_frame(TYPE_CMD_STOP, 1)
    expected_stop = bytes.fromhex("AA 55 03 01 38 0D 0A")
    if stop_frame != expected_stop:
        raise AssertionError(
            f"CMD_STOP 组帧不一致: {stop_frame.hex(' ').upper()}"
        )

    parsed_stop = parse_frame(stop_frame)
    if parsed_stop is None or parsed_stop.msg_type != TYPE_CMD_STOP or parsed_stop.seq != 1:
        raise AssertionError("CMD_STOP 帧解析自检失败")

    if parse_frame(b"\xAB\x55\x03\x01\x38\x0D\x0A") is not None:
        raise AssertionError("坏帧头未返回 None")
    if parse_frame(b"\xAA\x55\x03\x01\x38\x0D\x0B") is not None:
        raise AssertionError("坏帧尾未返回 None")
    if parse_frame(b"\xAA\x55\x03\x01\x39\x0D\x0A") is not None:
        raise AssertionError("坏 CRC8 未返回 None")
    if parse_frame(b"\xAA\x55\x03\x01\x38\x0D") is not None:
        raise AssertionError("短帧长度校验未返回 None")

    sample_tlm_raw = struct.pack(
        "<4h4b4h2B2H",
        100, -100, 99, 101,
        35, -35, 34, 36,
        2002, -12, -30, 17930,
        0x01, 1, 2, 1,
    )
    tlm_frame = build_frame(TYPE_TELEMETRY, 0xFF, sample_tlm_raw)
    parsed_tlm = parse_frame(tlm_frame)
    if parsed_tlm is None:
        raise AssertionError("TELEMETRY 33B 帧解析失败")
    tlm = unpack_telemetry(parsed_tlm.data)
    if tlm is None or tlm.rpm != (100, -100, 99, 101) or abs(tlm.x_m - 2.002) > 1e-6:
        raise AssertionError("TELEMETRY 26B 解包失败")

    return {
        "crc_vec1": c1,
        "crc_vec2": c2,
        "cmd_stop_hex": stop_frame.hex(" ").upper(),
    }


if __name__ == "__main__":
    res = self_test()
    print(f"CRC8 vec1 {{03 01}}             = 0x{res['crc_vec1']:02X} (PASS)")
    print(f"CRC8 vec2 {{02 01 64 00 00 00}} = 0x{res['crc_vec2']:02X} (PASS)")
    print(f"CMD_STOP frame (seq=1)        = {res['cmd_stop_hex']} (PASS)")
    print("protocol.py 所有自检通过！")
