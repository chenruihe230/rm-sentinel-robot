"""阶段 3（S3-DEMO v2/v3）「原始帧工具」标签页：手填 TYPE/SEQ/DATA 十六进制发帧、CRC8 预览、HEX/ASCII 历史与解析."""

try:
    from PySide6.QtCore import Signal
    from PySide6.QtWidgets import (
        QCheckBox,
        QGridLayout,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QPlainTextEdit,
        QPushButton,
        QVBoxLayout,
        QWidget,
    )
except ImportError:
    from PyQt6.QtCore import pyqtSignal as Signal  # type: ignore
    from PyQt6.QtWidgets import (  # type: ignore
        QCheckBox,
        QGridLayout,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QPlainTextEdit,
        QPushButton,
        QVBoxLayout,
        QWidget,
    )

import protocol_ext as proto


class RawFrameToolTab(QWidget):
    """替代传统串口助手的协议级原始帧收发与解析面板。"""

    sig_send_raw = Signal(int, object, bytes)  # (type_u8, seq_override|None, data_bytes)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._history_count = 0

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)

        # 1. 手动组帧区
        grp_build = QGroupBox("手动组帧发送（自动追加帧头 AA 55、CRC8、帧尾 0D 0A）")
        grid = QGridLayout(grp_build)

        grid.addWidget(QLabel("TYPE (HEX 1B):"), 0, 0)
        self.ed_type = QLineEdit("05")
        self.ed_type.setFixedWidth(70)
        grid.addWidget(self.ed_type, 0, 1)

        grid.addWidget(QLabel("SEQ (HEX 1B):"), 0, 2)
        self.ed_seq = QLineEdit("01")
        self.ed_seq.setFixedWidth(70)
        grid.addWidget(self.ed_seq, 0, 3)

        self.chk_auto_seq = QCheckBox("使用会话自动递增 SEQ")
        self.chk_auto_seq.setChecked(True)
        grid.addWidget(self.chk_auto_seq, 0, 4)

        grid.addWidget(QLabel("DATA (HEX 空格分隔):"), 1, 0)
        self.ed_data = QLineEdit("01 14 05")
        self.ed_data.setPlaceholderText("例如: 01 14 05 (前进1300mm) 或 06 00 00 (里程计归零)")
        grid.addWidget(self.ed_data, 1, 1, 1, 4)

        self.btn_send = QPushButton("发送原始帧 (Send Frame)")
        self.btn_send.setStyleSheet(
            "background-color:#0284C7;color:#FFFFFF;font-weight:bold;padding:6px 14px;border-radius:4px;"
        )
        self.btn_send.clicked.connect(self._on_send_clicked)
        grid.addWidget(self.btn_send, 1, 5)

        grid.addWidget(QLabel("完整帧预览:"), 2, 0)
        self.lbl_preview = QLabel("")
        self.lbl_preview.setStyleSheet("color:#00E5FF;font-family:Consolas,monospace;font-weight:bold;")
        grid.addWidget(self.lbl_preview, 2, 1, 1, 5)

        self.ed_type.textChanged.connect(self._update_preview)
        self.ed_seq.textChanged.connect(self._update_preview)
        self.ed_data.textChanged.connect(self._update_preview)
        root.addWidget(grp_build)

        # 2. 常用帧快捷按钮区
        grp_presets = QGroupBox("常用帧一键填入 / 发送")
        preset_layout = QHBoxLayout(grp_presets)
        presets = [
            ("POLL (0x01)", "01", ""),
            ("前进 1.3m (05 01 14 05)", "05", "01 14 05"),
            ("后退 0.5m (05 01 0C FE)", "05", "01 0C FE"),
            ("左转 90° (05 02 84 03)", "05", "02 84 03"),
            ("右转 90° (05 02 7C FC)", "05", "02 7C FC"),
            ("掉头 180° (05 04 00 00)", "05", "04 00 00"),
            ("里程计归零 (05 06 00 00)", "05", "06 00 00"),
            ("动作停车 (05 03 00 00)", "05", "03 00 00"),
            ("急停 STOP (0x03)", "03", ""),
            ("IMU融合 (04 01)", "04", "01"),
            ("纯编码器 (04 00)", "04", "00"),
        ]
        for title, t_hex, d_hex in presets:
            btn = QPushButton(title)
            btn.clicked.connect(lambda _=False, th=t_hex, dh=d_hex: self._apply_preset(th, dh))
            preset_layout.addWidget(btn)
        root.addWidget(grp_presets)

        # 3. 过滤与显示选项栏
        opt_bar = QHBoxLayout()
        self.chk_only_manual = QCheckBox("仅记录手动发送与应答（过滤后台 20Hz 自动 POLL 刷屏）")
        self.chk_only_manual.setChecked(True)
        opt_bar.addWidget(self.chk_only_manual)

        self.chk_show_ascii = QCheckBox("同时显示 ASCII 可见字符对照")
        self.chk_show_ascii.setChecked(False)
        opt_bar.addWidget(self.chk_show_ascii)

        opt_bar.addStretch()
        btn_clear = QPushButton("清空收发历史")
        btn_clear.clicked.connect(self._clear_history)
        opt_bar.addWidget(btn_clear)
        root.addLayout(opt_bar)

        # 4. 最新一帧深度解析区 & 收发历史日志区
        grp_parse = QGroupBox("最新手动/选中帧协议拆解详情")
        parse_v = QVBoxLayout(grp_parse)
        self.txt_breakdown = QPlainTextEdit()
        self.txt_breakdown.setReadOnly(True)
        self.txt_breakdown.setMaximumHeight(125)
        self.txt_breakdown.setStyleSheet("font-family:Consolas,monospace;color:#38BDF8;background:#090D16;")
        parse_v.addWidget(self.txt_breakdown)
        root.addWidget(grp_parse)

        grp_hist = QGroupBox("原始帧收发历史 (HEX / ASCII / 解析)")
        hist_v = QVBoxLayout(grp_hist)
        self.txt_history = QPlainTextEdit()
        self.txt_history.setReadOnly(True)
        self.txt_history.setMaximumBlockCount(600)
        self.txt_history.setStyleSheet("font-family:Consolas,monospace;color:#E2E8F0;background:#090D16;")
        hist_v.addWidget(self.txt_history)
        root.addWidget(grp_hist, 1)

        self._update_preview()

    def _parse_inputs(self) -> tuple:
        t_val = int(self.ed_type.text().strip() or "0", 16) & 0xFF
        s_val = int(self.ed_seq.text().strip() or "0", 16) & 0xFF
        d_str = self.ed_data.text().strip()
        d_bytes = bytes.fromhex(d_str) if d_str else b""
        return t_val, s_val, d_bytes

    def _update_preview(self) -> None:
        try:
            t_val, s_val, d_bytes = self._parse_inputs()
            frame = proto.build_raw_frame(t_val, s_val, d_bytes)
            crc = frame[-3]
            self.lbl_preview.setText(
                f"{frame.hex(' ').upper()}   (总长 {len(frame)}B, CRC8=0x{crc:02X})"
            )
        except Exception as exc:
            self.lbl_preview.setText(f"[HEX 格式错误] {exc}")

    def _apply_preset(self, t_hex: str, d_hex: str) -> None:
        self.ed_type.setText(t_hex)
        self.ed_data.setText(d_hex)
        self._update_preview()
        self._on_send_clicked()

    def _on_send_clicked(self) -> None:
        try:
            t_val, s_val, d_bytes = self._parse_inputs()
        except Exception as exc:
            self.txt_breakdown.setPlainText(f"[发送失败] HEX 输入不合法: {exc}")
            return

        seq_override = None if self.chk_auto_seq.isChecked() else s_val
        self.sig_send_raw.emit(t_val, seq_override, d_bytes)
        if not self.chk_auto_seq.isChecked():
            self.ed_seq.setText(f"{(s_val + 1) & 0xFF:02X}")

    def _clear_history(self) -> None:
        self._history_count = 0
        self.txt_history.clear()
        self.txt_breakdown.clear()

    def on_raw_frame(
        self,
        direction: str,
        ts_str: str,
        raw: bytes,
        breakdown: str,
        is_manual: bool,
    ) -> None:
        if self.chk_only_manual.isChecked() and not is_manual:
            return

        hex_str = raw.hex(" ").upper()
        line = f"[{ts_str}] {direction} ({len(raw):2d}B) | HEX: {hex_str}"
        if self.chk_show_ascii.isChecked():
            ascii_str = "".join(chr(b) if 32 <= b <= 126 else "." for b in raw)
            line += f" | ASCII: {ascii_str}"

        self.txt_history.appendPlainText(line)
        if is_manual or direction == "RX":
            self.txt_breakdown.setPlainText(f"[{ts_str} {direction}]\n{breakdown}")
