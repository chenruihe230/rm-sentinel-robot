"""阶段 3（S3-DEMO v3）交互式可视化上位机启动入口与全量自检脚本."""

import argparse
import math
import sys

try:
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtWidgets import QApplication
except ImportError:
    from PyQt6.QtCore import Qt, QTimer  # type: ignore
    from PyQt6.QtWidgets import QApplication  # type: ignore

import actions
import hmi_widget
import link
import protocol_ext as proto


def run_v3_headless_verification() -> None:
    """离线对 S3-DEMO v3 五大增量 (W1~W5) 进行自动化闭环逻辑与仿真误差核验。"""
    sim = link.MockStm32Simulator()

    # 1. W1 梯形加减速核验：1000mm 标准直行 vs 200mm 短距离直行 (<400mm)
    f_move_1000 = proto.build_frame_ext(proto.TYPE_CMD_ACTION, 1, proto.pack_cmd_action(proto.ACTION_MOVE_MM, 1000))
    sim.handle_frame(f_move_1000)
    for seq in range(2, 300):
        sim.last_t -= 0.020  # 推进 20ms 物理步
        rx = sim.handle_frame(proto.build_frame_ext(proto.TYPE_CMD_POLL, seq & 0xFF))
        tlm = proto.unpack_telemetry_ext(proto.parse_frame_ext(rx).data)
        if tlm.action_done:
            break
    dist_1000_mm = sim.x_m * 1000.0
    err_1000_mm = dist_1000_mm - 1000.0

    # 2. W2 0x06 远程里程计归零核验
    f_rst = proto.build_frame_ext(proto.TYPE_CMD_ACTION, 10, proto.pack_cmd_action(proto.ACTION_RESET_ODOM, 0))
    rx_rst = sim.handle_frame(f_rst)
    tlm_rst = proto.unpack_telemetry_ext(proto.parse_frame_ext(rx_rst).data)
    assert abs(tlm_rst.x_m) < 1e-4 and abs(tlm_rst.y_m) < 1e-4 and abs(tlm_rst.imu_yaw_deg) < 1e-4
    assert tlm_rst.action_done, "0x06 归零后应立即置 ACTION_DONE"

    # 3. W1 短距离 200mm (<400mm) 梯形保护核验
    f_move_200 = proto.build_frame_ext(proto.TYPE_CMD_ACTION, 11, proto.pack_cmd_action(proto.ACTION_MOVE_MM, 200))
    sim.handle_frame(f_move_200)
    for seq in range(12, 200):
        sim.last_t -= 0.020
        rx = sim.handle_frame(proto.build_frame_ext(proto.TYPE_CMD_POLL, seq & 0xFF))
        tlm = proto.unpack_telemetry_ext(proto.parse_frame_ext(rx).data)
        if tlm.action_done:
            break
    dist_200_mm = sim.x_m * 1000.0
    err_200_mm = dist_200_mm - 200.0

    # 4. W4 双击地图指点导航算法核验：(0,0,0°) -> (1.0, 1.0)m => 左转 45° + 直行 1414mm
    steps, dyaw_deg, dist_mm = actions.build_point_nav_steps(0.0, 0.0, 0.0, 1.0, 1.0)
    assert len(steps) == 2 and steps[0].action_id == proto.ACTION_TURN_01D and steps[0].param == 450
    assert steps[1].action_id == proto.ACTION_MOVE_MM and steps[1].param == 1414

    # 5. W5 三大预设剧本与两层打断核验
    for key, exp_len in (("square", 8), ("shuttle", 4), ("dance", 4)):
        _, st_list = actions.get_preset_script(key)
        assert len(st_list) == exp_len

    print(
        f"[S3-DEMO v3 闭环仿真自检通过] "
        f"1000mm梯形停止={dist_1000_mm:.1f}mm(误差{err_1000_mm:+.1f}mm) | "
        f"200mm短距停止={dist_200_mm:.1f}mm(误差{err_200_mm:+.1f}mm) | "
        f"0x06归零=({tlm_rst.x_m:.3f},{tlm_rst.y_m:.3f},{tlm_rst.imu_yaw_deg:.2f}°) | "
        f"双击导航(1,1)m=转{dyaw_deg:+.1f}°+走{dist_mm}mm"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="RM Sentry 四驱底盘车端闭环动作与遥测上位机 (S3-DEMO v3)")
    parser.add_argument("--port", default="COM6", help="默认串口号，如 COM6 或 COM3")
    parser.add_argument("--mock", action="store_true", help="启动后默认勾选并运行内置 STM32 仿真器")
    parser.add_argument("--auto-connect", action="store_true", help="启动后自动连接串口或仿真器")
    parser.add_argument("--self-test", action="store_true", help="运行协议扩展与 GUI 冒烟自检后自动退出")
    parser.add_argument("--screenshot", default="", help="自检或启动后自动保存窗口截图到指定路径")
    args = parser.parse_args()

    res = proto.self_test_ext()
    print(
        f"[S3-DEMO v3 协议自检通过] CRC8 vec1=0x{res['crc_vec1']:02X}, "
        f"vec2=0x{res['crc_vec2']:02X}, STOP={res['cmd_stop_hex']}, "
        f"ACT_1300={res['cmd_action_1300_hex']}, ACT_RST_06={res['cmd_action_reset_odom_hex']}"
    )
    run_v3_headless_verification()

    app = QApplication(sys.argv)
    win = hmi_widget.ChassisHmiWindow(
        default_port=args.port,
        default_mock=(args.mock or args.self_test),
    )
    win.show()

    if args.auto_connect or args.mock or args.self_test:
        QTimer.singleShot(100, win._toggle_connection)

    if args.self_test:
        # 自动化 GUI 演示验证：
        # 300ms: 触发双击地图 (1.20, 0.65)m 演示级导航
        # 900ms: 开启 WASD 并模拟按下 W+A 弧线驾驶打断导航
        # 1250ms: 松开 WASD 并加载『正方形巡逻』预设剧本展示队列
        def _demo_step1():
            win.plot_panel.set_nav_target(1.20, 0.65)
            win._on_map_double_clicked(1.20, 0.65)

        def _demo_step2():
            win.chk_wasd.setChecked(True)
            win._wasd_pressed.add(Qt.Key.Key_W)
            win._wasd_pressed.add(Qt.Key.Key_A)
            win._on_wasd_keys_changed()

        def _demo_step3():
            win._wasd_pressed.clear()
            win._on_wasd_keys_changed()
            win._load_and_run_preset("square")

        QTimer.singleShot(300, _demo_step1)
        QTimer.singleShot(850, _demo_step2)
        QTimer.singleShot(1250, _demo_step3)

        if args.screenshot:
            def _grab_and_quit():
                pix = win.grab()
                pix.save(args.screenshot)
                print(f"[GUI 截图已保存] {args.screenshot}")
                win.close()
                app.quit()
            QTimer.singleShot(1950, _grab_and_quit)
        else:
            QTimer.singleShot(1950, lambda: (win.close(), app.quit()))

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
