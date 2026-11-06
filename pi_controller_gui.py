#!/usr/bin/env python3
"""
PI Multi-Controller Stage GUI
==============================
Costanza Lincetto (& Claude) — FAU

Controllers : C-663.12 (×3), C-863.12 (×4), E-873.1AT (×6)
Stages      : L-509 (×2), L-310 (×1), M-110 (×4), N-472 piezo (×6)

Requirements
------------
    pip install PyQt5 pipython

Usage
-----
    python pi_controller_gui.py           # real hardware
    python pi_controller_gui.py --demo    # simulation / no hardware needed

Serial numbers
--------------
Fill in the `serial` field in CONTROLLERS for each controller that shares a
model number with another (e.g. the three C-663.12 units).  Leave it empty
("") only if you have a single unit of that model or if PIPython can resolve
the device unambiguously.  You can find the serial numbers printed on the
controller chassis or by running:

from pipython import GCSDevice

for model in ["C-663.12", "C-863.12", "E-873.1AT"]:
    d = GCSDevice(model)
    devices = d.EnumerateUSB(controllername=model)
    print(f"\n{model}:")
    for dev in devices:
        print(f"  {dev}")
        
"""

import sys
import time
import random
import argparse
from dataclasses import dataclass, field
from typing import Optional, List

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGroupBox, QLabel, QPushButton, QDoubleSpinBox, QScrollArea,
    QFrame, QStatusBar, QMessageBox, QSizePolicy, QTabWidget,
    QAction, QSpacerItem,
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QPalette, QColor

# ─── PIPython ──────────────────────────────────────────────────────────────
try:
    from pipython import GCSDevice, GCSError          # type: ignore
    HAS_PIPYTHON = True
except ImportError:
    HAS_PIPYTHON = False


# ═══════════════════════════════════════════════════════════════════════════
# Controller configuration
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class ControllerConfig:
    display_name: str   # Name shown in GUI
    controller:   str   # PI controller model string (used by PIPython)
    stage:        str   # Stage / piezo model (display only)
    unit:         str   # Position unit label
    pos_min:      float # Minimum travel limit
    pos_max:      float # Maximum travel limit
    vel_default:  float # Default velocity (unit/s)
    vel_max:      float # Maximum velocity
    step_default: float # Default step size
    decimals:     int   # Decimal places shown for position
    serial:       str = ""   # ← FILL IN USB serial number to distinguish units of same model
    axis_label:   str = ""   # ← FILL IN axis/movement label shown in GUI, e.g. "X", "Z", "Tip"



# ┌─────────────────────────────────────────────────────────────────────────┐
# │  Edit ONLY the `serial` fields once you know each controller's SN.     │
# └─────────────────────────────────────────────────────────────────────────┘
CONTROLLERS: List[ControllerConfig] = [

    # ── C-663.12 → L-509.021100V6  (×2, travel ≈ 200 mm) ─────────────────
    ControllerConfig("L-509 (x)",  "C-663.12", "L-509.021100V6",
                     unit="mm", pos_min=0, pos_max=200,
                     vel_default=5.0,  vel_max=50.0,  step_default=1.0,
                     decimals=4,  serial=""),   # ← enter SN e.g. "0123456789"
    ControllerConfig("L-509 (y)",  "C-663.12", "L-509.021100V6",
                     unit="mm", pos_min=0, pos_max=200,
                     vel_default=5.0,  vel_max=50.0,  step_default=1.0,
                     decimals=4,  serial=""),

    # ── C-663.12 → L-310.021211V6  (×1, travel ≈ 100 mm) ─────────────────
    ControllerConfig("L-310 (z)",     "C-663.12", "L-310.021211V6",
                     unit="mm", pos_min=0, pos_max=100,
                     vel_default=2.0,  vel_max=25.0,  step_default=1.0,
                     decimals=4,  serial=""),

    # ── C-863.12 → M-110.1VG1  (×4, travel = 5 mm) ────────────────────────
    ControllerConfig("M-110 (x - bottom mirror)",  "C-863.12", "M-110.1VG1",
                     unit="mm", pos_min=0, pos_max=5,
                     vel_default=0.5,  vel_max=5.0,   step_default=0.1,
                     decimals=5,  serial=""),
    ControllerConfig("M-110 (y - bottom mirror)",  "C-863.12", "M-110.1VG1",
                     unit="mm", pos_min=0, pos_max=5,
                     vel_default=0.5,  vel_max=5.0,   step_default=0.1,
                     decimals=5,  serial=""),
    ControllerConfig("M-110 (x - sample)",  "C-863.12", "M-110.1VG1",
                     unit="mm", pos_min=0, pos_max=5,
                     vel_default=0.5,  vel_max=5.0,   step_default=0.1,
                     decimals=5,  serial=""),
    ControllerConfig("M-110 (y - sample)",  "C-863.12", "M-110.1VG1",
                     unit="mm", pos_min=0, pos_max=5,
                     vel_default=0.5,  vel_max=5.0,   step_default=0.1,
                     decimals=5,  serial=""),

    # ── E-873.1AT → N-472.11V  (×6, travel ≈ 0.1 mm = 100 µm) ───────────
    ControllerConfig("N-472 #1 (bottom mirror)",  "E-873.1AT", "N-472.11V",
                     unit="mm", pos_min=0, pos_max=0.1,
                     vel_default=0.01, vel_max=0.033,  step_default=0.001,
                     decimals=6,  serial=""),
    ControllerConfig("N-472 #2 (bottom mirror)",  "E-873.1AT", "N-472.11V",
                     unit="mm", pos_min=0, pos_max=0.1,
                     vel_default=0.01, vel_max=0.033,  step_default=0.001,
                     decimals=6,  serial=""),
    ControllerConfig("N-472 #3 (bottom mirror)",  "E-873.1AT", "N-472.11V",
                     unit="mm", pos_min=0, pos_max=0.1,
                     vel_default=0.01, vel_max=0.033,  step_default=0.001,
                     decimals=6,  serial=""),
    ControllerConfig("N-472 #4 (top mirror)",  "E-873.1AT", "N-472.11V",
                     unit="mm", pos_min=0, pos_max=0.1,
                     vel_default=0.01, vel_max=0.033,  step_default=0.001,
                     decimals=6,  serial=""),
    ControllerConfig("N-472 #5 (top mirror)",  "E-873.1AT", "N-472.11V",
                     unit="mm", pos_min=0, pos_max=0.1,
                     vel_default=0.01, vel_max=0.033,  step_default=0.001,
                     decimals=6,  serial=""),
    ControllerConfig("N-472 #6 (top mirror)",  "E-873.1AT", "N-472.11V",
                     unit="mm", pos_min=0, pos_max=0.1,
                     vel_default=0.01, vel_max=0.033,  step_default=0.001,
                     decimals=6,  serial=""),
]

# Tab groups:  name → indices into CONTROLLERS
GROUPS = {
    "L-509, L-310  (C-663.12)":  [[0, 1, 2]],
    #"L-310  (C-663.12)":  [2],
    "M-110  (C-863.12)":  [[3, 4],      # bottom mirror - row 1
                           [5, 6]],     # sample - row 2
    "N-472  (E-873.1AT)": [[7, 8, 9],       # bottom mirror — row 1
                           [10, 11, 12]],   # top mirror   — row 2
}

AXIS = "1"   # All controllers here are single-axis; change if needed


# ═══════════════════════════════════════════════════════════════════════════
# Backend — real hardware
# ═══════════════════════════════════════════════════════════════════════════

class HardwareBackend:
    """Thin wrapper around PIPython GCSDevice for one controller."""

    def __init__(self, config: ControllerConfig):
        self.config = config
        self.device: Optional[GCSDevice] = None
        self.connected = False
        self._cached_pos  = 0.0
        self._cached_vel  = config.vel_default

    # ── Connection ──────────────────────────────────────────────────────────
    def connect(self) -> bool:
        try:
            self.device = GCSDevice(self.config.controller)
            sn = self.config.serial.strip()
            if sn:
                self.device.ConnectUSB(sn)
            else:
                # Fall back to model-name lookup (works for single units)
                self.device.ConnectUSB(self.config.controller)
            self.connected = True
            self._cached_pos = self._read_pos()
            self._cached_vel = self._read_vel()
            return True
        except Exception as exc:
            print(f"[{self.config.display_name}] Connect error: {exc}")
            self.device = None
            self.connected = False
            return False

    def disconnect(self):
        if self.device:
            try:
                self.device.CloseConnection()
            except Exception:
                pass
        self.device = None
        self.connected = False

    # ── Queries ─────────────────────────────────────────────────────────────
    def _read_pos(self) -> float:
        try:
            return self.device.qPOS(AXIS)[AXIS]
        except Exception:
            return self._cached_pos

    def _read_vel(self) -> float:
        try:
            return self.device.qVEL(AXIS)[AXIS]
        except Exception:
            return self._cached_vel

    def get_position(self) -> float:
        if not self.connected:
            return self._cached_pos
        self._cached_pos = self._read_pos()
        return self._cached_pos

    def get_velocity(self) -> float:
        if not self.connected:
            return self._cached_vel
        self._cached_vel = self._read_vel()
        return self._cached_vel

    def is_moving(self) -> bool:
        if not self.connected:
            return False
        try:
            return bool(self.device.IsMoving(AXIS))
        except Exception:
            return False

    # ── Commands ────────────────────────────────────────────────────────────
    def move_absolute(self, position: float):
        if not self.connected:
            return
        try:
            self.device.MOV(AXIS, position)
        except Exception as exc:
            print(f"[{self.config.display_name}] MOV error: {exc}")

    def move_relative(self, step: float):
        if not self.connected:
            return
        try:
            self.device.MVR(AXIS, step)
        except Exception as exc:
            print(f"[{self.config.display_name}] MVR error: {exc}")

    def set_velocity(self, velocity: float):
        if not self.connected:
            return
        try:
            self.device.VEL(AXIS, velocity)
            self._cached_vel = velocity
        except Exception as exc:
            print(f"[{self.config.display_name}] VEL error: {exc}")

    def halt(self):
        if not self.connected:
            return
        try:
            self.device.HLT(AXIS)
        except Exception:
            try:
                self.device.STP()
            except Exception:
                pass


# ═══════════════════════════════════════════════════════════════════════════
# Backend — demo / simulation
# ═══════════════════════════════════════════════════════════════════════════

class DemoBackend:
    """Simulated controller — mimics movement at the configured velocity."""

    def __init__(self, config: ControllerConfig):
        self.config    = config
        self.connected = False
        self._pos      = (config.pos_min + config.pos_max) / 2.0
        self._target   = self._pos
        self._vel      = config.vel_default
        self._moving   = False
        self._t_last   = time.monotonic()

    def connect(self) -> bool:
        time.sleep(0.15)          # simulate USB handshake
        self.connected = True
        return True

    def disconnect(self):
        self.connected = False

    # ── Simulation step ─────────────────────────────────────────────────────
    def _tick(self):
        now = time.monotonic()
        dt  = now - self._t_last
        self._t_last = now
        if not self._moving:
            return
        diff = self._target - self._pos
        move = self._vel * dt * (1 if diff > 0 else -1)
        if abs(move) >= abs(diff):
            self._pos    = self._target
            self._moving = False
        else:
            self._pos += move

    # ── Queries ─────────────────────────────────────────────────────────────
    def get_position(self) -> float:
        self._tick()
        noise = random.gauss(0, 1e-7)    # tiny realistic noise
        return self._pos + noise

    def get_velocity(self) -> float:
        return self._vel

    def is_moving(self) -> bool:
        self._tick()
        return self._moving

    # ── Commands ────────────────────────────────────────────────────────────
    def move_absolute(self, position: float):
        position     = max(self.config.pos_min, min(self.config.pos_max, position))
        self._target = position
        self._moving = True
        self._t_last = time.monotonic()

    def move_relative(self, step: float):
        self.move_absolute(self._pos + step)

    def set_velocity(self, velocity: float):
        self._vel = min(max(velocity, 1e-6), self.config.vel_max)

    def halt(self):
        self._target = self._pos
        self._moving = False


# ═══════════════════════════════════════════════════════════════════════════
# StatusLED — colored dot
# ═══════════════════════════════════════════════════════════════════════════

class StatusLED(QLabel):
    _COLORS = {
        "disconnected": "#555566",
        "connected":    "#33bb44",
        "moving":       "#ffaa00",
        "error":        "#cc2233",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(13, 13)
        self.set_state("disconnected")

    def set_state(self, state: str):
        color = self._COLORS.get(state, "#555566")
        self.setStyleSheet(
            f"background:{color}; border-radius:6px; border:1px solid rgba(0,0,0,.35);"
        )
        self.setToolTip(state.capitalize())


# ═══════════════════════════════════════════════════════════════════════════
# ControllerCard widget
# ═══════════════════════════════════════════════════════════════════════════

class ControllerCard(QFrame):
    """One card per controller — shows position and exposes all controls."""

    CARD_W = 330

    def __init__(self, config: ControllerConfig, backend, parent=None):
        super().__init__(parent)
        self.config  = config
        self.backend = backend
        self.setFixedWidth(self.CARD_W)
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet(
            "ControllerCard { border: 1px solid #3a3a4e; border-radius: 6px; "
            "background: #1e1e2c; }"
        )
        self._build_ui()

    # ── UI construction ─────────────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 10)
        root.setSpacing(6)

        # Header ─────────────────────────────────────────────────────────────
        hdr = QHBoxLayout()
        self.led = StatusLED()
        hdr.addWidget(self.led)
        hdr.addSpacing(4)

        name = QLabel(self.config.display_name)
        f = QFont(); f.setBold(True); f.setPointSize(10)
        name.setFont(f)
        hdr.addWidget(name)
        hdr.addStretch()

        self.btn_connect = QPushButton("Connect")
        self.btn_connect.setCheckable(True)
        self.btn_connect.setFixedWidth(82)
        self.btn_connect.clicked.connect(self._on_connect_clicked)
        hdr.addWidget(self.btn_connect)
        root.addLayout(hdr)

        # Sub-title ──────────────────────────────────────────────────────────
        sub = QLabel(f"{self.config.controller}  →  {self.config.stage}")
        sub.setStyleSheet("color: #7a7a9a; font-size: 8pt;")
        root.addWidget(sub)

        # Position display ───────────────────────────────────────────────────
        pos_frame = QFrame()
        pos_frame.setStyleSheet(
            "background:#111120; border-radius:4px; border:1px solid #333350;"
        )
        pfl = QHBoxLayout(pos_frame)
        pfl.setContentsMargins(8, 5, 8, 5)

        lbl_pos = QLabel("Position")
        lbl_pos.setStyleSheet("color:#6e6e8a; font-size:8pt; background:transparent; border:none;")
        pfl.addWidget(lbl_pos)

        self.lbl_value = QLabel("---")
        self.lbl_value.setStyleSheet(
            "color:#66ff88; font-family:monospace; font-size:15pt;"
            "font-weight:bold; background:transparent; border:none;"
        )
        self.lbl_value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        pfl.addWidget(self.lbl_value, 1)

        lbl_unit = QLabel(self.config.unit)
        lbl_unit.setStyleSheet("color:#6e6e8a; font-size:8pt; background:transparent; border:none;")
        pfl.addWidget(lbl_unit)
        root.addWidget(pos_frame)

        # Separator ──────────────────────────────────────────────────────────
        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color:#2e2e42;")
        root.addWidget(sep)

        # Target (absolute move) ─────────────────────────────────────────────
        row_target = QHBoxLayout()
        row_target.addWidget(self._lbl("Target:"))
        self.spin_target = self._dspin(
            self.config.pos_min, self.config.pos_max,
            (self.config.pos_min + self.config.pos_max) / 2,
            self.config.decimals, self.config.unit
        )
        row_target.addWidget(self.spin_target, 1)
        self.btn_move = QPushButton("Move")
        self.btn_move.setFixedWidth(52)
        self.btn_move.setEnabled(False)
        self.btn_move.clicked.connect(self._on_move)
        row_target.addWidget(self.btn_move)
        root.addLayout(row_target)

        # Step ───────────────────────────────────────────────────────────────
        row_step = QHBoxLayout()
        row_step.addWidget(self._lbl("Step:"))
        self.spin_step = self._dspin(
            10 ** (-self.config.decimals),
            self.config.pos_max - self.config.pos_min,
            self.config.step_default,
            self.config.decimals, self.config.unit,
            single_step=self.config.step_default / 10
        )
        row_step.addWidget(self.spin_step, 1)
        self.btn_minus = QPushButton("−")
        self.btn_minus.setFixedWidth(32)
        self.btn_minus.setEnabled(False)
        self.btn_minus.clicked.connect(lambda: self._on_step(-1))
        row_step.addWidget(self.btn_minus)
        self.btn_plus = QPushButton("+")
        self.btn_plus.setFixedWidth(32)
        self.btn_plus.setEnabled(False)
        self.btn_plus.clicked.connect(lambda: self._on_step(+1))
        row_step.addWidget(self.btn_plus)
        root.addLayout(row_step)

        # Velocity ───────────────────────────────────────────────────────────
        row_vel = QHBoxLayout()
        row_vel.addWidget(self._lbl("Velocity:"))
        self.spin_vel = self._dspin(
            1e-4, self.config.vel_max,
            self.config.vel_default,
            4, f"{self.config.unit}/s",
            single_step=self.config.vel_default / 10
        )
        row_vel.addWidget(self.spin_vel, 1)
        self.btn_set_vel = QPushButton("Set")
        self.btn_set_vel.setFixedWidth(40)
        self.btn_set_vel.setEnabled(False)
        self.btn_set_vel.clicked.connect(self._on_set_vel)
        row_vel.addWidget(self.btn_set_vel)
        root.addLayout(row_vel)

        # HALT ───────────────────────────────────────────────────────────────
        self.btn_halt = QPushButton("■  HALT")
        self.btn_halt.setEnabled(False)
        self.btn_halt.setStyleSheet(
            "QPushButton { background:#991c1c; color:white; font-weight:bold; border-radius:3px; }"
            "QPushButton:hover { background:#c02020; }"
            "QPushButton:disabled { background:#3a2222; color:#664444; }"
        )
        self.btn_halt.clicked.connect(self._on_halt)
        root.addWidget(self.btn_halt)

    # ── Helpers ─────────────────────────────────────────────────────────────
    @staticmethod
    def _lbl(text: str) -> QLabel:
        l = QLabel(text)
        l.setFixedWidth(58)
        l.setStyleSheet("color:#9090b0; font-size:9pt;")
        return l

    @staticmethod
    def _dspin(mn, mx, val, dec, suffix, single_step=None) -> QDoubleSpinBox:
        sb = QDoubleSpinBox()
        sb.setDecimals(dec)
        sb.setMinimum(mn); sb.setMaximum(mx); sb.setValue(val)
        sb.setSuffix(f"  {suffix}")
        sb.setSingleStep(single_step or 10 ** (-dec))
        sb.setMinimumWidth(120)
        return sb

    def _set_controls_enabled(self, en: bool):
        for w in (self.btn_move, self.btn_minus, self.btn_plus,
                  self.btn_set_vel, self.btn_halt):
            w.setEnabled(en)

    # ── Slots ────────────────────────────────────────────────────────────────
    def _on_connect_clicked(self, checked: bool):
        if checked:
            self.btn_connect.setText("...")
            self.btn_connect.setEnabled(False)
            QApplication.processEvents()
            ok = self.backend.connect()
            self.btn_connect.setEnabled(True)
            if ok:
                self.btn_connect.setText("Disconnect")
                self.led.set_state("connected")
                self._set_controls_enabled(True)
                self.spin_vel.setValue(self.backend.get_velocity())
            else:
                self.btn_connect.setChecked(False)
                self.btn_connect.setText("Connect")
                self.led.set_state("error")
                QMessageBox.warning(
                    self, "Connection failed",
                    f"Could not connect to {self.config.display_name}\n"
                    f"Controller: {self.config.controller}\n"
                    f"Serial: '{self.config.serial or 'not set'}'\n\n"
                    "Check USB cable, serial number, and PIPython install."
                )
        else:
            self.backend.disconnect()
            self.btn_connect.setText("Connect")
            self.led.set_state("disconnected")
            self.lbl_value.setText("---")
            self._set_controls_enabled(False)

    def _on_move(self):
        self.backend.move_absolute(self.spin_target.value())

    def _on_step(self, direction: int):
        self.backend.move_relative(direction * self.spin_step.value())

    def _on_set_vel(self):
        self.backend.set_velocity(self.spin_vel.value())

    def _on_halt(self):
        self.backend.halt()

    # ── Periodic update (called by MainWindow timer) ─────────────────────────
    def refresh(self):
        if not self.backend.connected:
            return
        pos     = self.backend.get_position()
        moving  = self.backend.is_moving()
        self.lbl_value.setText(f"{pos:.{self.config.decimals}f}")
        self.led.set_state("moving" if moving else "connected")


# ═══════════════════════════════════════════════════════════════════════════
# MainWindow
# ═══════════════════════════════════════════════════════════════════════════

class MainWindow(QMainWindow):

    POLL_MS = 200   # position polling interval

    def __init__(self, demo: bool):
        super().__init__()
        self.demo = demo
        self.setWindowTitle("PI Stage Controller — FAU")
        self.setMinimumSize(1050, 680)

        # Build backends
        self.backends = [
            DemoBackend(cfg) if demo else HardwareBackend(cfg)
            for cfg in CONTROLLERS
        ]
        # Build cards
        self.cards: List[ControllerCard] = [
            ControllerCard(cfg, be)
            for cfg, be in zip(CONTROLLERS, self.backends)
        ]

        self._build_ui()
        self._build_menu()

        # Polling timer
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll)
        self._timer.start(self.POLL_MS)

    # ── UI ───────────────────────────────────────────────────────────────────
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(6)

        # Demo banner
        if self.demo:
            banner = QLabel(
                "⚠   DEMO MODE  —  no hardware connected  "
                "(PIPython not found or --demo flag used)"
            )
            banner.setStyleSheet(
                "background:#6b3800; color:#ffcc44; padding:5px 14px;"
                "border-radius:4px; font-weight:bold;"
            )
            banner.setAlignment(Qt.AlignCenter)
            root.addWidget(banner)

        # Toolbar ────────────────────────────────────────────────────────────
        tb = QHBoxLayout()

        self.btn_conn_all = QPushButton("Connect All")
        self.btn_conn_all.setFixedHeight(28)
        self.btn_conn_all.clicked.connect(self._connect_all)
        tb.addWidget(self.btn_conn_all)

        self.btn_disc_all = QPushButton("Disconnect All")
        self.btn_disc_all.setFixedHeight(28)
        self.btn_disc_all.clicked.connect(self._disconnect_all)
        tb.addWidget(self.btn_disc_all)

        tb.addStretch()

        self.btn_halt_all = QPushButton("■   HALT ALL")
        self.btn_halt_all.setFixedHeight(28)
        self.btn_halt_all.setStyleSheet(
            "QPushButton { background:#bb1111; color:white; font-weight:bold; padding:0 18px; }"
            "QPushButton:hover { background:#e01a1a; }"
        )
        self.btn_halt_all.clicked.connect(self._halt_all)
        tb.addWidget(self.btn_halt_all)

        root.addLayout(tb)

        # Tabs ───────────────────────────────────────────────────────────────
        self.tabs = QTabWidget()
        for group_name, indices in GROUPS.items():
            tab_widget = QWidget()
            tab_layout = QVBoxLayout(tab_widget)
            tab_layout.setContentsMargins(0, 0, 0, 0)

            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.NoFrame)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

            container = QWidget()
            container.setStyleSheet("background: transparent;")
            col = QVBoxLayout(container)
            col.setContentsMargins(8, 10, 8, 10)
            col.setSpacing(10)
            
            for row_indices in indices:          # each row_indices is e.g. [7, 8, 9]
                row = QHBoxLayout()
                row.setAlignment(Qt.AlignLeft | Qt.AlignTop)
                row.setSpacing(10)
                for i in row_indices:            # each i is a card index
                    row.addWidget(self.cards[i])
                row.addStretch()
                col.addLayout(row)
            
            col.addStretch()
            scroll.setWidget(container)
            tab_layout.addWidget(scroll)
            self.tabs.addTab(tab_widget, group_name)

        root.addWidget(self.tabs)

        # Status bar ─────────────────────────────────────────────────────────
        sb = QStatusBar()
        self.setStatusBar(sb)
        mode = "DEMO" if self.demo else "HARDWARE"
        sb.showMessage(
            f"Mode: {mode}  |  {len(CONTROLLERS)} controllers  |  "
            f"Poll: {self.POLL_MS} ms  |  Axis: '{AXIS}'"
        )

    def _build_menu(self):
        mb = self.menuBar()

        fm = mb.addMenu("File")
        a = QAction("Quit", self); a.setShortcut("Ctrl+Q")
        a.triggered.connect(self.close); fm.addAction(a)

        cm = mb.addMenu("Controllers")
        a = QAction("Connect All", self); a.triggered.connect(self._connect_all); cm.addAction(a)
        a = QAction("Disconnect All", self); a.triggered.connect(self._disconnect_all); cm.addAction(a)
        cm.addSeparator()
        a = QAction("HALT ALL", self); a.triggered.connect(self._halt_all); cm.addAction(a)

    # ── Polling ──────────────────────────────────────────────────────────────
    def _poll(self):
        for card in self.cards:
            card.refresh()

    # ── Bulk actions ─────────────────────────────────────────────────────────
    def _connect_all(self):
        for card in self.cards:
            if not card.backend.connected:
                card.btn_connect.setChecked(True)
                card._on_connect_clicked(True)
                QApplication.processEvents()

    def _disconnect_all(self):
        for card in self.cards:
            if card.backend.connected:
                card.btn_connect.setChecked(False)
                card._on_connect_clicked(False)

    def _halt_all(self):
        for card in self.cards:
            if card.backend.connected:
                card.backend.halt()

    # ── Clean shutdown ────────────────────────────────────────────────────────
    def closeEvent(self, event):
        self._timer.stop()
        self._disconnect_all()
        event.accept()


# ═══════════════════════════════════════════════════════════════════════════
# Dark Fusion palette
# ═══════════════════════════════════════════════════════════════════════════

def _apply_dark_palette(app: QApplication):
    app.setStyle("Fusion")
    p = QPalette()
    bg    = QColor(30,  30,  42)
    mid   = QColor(45,  45,  60)
    light = QColor(70,  70,  90)
    txt   = QColor(215, 215, 230)
    hi    = QColor(0,  110, 210)
    base  = QColor(22,  22,  32)

    p.setColor(QPalette.Window,          bg)
    p.setColor(QPalette.WindowText,      txt)
    p.setColor(QPalette.Base,            base)
    p.setColor(QPalette.AlternateBase,   mid)
    p.setColor(QPalette.ToolTipBase,     mid)
    p.setColor(QPalette.ToolTipText,     txt)
    p.setColor(QPalette.Text,            txt)
    p.setColor(QPalette.Button,          mid)
    p.setColor(QPalette.ButtonText,      txt)
    p.setColor(QPalette.BrightText,      Qt.white)
    p.setColor(QPalette.Highlight,       hi)
    p.setColor(QPalette.HighlightedText, Qt.white)
    p.setColor(QPalette.Disabled, QPalette.Text,       QColor(90, 90, 110))
    p.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(90, 90, 110))
    p.setColor(QPalette.Disabled, QPalette.WindowText, QColor(90, 90, 110))
    app.setPalette(p)


# ═══════════════════════════════════════════════════════════════════════════
# Entry point
# ═══════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="PI Multi-Controller Stage GUI")
    parser.add_argument(
        "--demo", action="store_true",
        help="Run in demo/simulation mode (no hardware required)"
    )
    args = parser.parse_args()

    demo_mode = True #args.demo or not HAS_PIPYTHON
    if not HAS_PIPYTHON and not args.demo:
        print("[WARNING] PIPython is not installed — starting in DEMO mode.")
        print("          Install with:  pip install pipython\n")

    app = QApplication(sys.argv)
    _apply_dark_palette(app)

    win = MainWindow(demo=demo_mode)
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
