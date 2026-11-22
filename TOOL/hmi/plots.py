"""阶段 3（S3-DEMO v2/v3）三合一实时可视化曲线区：X-Y 轨迹（含车头朝向射线与双击地图演示级导航）、Yaw 双曲线、四轮 RPM."""

from collections import deque
import math
from typing import Optional

try:
    from PySide6.QtCore import Qt, Signal
    from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget
except ImportError:
    from PyQt6.QtCore import Qt, pyqtSignal as Signal  # type: ignore
    from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget  # type: ignore

import pyqtgraph as pg

import protocol_ext as proto

pg.setConfigOptions(antialias=True, background="#0D1322", foreground="#94A3B8")


class TelemetryPlotPanel(QWidget):
    """三图联动实时图表组件（X-Y 轨迹+车头朝向矢量+双击地图导航 / Yaw 双曲线 / 四轮 RPM）。"""

    sig_map_double_clicked = Signal(float, float)  # (target_x_m, target_y_m)

    def __init__(self, max_points: int = 300, parent=None) -> None:
        super().__init__(parent)
        self.max_points = max_points
        self.t0 = None
        self._cur_x = 0.0
        self._cur_y = 0.0
        self._cur_yaw_deg = 0.0
        self._nav_target: Optional[tuple] = None

        self.t_buf = deque(maxlen=max_points)
        self.x_buf = deque(maxlen=max_points)
        self.y_buf = deque(maxlen=max_points)
        self.imu_yaw_buf = deque(maxlen=max_points)
        self.odom_yaw_buf = deque(maxlen=max_points)
        self.rpm_bufs = [deque(maxlen=max_points) for _ in range(4)]

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        top_row = QHBoxLayout()
        # 1. X-Y 平面轨迹图（支持车头朝向矢量 + 双击地图演示级指点导航）
        self.plot_xy = pg.PlotWidget(
            title="<span style='color:#00E5FF;font-weight:bold;'>X-Y 轨迹 (m) [双击地图: 演示级导航 ~5cm]</span>"
        )
        self.plot_xy.showGrid(x=True, y=True, alpha=0.25)
        self.plot_xy.setLabel("bottom", "X (m)")
        self.plot_xy.setLabel("left", "Y (m)")
        self.plot_xy.setAspectLocked(True)
        self.plot_xy.setXRange(-0.5, 2.0, padding=0.05)
        self.plot_xy.setYRange(-1.0, 1.5, padding=0.05)

        self.curve_xy = self.plot_xy.plot(pen=pg.mkPen("#00E5FF", width=2.5), name="轨迹")
        self.scatter_origin = self.plot_xy.plot(
            [0.0], [0.0], pen=None, symbol="o", symbolBrush="#10B981", symbolSize=9, name="起点"
        )
        # 导航目标虚线与靶标
        self.curve_nav_line = self.plot_xy.plot(
            [], [], pen=pg.mkPen("#F43F5E", width=1.6, style=Qt.PenStyle.DashLine)
        )
        self.scatter_nav_target = self.plot_xy.plot(
            [],
            [],
            pen=None,
            symbol="x",
            symbolPen=pg.mkPen("#F43F5E", width=2.5),
            symbolBrush="#F43F5E",
            symbolSize=14,
            name="导航目标",
        )
        # 车体三角与车头朝向射线（W4：实时指示 ImuYaw 朝向）
        self.curve_heading_ray = self.plot_xy.plot(
            [0.0, 0.22],
            [0.0, 0.0],
            pen=pg.mkPen("#FACC15", width=3.0),
            name="车头朝向射线",
        )
        self.scatter_car = self.plot_xy.plot(
            [0.0], [0.0], pen=None, symbol="t1", symbolBrush="#FF9100", symbolSize=13, name="车体位置"
        )
        self.scatter_heading_tip = self.plot_xy.plot(
            [0.22], [0.0], pen=None, symbol="o", symbolBrush="#FACC15", symbolSize=7
        )

        self.plot_xy.scene().sigMouseClicked.connect(self._on_xy_mouse_clicked)
        top_row.addWidget(self.plot_xy, 1)

        # 2. 航向角双曲线 (IMU 青色 vs 编码器橙色)
        self.plot_yaw = pg.PlotWidget(
            title="<span style='color:#00E5FF;font-weight:bold;'>航向角双曲线：IMU(青) vs 里程计(橙) (°)</span>"
        )
        self.plot_yaw.showGrid(x=True, y=True, alpha=0.25)
        self.plot_yaw.setLabel("bottom", "时间 (s)")
        self.plot_yaw.setLabel("left", "Yaw (°)")
        self.plot_yaw.addLegend(offset=(10, 10))
        self.curve_imu_yaw = self.plot_yaw.plot(
            pen=pg.mkPen("#00E5FF", width=2.4), name="IMU Yaw (青)"
        )
        self.curve_odom_yaw = self.plot_yaw.plot(
            pen=pg.mkPen("#FF9100", width=2.0, style=Qt.PenStyle.DashLine),
            name="Odom Yaw (橙)",
        )
        top_row.addWidget(self.plot_yaw, 1)
        layout.addLayout(top_row, 1)

        # 3. 四轮 RPM 实时曲线
        self.plot_rpm = pg.PlotWidget(
            title="<span style='color:#38BDF8;font-weight:bold;'>四轮转速实时曲线 M1~M4 (RPM)</span>"
        )
        self.plot_rpm.showGrid(x=True, y=True, alpha=0.25)
        self.plot_rpm.setLabel("bottom", "时间 (s)")
        self.plot_rpm.setLabel("left", "RPM")
        self.plot_rpm.addLegend(offset=(10, 10))
        rpm_colors = ["#00E5FF", "#FF9100", "#10B981", "#F43F5E"]
        rpm_names = ["M1(左前)", "M2(右前)", "M3(左后)", "M4(右后)"]
        self.curves_rpm = [
            self.plot_rpm.plot(pen=pg.mkPen(c, width=1.8), name=n)
            for c, n in zip(rpm_colors, rpm_names)
        ]
        layout.addWidget(self.plot_rpm, 1)

        btn_bar = QHBoxLayout()
        self.lbl_nav_hint = QLabel(
            "💡 提示：双击左上 X-Y 轨迹图任意坐标点 (X*, Y*) 可触发『演示级导航（先转向对准 → 再直行到达，预期落点误差 ~5cm 量级）』"
        )
        self.lbl_nav_hint.setStyleSheet("color:#FACC15;font-size:12px;font-weight:bold;")
        btn_bar.addWidget(self.lbl_nav_hint)
        btn_bar.addStretch()
        self.btn_clear = QPushButton("清空历史曲线")
        self.btn_clear.setFixedWidth(130)
        self.btn_clear.clicked.connect(self.clear_plots)
        btn_bar.addWidget(self.btn_clear)
        layout.addLayout(btn_bar)

    def _on_xy_mouse_clicked(self, ev) -> None:
        if ev.double() and ev.button() == Qt.MouseButton.LeftButton:
            vb = self.plot_xy.getPlotItem().vb
            if vb.sceneBoundingRect().contains(ev.scenePos()):
                pt = vb.mapSceneToView(ev.scenePos())
                tx = float(pt.x())
                ty = float(pt.y())
                self.set_nav_target(tx, ty)
                self.sig_map_double_clicked.emit(tx, ty)

    def set_nav_target(self, tx: float, ty: float) -> None:
        self._nav_target = (tx, ty)
        self.scatter_nav_target.setData([tx], [ty])
        self.curve_nav_line.setData([self._cur_x, tx], [self._cur_y, ty])

    def clear_nav_target(self) -> None:
        self._nav_target = None
        self.scatter_nav_target.setData([], [])
        self.curve_nav_line.setData([], [])

    def _update_car_heading_graphic(self, x_m: float, y_m: float, yaw_deg: float) -> None:
        self._cur_x = x_m
        self._cur_y = y_m
        self._cur_yaw_deg = yaw_deg
        ray_len = 0.22
        yaw_rad = math.radians(yaw_deg)
        tip_x = x_m + ray_len * math.cos(yaw_rad)
        tip_y = y_m + ray_len * math.sin(yaw_rad)
        self.scatter_car.setData([x_m], [y_m])
        self.curve_heading_ray.setData([x_m, tip_x], [y_m, tip_y])
        self.scatter_heading_tip.setData([tip_x], [tip_y])
        if self._nav_target is not None:
            self.curve_nav_line.setData([x_m, self._nav_target[0]], [y_m, self._nav_target[1]])

    def clear_plots(self) -> None:
        self.t0 = None
        self.t_buf.clear()
        self.x_buf.clear()
        self.y_buf.clear()
        self.imu_yaw_buf.clear()
        self.odom_yaw_buf.clear()
        for b in self.rpm_bufs:
            b.clear()
        self.curve_xy.setData([], [])
        self.clear_nav_target()
        self._update_car_heading_graphic(0.0, 0.0, 0.0)
        self.curve_imu_yaw.setData([], [])
        self.curve_odom_yaw.setData([], [])
        for c in self.curves_rpm:
            c.setData([], [])

    def append_telemetry(self, tlm: proto.TelemetryExt, now_s: float) -> None:
        if self.t0 is None:
            self.t0 = now_s
        t_rel = now_s - self.t0

        self.t_buf.append(t_rel)
        self.x_buf.append(tlm.x_m)
        self.y_buf.append(tlm.y_m)
        self.imu_yaw_buf.append(tlm.imu_yaw_deg)
        self.odom_yaw_buf.append(tlm.odom_yaw_deg)
        for i in range(4):
            self.rpm_bufs[i].append(tlm.rpm[i])

        t_list = list(self.t_buf)
        x_list = list(self.x_buf)
        y_list = list(self.y_buf)

        self.curve_xy.setData(x_list, y_list)
        yaw_use = tlm.imu_yaw_deg if tlm.imu_ok else tlm.odom_yaw_deg
        self._update_car_heading_graphic(tlm.x_m, tlm.y_m, yaw_use)
        self.curve_imu_yaw.setData(t_list, list(self.imu_yaw_buf))
        self.curve_odom_yaw.setData(t_list, list(self.odom_yaw_buf))
        for i in range(4):
            self.curves_rpm[i].setData(t_list, list(self.rpm_bufs[i]))
