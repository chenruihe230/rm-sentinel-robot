"""阶段 3（S3-DEMO v3）暗色科技风交互式可视化主窗口（五区布局 + 0x06归零 + WASD三档赛车 + 双击地图演示级导航 + 剧本编排器 + 原始帧工具）."""

from datetime import datetime
import math
import time
from typing import Optional, Set

try:
    from PySide6.QtCore import QEvent, QObject, Qt, QTimer
    from PySide6.QtGui import QKeySequence, QShortcut
    from PySide6.QtWidgets import (
        QApplication,
        QCheckBox,
        QComboBox,
        QDoubleSpinBox,
        QFrame,
        QGridLayout,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QListWidget,
        QMainWindow,
        QPlainTextEdit,
        QProgressBar,
        QPushButton,
        QSpinBox,
        QSplitter,
        QTabWidget,
        QVBoxLayout,
        QWidget,
    )
except ImportError:
    from PyQt6.QtCore import QEvent, QObject, Qt, QTimer  # type: ignore
    from PyQt6.QtGui import QKeySequence, QShortcut  # type: ignore
    from PyQt6.QtWidgets import (  # type: ignore
        QApplication,
        QCheckBox,
        QComboBox,
        QDoubleSpinBox,
        QFrame,
        QGridLayout,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QListWidget,
        QMainWindow,
        QPlainTextEdit,
        QProgressBar,
        QPushButton,
        QSpinBox,
        QSplitter,
        QTabWidget,
        QVBoxLayout,
        QWidget,
    )

import actions
import link
import plots
import protocol_ext as proto
import raw_tool

DARK_TECH_QSS = """
QMainWindow, QWidget {
    background-color: #0B0F19;
    color: #E2E8F0;
    font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
    font-size: 12px;
}
QGroupBox {
    background-color: #111827;
    border: 1px solid #1E293B;
    border-radius: 6px;
    margin-top: 8px;
    padding-top: 8px;
    font-weight: bold;
    color: #00E5FF;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
}
QPushButton {
    background-color: #1E293B;
    color: #F8FAFC;
    border: 1px solid #334155;
    border-radius: 5px;
    padding: 5px 9px;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #0284C7;
    border-color: #00E5FF;
}
QPushButton:pressed {
    background-color: #0369A1;
}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QListWidget {
    background-color: #090D16;
    color: #00E5FF;
    border: 1px solid #334155;
    border-radius: 4px;
    padding: 3px 6px;
    font-family: Consolas, monospace;
    font-weight: bold;
}
QTabWidget::pane {
    border: 1px solid #1E293B;
    background-color: #0B0F19;
}
QTabBar::tab {
    background-color: #111827;
    color: #94A3B8;
    padding: 7px 16px;
    border: 1px solid #1E293B;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    font-weight: bold;
}
QTabBar::tab:selected {
    background-color: #0284C7;
    color: #FFFFFF;
}
QProgressBar {
    border: 1px solid #334155;
    border-radius: 4px;
    text-align: center;
    background-color: #090D16;
    color: #FFFFFF;
    font-weight: bold;
}
QProgressBar::chunk {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284C7, stop:1 #00E5FF);
}
"""

# 五档 WASD 速度配置: (档位名称, 线速度 vx m/s, 原地角速度 omega rad/s, 弧线角速度系数)
# 车端硬限幅: CHASSIS_MAX_VX_MPS = 0.869 m/s, CHASSIS_MAX_WHEEL_RPM = 250 (chassis.h，不改)
# 5 档 0.85 m/s 已贴近单轮 250 RPM 上限，弧线时车端会按比例等比缩放四轮转速（不会失控）
WASD_GEARS = [
    ("1 慢速档 (0.15 m/s | 精细微调)", 0.15, 0.80, 0.75),
    ("2 常速档 (0.30 m/s | 标准巡航)", 0.30, 1.20, 0.75),
    ("3 快速档 (0.60 m/s | 运动竞速)", 0.60, 1.80, 0.75),
    ("4 狂飙档 (0.75 m/s | 高速竞技)", 0.75, 2.40, 0.70),
    ("5 极速档 (0.85 m/s | 贴近硬件上限)", 0.85, 3.00, 0.65),
]


class ChassisHmiWindow(QMainWindow):
    """S3-DEMO v3 车端闭环动作、WASD 赛车、指点导航、剧本编排与实时遥测上位机主窗口。"""

    def __init__(self, default_port: str = "COM6", default_mock: bool = False) -> None:
        super().__init__()
        self.setWindowTitle("RM Sentry 四驱底盘车端闭环动作与遥测控制台 (S3-DEMO v3 增强版)")
        self.resize(1460, 920)
        self.setStyleSheet(DARK_TECH_QSS)

        self.worker = link.SerialLinkWorker(self)
        self.tracker = actions.ActionTracker()
        self.sequencer = actions.ActionScriptSequencer(settle_delay_s=0.30)
        self.latest_tlm: Optional[proto.TelemetryExt] = None
        self._nav_target_xy: Optional[tuple] = None

        # WASD 键盘状态集合
        self._wasd_pressed: Set[int] = set()
        self._wasd_moving: bool = False
        self._last_wasd_cmd: tuple = (0.0, 0.0)

        central = QWidget(self)
        self.setCentralWidget(central)
        root_v = QVBoxLayout(central)
        root_v.setContentsMargins(10, 6, 10, 6)
        root_v.setSpacing(6)

        # ==================== 一、顶栏 (连接状态 + 红色急停) ====================
        top_frame = QFrame()
        top_frame.setStyleSheet("background-color:#111827;border:1px solid #1E293B;border-radius:6px;")
        top_bar = QHBoxLayout(top_frame)
        top_bar.setContentsMargins(12, 6, 12, 6)

        lbl_title = QLabel("⚡ S3-DEMO v3 车端闭环 & 娱乐操控台")
        lbl_title.setStyleSheet("font-size:15px;font-weight:bold;color:#00E5FF;")
        top_bar.addWidget(lbl_title)
        top_bar.addSpacing(10)

        top_bar.addWidget(QLabel("端口:"))
        self.cmb_port = QComboBox()
        self.cmb_port.setEditable(True)
        self.cmb_port.setFixedWidth(95)
        ports = link.list_serial_ports()
        if default_port not in ports:
            ports.insert(0, default_port)
        self.cmb_port.addItems(ports)
        self.cmb_port.setCurrentText(default_port)
        top_bar.addWidget(self.cmb_port)

        btn_refresh = QPushButton("刷新端口")
        btn_refresh.clicked.connect(self._refresh_ports)
        top_bar.addWidget(btn_refresh)

        self.chk_mock = QCheckBox("仿真车端 (Mock)")
        self.chk_mock.setChecked(default_mock)
        self.chk_mock.setStyleSheet("color:#FF9100;font-weight:bold;")
        top_bar.addWidget(self.chk_mock)

        self.btn_connect = QPushButton("连接车端")
        self.btn_connect.setStyleSheet("background-color:#059669;color:#FFFFFF;padding:5px 14px;")
        self.btn_connect.clicked.connect(self._toggle_connection)
        top_bar.addWidget(self.btn_connect)

        self.lbl_link_badge = QLabel("● 未连接")
        self.lbl_link_badge.setStyleSheet("color:#94A3B8;font-weight:bold;padding:0 8px;")
        top_bar.addWidget(self.lbl_link_badge)

        top_bar.addStretch()

        self.btn_estop = QPushButton("🛑 紧急停车 E-STOP (Space)")
        self.btn_estop.setMinimumHeight(38)
        self.btn_estop.setMinimumWidth(225)
        self.btn_estop.setStyleSheet(
            "background-color:#E11D48;color:#FFFFFF;font-size:14px;font-weight:bold;"
            "border:2px solid #FDA4AF;border-radius:6px;padding:5px 16px;"
        )
        self.btn_estop.clicked.connect(lambda: self._on_emergency_stop("点击顶栏红色急停按钮"))
        top_bar.addWidget(self.btn_estop)
        root_v.addWidget(top_frame)

        # 空格键全局急停快捷键
        self.shortcut_space = QShortcut(QKeySequence(Qt.Key.Key_Space), self)
        self.shortcut_space.activated.connect(lambda: self._on_emergency_stop("按下空格键 (Space) 急停"))

        # ==================== 主标签页 (仪表盘 / 原始帧工具) ====================
        self.tabs = QTabWidget()
        root_v.addWidget(self.tabs, 1)

        # ---- Tab 1: 驾驶舱主控台 ----
        dash_tab = QWidget()
        dash_v = QVBoxLayout(dash_tab)
        dash_v.setContentsMargins(4, 4, 4, 4)

        main_split = QSplitter(Qt.Orientation.Horizontal)

        # 左侧列：二、动作区 + WASD 赛车区 + 剧本编排器 + 三、数据区
        left_col = QWidget()
        left_v = QVBoxLayout(left_col)
        left_v.setContentsMargins(0, 0, 4, 0)
        left_v.setSpacing(5)

        # -------------------- 二、动作区 (CMD_ACTION 0x05 + 0x06 归零) --------------------
        grp_action = QGroupBox("二、车端闭环参数化动作区 (TYPE 0x05 | 梯形加减速 + 0x06 归零)")
        act_grid = QGridLayout(grp_action)
        act_grid.setVerticalSpacing(4)

        # 1) 直线前进/后退 (mm)
        act_grid.addWidget(QLabel("直线距离 (mm):"), 0, 0)
        self.spin_dist_mm = QSpinBox()
        self.spin_dist_mm.setRange(10, 10000)
        self.spin_dist_mm.setSingleStep(100)
        self.spin_dist_mm.setValue(1300)
        self.spin_dist_mm.setSuffix(" mm")
        act_grid.addWidget(self.spin_dist_mm, 0, 1)

        btn_fwd = QPushButton("▲ 前进 (0x01)")
        btn_fwd.setStyleSheet("background-color:#0284C7;color:#FFFFFF;")
        btn_fwd.clicked.connect(lambda: self._trigger_move_mm(+self.spin_dist_mm.value()))
        act_grid.addWidget(btn_fwd, 0, 2)

        btn_bwd = QPushButton("▼ 后退 (0x01)")
        btn_bwd.setStyleSheet("background-color:#0369A1;color:#FFFFFF;")
        btn_bwd.clicked.connect(lambda: self._trigger_move_mm(-self.spin_dist_mm.value()))
        act_grid.addWidget(btn_bwd, 0, 3)

        # 快捷距离行（含 200mm 短距离梯形测试）
        quick_dist_bar = QHBoxLayout()
        for d_mm in (200, 500, 1000, 1300, 2000):
            b = QPushButton(f"{d_mm}mm")
            b.clicked.connect(lambda _=False, dm=d_mm: self._quick_move(dm))
            quick_dist_bar.addWidget(b)
        act_grid.addLayout(quick_dist_bar, 1, 0, 1, 4)

        # 2) 定点左转/右转 (°) 与掉头、0x06 归零
        act_grid.addWidget(QLabel("转向角度 (°):"), 2, 0)
        self.spin_turn_deg = QDoubleSpinBox()
        self.spin_turn_deg.setRange(1.0, 360.0)
        self.spin_turn_deg.setDecimals(1)
        self.spin_turn_deg.setSingleStep(15.0)
        self.spin_turn_deg.setValue(90.0)
        self.spin_turn_deg.setSuffix(" °")
        act_grid.addWidget(self.spin_turn_deg, 2, 1)

        btn_left = QPushButton("↺ 左转 CCW (0x02)")
        btn_left.setStyleSheet("background-color:#0D9488;color:#FFFFFF;")
        btn_left.clicked.connect(lambda: self._trigger_turn_deg(+self.spin_turn_deg.value()))
        act_grid.addWidget(btn_left, 2, 2)

        btn_right = QPushButton("↻ 右转 CW (0x02)")
        btn_right.setStyleSheet("background-color:#0F766E;color:#FFFFFF;")
        btn_right.clicked.connect(lambda: self._trigger_turn_deg(-self.spin_turn_deg.value()))
        act_grid.addWidget(btn_right, 2, 3)

        btn_uturn = QPushButton("⮌ 掉头 180° (0x04)")
        btn_uturn.setStyleSheet("background-color:#D97706;color:#FFFFFF;")
        btn_uturn.clicked.connect(self._trigger_uturn)
        act_grid.addWidget(btn_uturn, 3, 0, 1, 1)

        btn_reset_odom = QPushButton("🎯 里程计归零 (0x06)")
        btn_reset_odom.setStyleSheet("background-color:#7C3AED;color:#FFFFFF;")
        btn_reset_odom.clicked.connect(self._trigger_reset_odom)
        act_grid.addWidget(btn_reset_odom, 3, 1, 1, 2)

        btn_act_stop = QPushButton("■ 动作停车 (0x03)")
        btn_act_stop.setStyleSheet("background-color:#BE123C;color:#FFFFFF;")
        btn_act_stop.clicked.connect(self._trigger_action_stop)
        act_grid.addWidget(btn_act_stop, 3, 3, 1, 1)

        # 动作状态与进度条
        self.lbl_act_state = QLabel("动作状态: IDLE (就绪)")
        self.lbl_act_state.setStyleSheet("color:#00E5FF;font-weight:bold;")
        act_grid.addWidget(self.lbl_act_state, 4, 0, 1, 4)

        self.bar_action = QProgressBar()
        self.bar_action.setRange(0, 100)
        self.bar_action.setValue(0)
        self.bar_action.setFixedHeight(16)
        act_grid.addWidget(self.bar_action, 5, 0, 1, 4)

        left_v.addWidget(grp_action)

        # -------------------- W3: WASD 键盘赛车模式 + 手动速度区 --------------------
        grp_wasd = QGroupBox("🎮 W3 键盘赛车模式 (WASD 八向/五档变速[数字键1~5换挡]/松手即停) & 手动打断")
        wasd_grid = QGridLayout(grp_wasd)
        wasd_grid.setVerticalSpacing(4)

        self.chk_wasd = QCheckBox("开启 WASD 键盘驾驶 (按住 W/A/S/D 驾驶，松手自动停)")
        self.chk_wasd.setStyleSheet("color:#10B981;font-weight:bold;")
        self.chk_wasd.toggled.connect(self._on_wasd_toggled)
        wasd_grid.addWidget(self.chk_wasd, 0, 0, 1, 2)

        self.cmb_wasd_gear = QComboBox()
        for g_title, _, _, _ in WASD_GEARS:
            self.cmb_wasd_gear.addItem(g_title)
        self.cmb_wasd_gear.setCurrentIndex(1)  # 默认常速档 0.30 m/s
        wasd_grid.addWidget(self.cmb_wasd_gear, 0, 2, 1, 2)

        self.lbl_wasd_status = QLabel("键盘状态: [未激活] (勾选上方开关后按住 W/A/S/D 即可八向驾驶)")
        self.lbl_wasd_status.setStyleSheet("color:#94A3B8;font-family:Consolas,monospace;")
        wasd_grid.addWidget(self.lbl_wasd_status, 1, 0, 1, 4)

        wasd_grid.addWidget(QLabel("手动 vx:"), 2, 0)
        self.spin_vx = QDoubleSpinBox()
        self.spin_vx.setRange(-0.85, 0.85)
        self.spin_vx.setDecimals(2)
        self.spin_vx.setSingleStep(0.05)
        self.spin_vx.setValue(0.20)
        wasd_grid.addWidget(self.spin_vx, 2, 1)

        wasd_grid.addWidget(QLabel("ω (rad/s):"), 2, 2)
        self.spin_omega = QDoubleSpinBox()
        self.spin_omega.setRange(-4.0, 4.0)
        self.spin_omega.setDecimals(2)
        self.spin_omega.setSingleStep(0.20)
        self.spin_omega.setValue(0.00)
        wasd_grid.addWidget(self.spin_omega, 2, 3)

        btn_vel = QPushButton("▶ 发 CMD_VEL")
        btn_vel.clicked.connect(self._trigger_manual_vel)
        wasd_grid.addWidget(btn_vel, 3, 0, 1, 1)

        btn_mode_imu = QPushButton("IMU主融合(m=1)")
        btn_mode_imu.clicked.connect(lambda: self._trigger_mode(1))
        wasd_grid.addWidget(btn_mode_imu, 3, 1, 1, 1)

        btn_mode_enc = QPushButton("纯编码器(m=0)")
        btn_mode_enc.clicked.connect(lambda: self._trigger_mode(0))
        wasd_grid.addWidget(btn_mode_enc, 3, 2, 1, 1)

        btn_timeout_test = QPushButton("⏱ 0.8s断连测试")
        btn_timeout_test.clicked.connect(self._trigger_timeout_test)
        wasd_grid.addWidget(btn_timeout_test, 3, 3, 1, 1)

        left_v.addWidget(grp_wasd)

        # -------------------- W5 & W4: 动作剧本编排器 & 演示级指点导航队列 --------------------
        grp_seq = QGroupBox("🎬 W5 动作剧本编排器 & W4 演示级导航队列 (收到 DONE 停 0.3s 发下一步)")
        seq_v = QVBoxLayout(grp_seq)
        seq_v.setContentsMargins(8, 6, 8, 6)
        seq_v.setSpacing(4)

        preset_row = QHBoxLayout()
        btn_p_sq = QPushButton("🟩 正方形巡逻")
        btn_p_sq.setStyleSheet("background-color:#065F46;color:#FFFFFF;")
        btn_p_sq.clicked.connect(lambda: self._load_and_run_preset("square"))
        preset_row.addWidget(btn_p_sq)

        btn_p_sh = QPushButton("🟦 2m 折返跑")
        btn_p_sh.setStyleSheet("background-color:#1E40AF;color:#FFFFFF;")
        btn_p_sh.clicked.connect(lambda: self._load_and_run_preset("shuttle"))
        preset_row.addWidget(btn_p_sh)

        btn_p_da = QPushButton("🟧 左右摇摆舞")
        btn_p_da.setStyleSheet("background-color:#9A3412;color:#FFFFFF;")
        btn_p_da.clicked.connect(lambda: self._load_and_run_preset("dance"))
        preset_row.addWidget(btn_p_da)
        seq_v.addLayout(preset_row)

        edit_row = QHBoxLayout()
        btn_add_mv = QPushButton("+加直行步")
        btn_add_mv.clicked.connect(self._seq_add_move_step)
        edit_row.addWidget(btn_add_mv)

        btn_add_tn = QPushButton("+加转向步")
        btn_add_tn.clicked.connect(self._seq_add_turn_step)
        edit_row.addWidget(btn_add_tn)

        btn_del_step = QPushButton("-删选中")
        btn_del_step.clicked.connect(self._seq_remove_selected)
        edit_row.addWidget(btn_del_step)

        btn_run_seq = QPushButton("▶ 启动队列")
        btn_run_seq.setStyleSheet("background-color:#0284C7;color:#FFFFFF;")
        btn_run_seq.clicked.connect(self._seq_start_clicked)
        edit_row.addWidget(btn_run_seq)

        btn_clr_seq = QPushButton("■ 清空/中止")
        btn_clr_seq.setStyleSheet("background-color:#BE123C;color:#FFFFFF;")
        btn_clr_seq.clicked.connect(lambda: self._abort_script_queue("用户点击『清空/中止』剧本按钮", stop_car=True))
        edit_row.addWidget(btn_clr_seq)
        seq_v.addLayout(edit_row)

        self.list_seq = QListWidget()
        self.list_seq.setFixedHeight(88)
        seq_v.addWidget(self.list_seq)

        self.lbl_seq_status = QLabel("剧本队列状态: 空闲 | 双击右侧 X-Y 轨迹图可触发『演示级导航（预期落点误差 ~5cm 量级）』")
        self.lbl_seq_status.setStyleSheet("color:#FACC15;font-weight:bold;font-size:11px;")
        seq_v.addWidget(self.lbl_seq_status)

        left_v.addWidget(grp_seq)

        # ==================== 三、数据区 ====================
        grp_data = QGroupBox("三、实时遥测数据区 (26B TELEMETRY)")
        data_grid = QGridLayout(grp_data)
        data_grid.setVerticalSpacing(3)

        self.lbl_vals = {}
        fields = [
            ("x_m", "位置 X (m):", "+0.000 m", 0, 0),
            ("y_m", "位置 Y (m):", "+0.000 m", 0, 2),
            ("imu_yaw", "IMU Yaw (°):", "+0.00 °", 1, 0),
            ("odom_yaw", "Odom Yaw (°):", "+0.00 °", 1, 2),
            ("m1", "M1 左前:", "0 RPM | 0%", 2, 0),
            ("m2", "M2 右前:", "0 RPM | 0%", 2, 2),
            ("m3", "M3 左后:", "0 RPM | 0%", 3, 0),
            ("m4", "M4 右后:", "0 RPM | 0%", 3, 2),
            ("imu_st", "IMU 状态:", "未知", 4, 0),
            ("fusion", "融合模式:", "1 (IMU主)", 4, 2),
            ("hdg_st", "航向/拒绝:", "IDLE | OK", 5, 0),
            ("to_flag", "400ms 超时标志:", "正常", 5, 2),
            ("drop_cnt", "车端 drop_count:", "0", 6, 0),
            ("to_cnt", "车端 timeout_count:", "0", 6, 2),
            ("local_to", "上位机本地超时:", "0 (0.0%)", 7, 0),
            ("rtt_hz", "往返 RTT / 频率:", "0.0 ms | 0.0 Hz", 7, 2),
        ]
        for key, title, init_val, r, c in fields:
            lbl_t = QLabel(title)
            lbl_t.setStyleSheet("color:#94A3B8;")
            lbl_v = QLabel(init_val)
            lbl_v.setStyleSheet("color:#00E5FF;font-family:Consolas,monospace;font-weight:bold;")
            data_grid.addWidget(lbl_t, r, c)
            data_grid.addWidget(lbl_v, r, c + 1)
            self.lbl_vals[key] = lbl_v

        left_v.addWidget(grp_data)
        left_v.addStretch()
        left_col.setFixedWidth(540)
        main_split.addWidget(left_col)

        # 右侧列：四、曲线区 + 五、日志区
        right_split = QSplitter(Qt.Orientation.Vertical)

        grp_plots = QGroupBox("四、实时曲线区（X-Y 轨迹+车头朝向射线+双击地图演示级导航 / Yaw 双曲线 / 四轮 RPM）")
        plot_v = QVBoxLayout(grp_plots)
        plot_v.setContentsMargins(4, 6, 4, 4)
        self.plot_panel = plots.TelemetryPlotPanel()
        self.plot_panel.sig_map_double_clicked.connect(self._on_map_double_clicked)
        plot_v.addWidget(self.plot_panel)
        right_split.addWidget(grp_plots)

        grp_log = QGroupBox("五、事件与动作日志区（指令 / 剧本进度 / 指点导航落点误差 / 到位 / 超时 / 急停）")
        log_v = QVBoxLayout(grp_log)
        self.txt_log = QPlainTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setMaximumBlockCount(500)
        self.txt_log.setStyleSheet("font-family:Consolas,monospace;background:#090D16;color:#E2E8F0;")
        log_v.addWidget(self.txt_log)
        grp_log.setMaximumHeight(195)
        right_split.addWidget(grp_log)

        main_split.addWidget(right_split)
        dash_v.addWidget(main_split)
        self.tabs.addTab(dash_tab, "🚀 主控仪表盘 (S3-DEMO v3 五区视图)")

        # ---- Tab 2: 原始帧工具 ----
        self.raw_tab = raw_tool.RawFrameToolTab()
        self.raw_tab.sig_send_raw.connect(self._on_raw_tab_send)
        self.tabs.addTab(self.raw_tab, "🛠 原始帧工具 (替代串口助手)")

        # 绑定后台线程信号
        self.worker.sig_telemetry.connect(self._on_telemetry)
        self.worker.sig_raw_frame.connect(self.raw_tab.on_raw_frame)
        self.worker.sig_log.connect(self.append_log)
        self.worker.sig_link_state.connect(self._on_link_state)

        # 50ms 定时器：驱动 WASD 非阻塞周期发帧 + 剧本编排器 0.3s 停顿步进
        self._ctrl_timer = QTimer(self)
        self._ctrl_timer.setInterval(50)
        self._ctrl_timer.timeout.connect(self._on_ctrl_timer_50ms)
        self._ctrl_timer.start()

        # 安装全局事件过滤器以捕获 W/A/S/D 按键按下与松开
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

        self.append_log(
            "INFO",
            "S3-DEMO v3 就绪：新增 ① 0x01 直行梯形加减速 ② 0x06 远程里程计归零 ③ WASD 三档八向赛车 ④ 车头朝向射线+双击地图演示级导航 ⑤ 花式剧本编排器。",
        )

    # ==================== WASD 键盘事件过滤与 50ms 周期控制 ====================
    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if self.chk_wasd.isChecked() and event.type() in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
            # 若当前焦点在输入框 QLineEdit 内则不拦截字母输入
            focus_w = QApplication.focusWidget()
            if isinstance(focus_w, QLineEdit):
                return super().eventFilter(watched, event)

            key = event.key()
            # 数字键 1~5 快速换挡
            gear_keys = (Qt.Key.Key_1, Qt.Key.Key_2, Qt.Key.Key_3, Qt.Key.Key_4, Qt.Key.Key_5)
            if key in gear_keys:
                if event.type() == QEvent.Type.KeyPress and not event.isAutoRepeat():
                    g_idx = gear_keys.index(key)
                    if g_idx < self.cmb_wasd_gear.count():
                        self.cmb_wasd_gear.setCurrentIndex(g_idx)
                        self.append_log("INFO", f"🎮 WASD 换挡 -> {WASD_GEARS[g_idx][0]}")
                return True
            if key in (Qt.Key.Key_W, Qt.Key.Key_A, Qt.Key.Key_S, Qt.Key.Key_D):
                if not event.isAutoRepeat():
                    if event.type() == QEvent.Type.KeyPress:
                        self._wasd_pressed.add(key)
                        self._on_wasd_keys_changed()
                    elif event.type() == QEvent.Type.KeyRelease:
                        self._wasd_pressed.discard(key)
                        self._on_wasd_keys_changed()
                return True
        return super().eventFilter(watched, event)

    def _on_wasd_toggled(self, checked: bool) -> None:
        was_moving = self._wasd_moving
        self._wasd_pressed.clear()
        self._wasd_moving = False
        self._last_wasd_cmd = (0.0, 0.0)
        if checked:
            self._abort_script_queue("开启 WASD 键盘驾驶模式")
            msg = self.tracker.abort("切换至 WASD 键盘驾驶模式")
            if msg:
                self.append_log("WARN", msg)
            self._refresh_action_ui()
            self.lbl_wasd_status.setText("键盘状态: [待命] 按住 W/S 前后、A/D 转向、W+A/W+D 弧线，松手即停")
            self.lbl_wasd_status.setStyleSheet("color:#10B981;font-family:Consolas,monospace;font-weight:bold;")
            self.append_log("INFO", "🎮 已开启 WASD 键盘驾驶模式（已自动清空剧本队列并中断在途动作）")
        else:
            if was_moving and self.worker.isRunning():
                self.worker.enqueue_velocity(0.0, 0.0, silent=True)
            self.lbl_wasd_status.setText("键盘状态: [未激活]")
            self.lbl_wasd_status.setStyleSheet("color:#94A3B8;font-family:Consolas,monospace;")
            self.append_log("INFO", "已关闭 WASD 键盘驾驶模式")

    def _compute_wasd_vel(self) -> tuple:
        idx = max(0, min(len(WASD_GEARS) - 1, self.cmb_wasd_gear.currentIndex()))
        _, v_base, w_base, arc_ratio = WASD_GEARS[idx]

        w_on = Qt.Key.Key_W in self._wasd_pressed
        s_on = Qt.Key.Key_S in self._wasd_pressed
        a_on = Qt.Key.Key_A in self._wasd_pressed
        d_on = Qt.Key.Key_D in self._wasd_pressed

        vx = 0.0
        omega = 0.0
        if w_on and not s_on:
            vx = +v_base
        elif s_on and not w_on:
            vx = -v_base

        if a_on and not d_on:
            omega = +(w_base * arc_ratio if abs(vx) > 1e-4 else w_base)
        elif d_on and not a_on:
            omega = -(w_base * arc_ratio if abs(vx) > 1e-4 else w_base)

        key_names = []
        if w_on:
            key_names.append("W")
        if a_on:
            key_names.append("A")
        if s_on:
            key_names.append("S")
        if d_on:
            key_names.append("D")
        return vx, omega, "+".join(key_names) if key_names else "松手停止"

    def _on_wasd_keys_changed(self) -> None:
        if not self.chk_wasd.isChecked():
            return
        vx, omega, k_str = self._compute_wasd_vel()
        # 纠正 3：按下任何 WASD 键时立即清空上位机队列 + 车端单一司机 Abort
        if self.sequencer.active or self.sequencer.steps:
            self._abort_script_queue(f"按下 WASD ({k_str}) 键盘接管")
        msg = self.tracker.abort(f"WASD 键盘驾驶 ({k_str})")
        if msg:
            self.append_log("WARN", msg)
            self._refresh_action_ui()

        self.lbl_wasd_status.setText(
            f"按键: [{k_str}] -> vx={vx:+.2f} m/s, ω={omega:+.2f} rad/s"
        )
        if self.worker.isRunning():
            if abs(vx) > 1e-4 or abs(omega) > 1e-4:
                self._wasd_moving = True
                if (vx, omega) != self._last_wasd_cmd:
                    self._last_wasd_cmd = (vx, omega)
                    self.worker.enqueue_velocity(vx, omega, silent=False)
            else:
                if self._wasd_moving:
                    self._wasd_moving = False
                    self._last_wasd_cmd = (0.0, 0.0)
                    self.worker.enqueue_velocity(0.0, 0.0, silent=False)

    def _on_ctrl_timer_50ms(self) -> None:
        # 1) 若 WASD 处于按住状态，由 SerialLinkWorker 的 _active_mode="VEL(...)" 自动维持 20Hz 心跳；
        #    若用户在按住期间切换了档位下拉框，立即同步新档位速度
        if self.chk_wasd.isChecked() and self._wasd_pressed and self.worker.isRunning():
            vx, omega, k_str = self._compute_wasd_vel()
            if (vx, omega) != self._last_wasd_cmd:
                self._last_wasd_cmd = (vx, omega)
                self.lbl_wasd_status.setText(
                    f"按键: [{k_str}] -> vx={vx:+.2f} m/s, ω={omega:+.2f} rad/s"
                )
                self.worker.enqueue_velocity(vx, omega, silent=True)

        # 2) 检查剧本编排器 0.3s 停顿后是否该下发下一步
        if self.sequencer.active and self.worker.isRunning():
            nxt = self.sequencer.poll_next_step()
            if nxt is not None:
                idx, total, step = nxt
                self._dispatch_script_step(idx, total, step)

    # ==================== 串口与连接控制 ====================
    def _refresh_ports(self) -> None:
        cur = self.cmb_port.currentText()
        self.cmb_port.clear()
        ports = link.list_serial_ports()
        self.cmb_port.addItems(ports)
        if cur in ports:
            self.cmb_port.setCurrentText(cur)
        self.append_log("INFO", f"已刷新串口列表: {', '.join(ports)}")

    def _toggle_connection(self) -> None:
        if self.worker.isRunning():
            self._abort_script_queue("断开串口连接")
            self.worker.stop_link()
            self.worker.wait(1500)
        else:
            port = self.cmb_port.currentText().strip() or "COM6"
            use_mock = self.chk_mock.isChecked()
            self.worker.configure(port_name=port, baudrate=9600, use_mock=use_mock)
            self.worker.start()

    def _on_link_state(self, connected: bool, desc: str) -> None:
        if connected:
            self.btn_connect.setText("断开连接")
            self.btn_connect.setStyleSheet("background-color:#475569;color:#FFFFFF;padding:5px 14px;")
            self.lbl_link_badge.setText(f"● 已连接: {desc}")
            self.lbl_link_badge.setStyleSheet("color:#10B981;font-weight:bold;padding:0 8px;")
        else:
            self.btn_connect.setText("连接车端")
            self.btn_connect.setStyleSheet("background-color:#059669;color:#FFFFFF;padding:5px 14px;")
            self.lbl_link_badge.setText(f"● {desc}")
            self.lbl_link_badge.setStyleSheet("color:#94A3B8;font-weight:bold;padding:0 8px;")

    def _ensure_connected(self) -> bool:
        if not self.worker.isRunning():
            self.append_log("WARN", "尚未连接车端串口（或 Mock 仿真），请先点击顶栏『连接车端』！")
            return False
        return True

    # ==================== 剧本编排器 & 演示级指点导航 (W4 & W5) ====================
    def _refresh_seq_list_ui(self) -> None:
        self.list_seq.clear()
        for i, st in enumerate(self.sequencer.steps):
            if self.sequencer.active:
                if i < self.sequencer.current_index:
                    prefix = "✅ [已完成]"
                elif i == self.sequencer.current_index:
                    prefix = "▶ [执行中]"
                else:
                    prefix = "⏳ [待执行]"
            else:
                prefix = f"#{i+1}"
            self.list_seq.addItem(
                f"{prefix} {st.label}  (id=0x{st.action_id:02X}, param={st.param})"
            )
        if self.sequencer.active and 0 <= self.sequencer.current_index < self.list_seq.count():
            self.list_seq.setCurrentRow(self.sequencer.current_index)

    def _abort_script_queue(self, reason: str, stop_car: bool = False) -> None:
        """纠正 3：两层打断机制——第 1 层清空上位机待发队列，第 2 层由车端单一司机规则或 CMD_ACTION(0x03) 打断车端动作。"""
        was_running = self.sequencer.active
        had_steps = len(self.sequencer.steps) > 0
        self.sequencer.abort_running()
        self._nav_target_xy = None
        self.plot_panel.clear_nav_target()
        self._refresh_seq_list_ui()
        self.lbl_seq_status.setText(f"剧本队列状态: 已清空/就绪 ({reason})")
        if was_running or had_steps:
            self.append_log("WARN", f"[剧本/导航打断] 已清空上位机队列: {reason}")
        if stop_car and self.worker.isRunning():
            msg = self.tracker.abort(reason)
            if msg:
                self.append_log("WARN", msg)
            aid, param, _, label = actions.make_stop_action_payload()
            self.tracker.start(aid, param, label, self.latest_tlm)
            self._refresh_action_ui()
            self.worker.enqueue_action(aid, param, label)

    def _dispatch_script_step(self, idx: int, total: int, step: actions.ScriptStep) -> None:
        self._refresh_seq_list_ui()
        self.lbl_seq_status.setText(
            f"正在执行『{self.sequencer.script_name}』: 第 {idx+1}/{total} 步 -> {step.label}"
        )
        self.tracker.start(step.action_id, step.param, f"[{idx+1}/{total}] {step.label}", self.latest_tlm)
        self._refresh_action_ui()
        self.worker.enqueue_action(step.action_id, step.param, f"[{idx+1}/{total}] {step.label}")

    def _load_and_run_preset(self, preset_key: str) -> None:
        if not self._ensure_connected():
            return
        if self.chk_wasd.isChecked():
            self.chk_wasd.setChecked(False)
        self._nav_target_xy = None
        self.plot_panel.clear_nav_target()
        name, steps = actions.get_preset_script(preset_key)
        self.sequencer.load_steps(steps, name=name)
        self._refresh_seq_list_ui()
        first = self.sequencer.start_sequence()
        if first is not None:
            idx, total, step = first
            self.append_log("INFO", f"🎬 启动预设剧本『{name}』（共 {total} 步，每步 DONE 后停稳 0.3s）")
            self._dispatch_script_step(idx, total, step)

    def _seq_add_move_step(self) -> None:
        aid, param, _, label = actions.make_move_payload(self.spin_dist_mm.value())
        self.sequencer.add_step(aid, param, label)
        self._refresh_seq_list_ui()
        self.lbl_seq_status.setText(f"已添加步骤: {label} (当前共 {len(self.sequencer.steps)} 步)")

    def _seq_add_turn_step(self) -> None:
        aid, param, _, label = actions.make_turn_payload(self.spin_turn_deg.value())
        self.sequencer.add_step(aid, param, label)
        self._refresh_seq_list_ui()
        self.lbl_seq_status.setText(f"已添加步骤: {label} (当前共 {len(self.sequencer.steps)} 步)")

    def _seq_remove_selected(self) -> None:
        row = self.list_seq.currentRow()
        if row >= 0:
            self.sequencer.remove_step(row)
            self._refresh_seq_list_ui()

    def _seq_start_clicked(self) -> None:
        if not self._ensure_connected():
            return
        if not self.sequencer.steps:
            self.append_log("WARN", "当前剧本队列为空，请先点击『+加直行步 / +加转向步』或点击上方三大预设剧本按钮！")
            return
        if self.chk_wasd.isChecked():
            self.chk_wasd.setChecked(False)
        first = self.sequencer.start_sequence()
        if first is not None:
            idx, total, step = first
            self.append_log("INFO", f"▶ 启动自定义动作队列（共 {total} 步）")
            self._dispatch_script_step(idx, total, step)

    def _on_map_double_clicked(self, target_x_m: float, target_y_m: float) -> None:
        """W4：双击 X-Y 轨迹图任意点 (X*, Y*) -> 演示级指点导航（先转向对准 -> 等 DONE -> 再直行到达）。"""
        if not self._ensure_connected():
            return
        if self.chk_wasd.isChecked():
            self.chk_wasd.setChecked(False)

        cur_x = self.latest_tlm.x_m if self.latest_tlm else 0.0
        cur_y = self.latest_tlm.y_m if self.latest_tlm else 0.0
        cur_yaw = (
            (self.latest_tlm.imu_yaw_deg if self.latest_tlm.imu_ok else self.latest_tlm.odom_yaw_deg)
            if self.latest_tlm
            else 0.0
        )

        steps, dyaw_deg, dist_mm = actions.build_point_nav_steps(
            cur_x, cur_y, cur_yaw, target_x_m, target_y_m
        )
        if not steps:
            self.append_log("WARN", f"目标点 ({target_x_m:+.2f}, {target_y_m:+.2f})m 距离当前位置过近 (<20mm)，无需移动。")
            return

        self._nav_target_xy = (target_x_m, target_y_m)
        nav_title = f"演示级导航->({target_x_m:+.2f},{target_y_m:+.2f})m"
        self.sequencer.load_steps(steps, name=nav_title)
        self._refresh_seq_list_ui()
        first = self.sequencer.start_sequence()
        if first is not None:
            idx, total, step = first
            self.append_log(
                "INFO",
                f"🧭 [演示级导航（预期落点误差 ~5cm 量级）] 起点({cur_x:+.2f},{cur_y:+.2f})m -> 目标({target_x_m:+.2f},{target_y_m:+.2f})m: "
                f"Δyaw={dyaw_deg:+.1f}°, L={dist_mm}mm (共 {total} 步串行)",
            )
            self._dispatch_script_step(idx, total, step)

    # ==================== 单步动作按钮（触发前自动执行两层打断） ====================
    def _quick_move(self, dist_mm: int) -> None:
        self.spin_dist_mm.setValue(abs(dist_mm))
        self._trigger_move_mm(dist_mm)

    def _trigger_move_mm(self, dist_mm: int) -> None:
        if not self._ensure_connected():
            return
        self._abort_script_queue(f"手动触发直行 {dist_mm}mm")
        aid, param, _, label = actions.make_move_payload(dist_mm)
        self.tracker.start(aid, param, label, self.latest_tlm)
        self._refresh_action_ui()
        self.worker.enqueue_action(aid, param, label)

    def _trigger_turn_deg(self, angle_deg: float) -> None:
        if not self._ensure_connected():
            return
        self._abort_script_queue(f"手动触发转向 {angle_deg:+.1f}°")
        aid, param, _, label = actions.make_turn_payload(angle_deg)
        self.tracker.start(aid, param, label, self.latest_tlm)
        self._refresh_action_ui()
        self.worker.enqueue_action(aid, param, label)

    def _trigger_uturn(self) -> None:
        if not self._ensure_connected():
            return
        self._abort_script_queue("手动触发掉头 180°")
        aid, param, _, label = actions.make_uturn_payload()
        self.tracker.start(aid, param, label, self.latest_tlm)
        self._refresh_action_ui()
        self.worker.enqueue_action(aid, param, label)

    def _trigger_reset_odom(self) -> None:
        """W2：触发 TYPE 0x05 + action_id 0x06 远程里程计归零，并同步清空轨迹图。"""
        if not self._ensure_connected():
            return
        self._abort_script_queue("执行 0x06 里程计归零")
        aid, param, _, label = actions.make_reset_odom_payload()
        self.tracker.start(aid, param, label, self.latest_tlm)
        self._refresh_action_ui()
        self.worker.enqueue_action(aid, param, label)
        self.plot_panel.clear_plots()
        self.append_log("OK", "🎯 已下发 CMD_ACTION(0x06, 0) 远程里程计归零，X/Y/Yaw 已重置并清空历史轨迹。")

    def _trigger_action_stop(self) -> None:
        if not self._ensure_connected():
            return
        self._abort_script_queue("发送 CMD_ACTION(0x03) 动作停车")
        msg = self.tracker.abort("发送 CMD_ACTION(0x03) 动作停车")
        if msg:
            self.append_log("WARN", msg)
        aid, param, _, label = actions.make_stop_action_payload()
        self.tracker.start(aid, param, label, self.latest_tlm)
        self._refresh_action_ui()
        self.worker.enqueue_action(aid, param, label)

    def _trigger_manual_vel(self) -> None:
        if not self._ensure_connected():
            return
        self._abort_script_queue("发送手动 CMD_VEL")
        msg = self.tracker.abort("被 CMD_VEL 手动速度指令打断 (单一司机规则)")
        if msg:
            self.append_log("WARN", msg)
        self._refresh_action_ui()
        self.worker.enqueue_velocity(self.spin_vx.value(), self.spin_omega.value())

    def _trigger_mode(self, fusion_mode: int) -> None:
        if not self._ensure_connected():
            return
        self._abort_script_queue(f"切换融合模式 CMD_MODE({fusion_mode})")
        msg = self.tracker.abort(f"被 CMD_MODE(fusion={fusion_mode}) 打断 (单一司机规则)")
        if msg:
            self.append_log("WARN", msg)
        self._refresh_action_ui()
        self.worker.enqueue_mode(fusion_mode)

    def _trigger_timeout_test(self) -> None:
        if not self._ensure_connected():
            return
        self._abort_script_queue("触发 0.8s 断连超时测试")
        msg = self.tracker.abort("触发 0.8s 断连超时测试")
        if msg:
            self.append_log("WARN", msg)
        self._refresh_action_ui()
        self.worker.trigger_timeout_test(0.80)

    def _on_emergency_stop(self, source: str) -> None:
        self._wasd_pressed.clear()
        self._wasd_moving = False
        self._last_wasd_cmd = (0.0, 0.0)
        self._abort_script_queue(f"紧急停车 ({source})")
        msg = self.tracker.abort(f"紧急停车 ({source})")
        if msg:
            self.append_log("ERR", msg)
        self._refresh_action_ui()
        if self.worker.isRunning():
            self.worker.enqueue_stop(f"🛑 紧急停车: {source}")
        else:
            self.append_log("ERR", f"🛑 紧急停车触发 ({source})")

    def _on_raw_tab_send(self, msg_type: int, seq_override: object, data: bytes) -> None:
        if not self._ensure_connected():
            return
        if msg_type != proto.TYPE_CMD_POLL:
            self._abort_script_queue(f"原始帧工具发送 TYPE=0x{msg_type:02X}")
            msg = self.tracker.abort(f"原始帧工具发送 TYPE=0x{msg_type:02X}")
            if msg:
                self.append_log("WARN", msg)
            self._refresh_action_ui()
        self.worker.enqueue_raw_frame(msg_type, seq_override, data)

    def _refresh_action_ui(self) -> None:
        st = self.tracker.state
        color_map = {
            "IDLE": "#94A3B8",
            "RUNNING": "#00E5FF",
            "DONE": "#10B981",
            "TIMEOUT": "#F43F5E",
            "ABORTED": "#FF9100",
        }
        c = color_map.get(st, "#00E5FF")
        self.lbl_act_state.setText(f"动作状态: [{st}] {self.tracker.detail_text}")
        self.lbl_act_state.setStyleSheet(f"color:{c};font-weight:bold;")
        self.bar_action.setValue(int(round(self.tracker.progress_pct)))

    def _on_telemetry(self, tlm: proto.TelemetryExt, stats: dict) -> None:
        self.latest_tlm = tlm
        now_s = time.monotonic()

        ev = self.tracker.update_from_telemetry(tlm)
        if ev is not None:
            self.append_log(ev[0], ev[1])
            # 若剧本编排器处于激活态且当前步 DONE，推进剧本
            if self.sequencer.active:
                if self.tracker.state == "DONE":
                    finish_msg = self.sequencer.notify_step_done(now_s)
                    self._refresh_seq_list_ui()
                    if finish_msg:
                        self.lbl_seq_status.setText(finish_msg)
                        self.append_log("OK", finish_msg)
                        if self._nav_target_xy is not None:
                            tx, ty = self._nav_target_xy
                            err_cm = math.hypot(tlm.x_m - tx, tlm.y_m - ty) * 100.0
                            self.append_log(
                                "OK",
                                f"🎯 [演示级导航落点结算] 目标=({tx:+.3f}, {ty:+.3f})m | 实到=({tlm.x_m:+.3f}, {tlm.y_m:+.3f})m | 落点误差={err_cm:.2f} cm",
                            )
                            self._nav_target_xy = None
                    else:
                        self.lbl_seq_status.setText(
                            f"剧本『{self.sequencer.script_name}』第 {self.sequencer.current_index+1} 步到位，停稳 0.3s 后发下一步..."
                        )
                elif self.tracker.state in ("TIMEOUT", "ABORTED"):
                    self._abort_script_queue(f"步骤异常终止 ({self.tracker.state})")

        self._refresh_action_ui()

        # 更新数据区卡片
        self.lbl_vals["x_m"].setText(f"{tlm.x_m:+.3f} m")
        self.lbl_vals["y_m"].setText(f"{tlm.y_m:+.3f} m")
        self.lbl_vals["imu_yaw"].setText(f"{tlm.imu_yaw_deg:+.2f} °")
        self.lbl_vals["odom_yaw"].setText(f"{tlm.odom_yaw_deg:+.2f} °")
        for i, k in enumerate(("m1", "m2", "m3", "m4")):
            self.lbl_vals[k].setText(f"{tlm.rpm[i]:4d} RPM | {tlm.pwm[i]:+3d}%")

        self.lbl_vals["imu_st"].setText("OK (在线)" if tlm.imu_ok else "OFFLINE!")
        self.lbl_vals["imu_st"].setStyleSheet(
            f"color:{'#10B981' if tlm.imu_ok else '#F43F5E'};font-weight:bold;"
        )
        self.lbl_vals["fusion"].setText("1 (IMU主融合)" if tlm.fusion_mode == 1 else "0 (纯编码器)")
        hdg_str = "ACTIVE" if tlm.heading_active else "IDLE"
        rej_str = "REJECT!" if tlm.cmd_rejected else "OK"
        self.lbl_vals["hdg_st"].setText(f"{hdg_str} | {rej_str}")
        self.lbl_vals["to_flag"].setText("TIMEOUT!" if tlm.timed_out else "正常 (OK)")
        self.lbl_vals["to_flag"].setStyleSheet(
            f"color:{'#F43F5E' if tlm.timed_out else '#10B981'};font-weight:bold;"
        )
        self.lbl_vals["drop_cnt"].setText(str(tlm.drop_count))
        self.lbl_vals["to_cnt"].setText(str(tlm.timeout_count))
        self.lbl_vals["local_to"].setText(
            f"{stats['local_timeout']} ({stats['loss_pct']:.1f}%)"
        )
        self.lbl_vals["rtt_hz"].setText(
            f"{stats['rtt_ms']:.1f} ms | {stats['hz']:.1f} Hz"
        )

        # 更新三合一实时曲线
        self.plot_panel.append_telemetry(tlm, now_s)

    def append_log(self, level: str, msg: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        prefix = {"OK": "✅", "WARN": "⚠️", "ERR": "🛑", "INFO": "ℹ️"}.get(level, "•")
        self.txt_log.appendPlainText(f"[{ts}] {prefix} [{level}] {msg}")

    def closeEvent(self, event) -> None:
        self._ctrl_timer.stop()
        if self.worker.isRunning():
            self.worker.stop_link()
            self.worker.wait(1500)
        super().closeEvent(event)
