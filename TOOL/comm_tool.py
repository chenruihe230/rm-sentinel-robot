"""阶段 3（S3-03）电脑端 HC-12 半双工遥控与遥测工具."""

import argparse
import queue
import sys
import threading
import time
from typing import Optional

import serial

import protocol


def _stdin_worker(cmd_queue: "queue.Queue[str]", stop_event: threading.Event) -> None:
    while not stop_event.is_set():
        try:
            line = sys.stdin.readline()
        except Exception:
            break
        if not line:
            break
        cmd_queue.put(line.strip())


def _print_help() -> None:
    print(
        "\n命令说明:\n"
        "  v <vx> <omega>   发送速度指令并持续保持心跳（m/s, rad/s），如: v 0.2 0\n"
        "  s                立即发送 CMD_STOP 强停（切回 POLL 心跳）\n"
        "  m <0|1>          切换融合模式 (0=纯编码器, 1=IMU 为主)\n"
        "  p                切回纯 POLL 轮询（不改当前状态；停车请用 s）\n"
        "  t                断连超时测试：暂停发送 0.8s 触发 STM32 400ms 自动停车\n"
        "  h                显示本帮助\n"
        "  q                发送 CMD_STOP 停车并退出\n"
    )


def _format_status_line(
    tlm: Optional[protocol.Telemetry],
    stats: dict,
    mode_desc: str,
) -> str:
    tx = stats["tx"]
    rx = stats["rx"]
    lto = stats["local_timeout"]
    loss_pct = ((tx - rx) / tx * 100.0) if tx > 0 else 0.0
    avg_rtt = (stats["rtt_sum_ms"] / rx) if rx > 0 else 0.0
    elapsed_s = max(time.monotonic() - stats["t_start"], 1e-3)
    rate_hz = tx / elapsed_s

    header = (
        f"[{mode_desc}] TX={tx} RX={rx} 本地超时={lto} "
        f"丢包率={loss_pct:.1f}% 频率={rate_hz:.1f}Hz RTT={avg_rtt:.1f}ms"
    )
    if tlm is None:
        return header + "\n  (等待 STM32 首帧遥测...)"

    flags = []
    flags.append("IMU:OK" if tlm.imu_ok else "IMU:NO")
    if tlm.timed_out:
        flags.append("TIMEOUT!")
    if tlm.heading_active:
        flags.append("HDG")
    if tlm.cmd_rejected:
        flags.append("REJECT")

    return (
        f"{header}\n"
        f"  RPM: [{tlm.rpm[0]:4d}, {tlm.rpm[1]:4d}, {tlm.rpm[2]:4d}, {tlm.rpm[3]:4d}]  "
        f"PWM%: [{tlm.pwm[0]:4d}, {tlm.pwm[1]:4d}, {tlm.pwm[2]:4d}, {tlm.pwm[3]:4d}]\n"
        f"  Pos: X={tlm.x_m:+.3f}m Y={tlm.y_m:+.3f}m  "
        f"OdomYaw={tlm.odom_yaw_deg:+6.2f}° ImuYaw={tlm.imu_yaw_deg:+6.2f}°\n"
        f"  State: {' '.join(flags)} | fusion={tlm.fusion_mode} | "
        f"drop={tlm.drop_count} timeout={tlm.timeout_count}"
    )


def _send_and_wait_reply(
    ser: serial.Serial,
    msg_type: int,
    seq: int,
    data: bytes,
    read_timeout_s: float,
) -> tuple:
    """半双工单回合：发 1 帧 -> 等回帧 TELEMETRY 或读超时，返回 (Telemetry|None, rtt_ms|None, rx_bytes)."""
    frame = protocol.build_frame(msg_type, seq, data)
    t0 = time.monotonic()
    ser.write(frame)
    ser.flush()

    rx_buf = bytearray()
    deadline = t0 + read_timeout_s
    while time.monotonic() < deadline:
        waiting = ser.in_waiting
        chunk = ser.read(waiting if waiting > 0 else 1)
        if chunk:
            rx_buf.extend(chunk)
            parsed = protocol.extract_frame_from_buffer(rx_buf)
            if parsed is not None and parsed.msg_type == protocol.TYPE_TELEMETRY:
                rtt_ms = (time.monotonic() - t0) * 1000.0
                tlm = protocol.unpack_telemetry(parsed.data)
                return tlm, rtt_ms, len(rx_buf)

    return None, None, len(rx_buf)


def run_tool(args: argparse.Namespace) -> int:
    try:
        self_check = protocol.self_test()
    except AssertionError as exc:
        print(f"[自检失败] {exc}", file=sys.stderr)
        return 1

    print(
        f"[CRC8 自检通过] vec1=0x{self_check['crc_vec1']:02X} "
        f"vec2=0x{self_check['crc_vec2']:02X} "
        f"STOP={self_check['cmd_stop_hex']}"
    )

    read_timeout_s = max(args.timeout_ms / 1000.0, 0.05)
    period_s = max(args.period_ms / 1000.0, 0.02)

    try:
        ser = serial.Serial(
            port=args.port,
            baudrate=args.baud,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.02,
            rtscts=False,
            dsrdtr=False,
        )
    except serial.SerialException as exc:
        print(f"[串口打开失败] {args.port}: {exc}", file=sys.stderr)
        return 2

    print(f"[串口已打开] {args.port} @ {args.baud} 8N1 (读超时={args.timeout_ms}ms)")
    _print_help()

    cmd_queue: "queue.Queue[str]" = queue.Queue()
    stop_event = threading.Event()
    input_thread = threading.Thread(
        target=_stdin_worker, args=(cmd_queue, stop_event), daemon=True
    )
    input_thread.start()

    seq = 0
    active_mode = "POLL"
    hold_vx = 0.0
    hold_omega = 0.0
    one_shot_cmds: "queue.Queue[tuple]" = queue.Queue()
    latest_tlm: Optional[protocol.Telemetry] = None
    stats = {
        "tx": 0,
        "rx": 0,
        "local_timeout": 0,
        "rtt_sum_ms": 0.0,
        "t_start": time.monotonic(),
    }
    last_print_t = 0.0
    force_print = True

    try:
        ser.reset_input_buffer()
        while True:
            cycle_start = time.monotonic()

            # 处理用户输入指令（不阻塞主轮询循环）
            while not cmd_queue.empty():
                raw_cmd = cmd_queue.get_nowait()
                if not raw_cmd:
                    continue
                parts = raw_cmd.split()
                op = parts[0].lower()

                if op == "q":
                    print("[退出] 发送 CMD_STOP 停车...")
                    _send_and_wait_reply(
                        ser, protocol.TYPE_CMD_STOP, seq, b"", read_timeout_s
                    )
                    return 0
                elif op == "s":
                    active_mode = "POLL"
                    hold_vx = 0.0
                    hold_omega = 0.0
                    while not one_shot_cmds.empty():
                        one_shot_cmds.get_nowait()
                    one_shot_cmds.put((protocol.TYPE_CMD_STOP, b""))
                    force_print = True
                elif op == "p":
                    active_mode = "POLL"
                    force_print = True
                elif op == "v" and len(parts) == 3:
                    try:
                        hold_vx = float(parts[1])
                        hold_omega = float(parts[2])
                    except ValueError:
                        print("[格式错误] 用法: v <vx_mps> <omega_rads>，例如 v 0.2 0")
                        continue
                    active_mode = f"VEL({hold_vx:+.2f},{hold_omega:+.2f})"
                    one_shot_cmds.put(
                        (protocol.TYPE_CMD_VEL, protocol.pack_cmd_vel(hold_vx, hold_omega))
                    )
                    force_print = True
                elif op == "m" and len(parts) == 2 and parts[1] in ("0", "1"):
                    one_shot_cmds.put(
                        (protocol.TYPE_CMD_MODE, protocol.pack_cmd_mode(int(parts[1])))
                    )
                    force_print = True
                elif op == "t":
                    print("[超时测试] 暂停发帧 0.80 s，等待触发 STM32 400ms 自动停车...")
                    active_mode = "POLL"
                    hold_vx = 0.0
                    hold_omega = 0.0
                    time.sleep(0.80)
                    ser.reset_input_buffer()
                    force_print = True
                    continue
                elif op == "h":
                    _print_help()
                else:
                    print(f"[未知指令] '{raw_cmd}'（输入 h 查看帮助）")

            # 选择本周期发送的帧类型
            if not one_shot_cmds.empty():
                msg_type, payload = one_shot_cmds.get_nowait()
            elif active_mode.startswith("VEL("):
                msg_type = protocol.TYPE_CMD_VEL
                payload = protocol.pack_cmd_vel(hold_vx, hold_omega)
            else:
                msg_type = protocol.TYPE_CMD_POLL
                payload = b""

            tlm, rtt_ms, _ = _send_and_wait_reply(
                ser, msg_type, seq, payload, read_timeout_s
            )
            stats["tx"] += 1
            if tlm is not None:
                stats["rx"] += 1
                stats["rtt_sum_ms"] += rtt_ms
                latest_tlm = tlm
            else:
                stats["local_timeout"] += 1

            seq = (seq + 1) & 0xFF

            now = time.monotonic()
            if force_print or (now - last_print_t) >= args.print_interval:
                print(_format_status_line(latest_tlm, stats, active_mode))
                last_print_t = now
                force_print = False

            elapsed = time.monotonic() - cycle_start
            if elapsed < period_s:
                time.sleep(period_s - elapsed)

    except KeyboardInterrupt:
        print("\n[Ctrl+C] 发送 CMD_STOP 安全停车...")
        try:
            _send_and_wait_reply(
                ser, protocol.TYPE_CMD_STOP, seq, b"", read_timeout_s
            )
        except Exception:
            pass
        return 0
    finally:
        stop_event.set()
        if ser.is_open:
            ser.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="HC-12 半双工底盘遥控与遥测工具 (9600 8N1)"
    )
    parser.add_argument("--port", default="COM3", help="串口号，默认 COM3（可改为 COM6 等）")
    parser.add_argument("--baud", type=int, default=9600, help="波特率，默认 9600")
    parser.add_argument(
        "--period-ms",
        type=int,
        default=protocol.COMM_PERIOD_MS,
        help="最小轮询周期 ms（默认 50，受半双工 RTT 限制实际约为 9~10 Hz）",
    )
    parser.add_argument(
        "--timeout-ms",
        type=int,
        default=260,
        help="单帧等待回包超时 ms（默认 260，留足 9600 bps 下 33B 遥测回包传输余量）",
    )
    parser.add_argument(
        "--print-interval",
        type=float,
        default=2.0,
        help="终端状态刷新间隔 s（默认 2.0s，避免打字时刷屏；收到控制命令会立即刷新）",
    )
    args = parser.parse_args()
    return run_tool(args)


if __name__ == "__main__":
    sys.exit(main())
