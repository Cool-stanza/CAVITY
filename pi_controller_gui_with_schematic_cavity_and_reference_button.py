#!/usr/bin/env python3
"""
PI Multi-Controller Stage GUI
==============================

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
    d = GCSDevice("C-663.12") 
    print(d.EnumerateUSB())
"""

import sys
import time
import random
import argparse
from dataclasses import dataclass
from typing import Optional, List, Dict

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGroupBox, QLabel, QPushButton, QDoubleSpinBox, QScrollArea,
    QFrame, QStatusBar, QMessageBox, QSizePolicy, QTabWidget,
    QAction, QSpacerItem,
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QPalette, QColor, QPainter, QPen, QBrush

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
    serial:          str  = ""    # ← FILL IN USB serial number to distinguish units of same model
    axis_label:      str  = ""    # ← FILL IN axis/movement label shown in GUI, e.g. "X", "Y"
    needs_reference: bool = True  # False for piezos (N-472) — they have no limit switch
    is_piezo:        bool = False


# ┌─────────────────────────────────────────────────────────────────────────┐
# │  Edit ONLY the `serial` fields once you know each controller's SN.     │
# └─────────────────────────────────────────────────────────────────────────┘
CONTROLLERS: List[ControllerConfig] = [

    # ── C-663.12 → L-509.021100V6  (×2, travel = 26 mm) ─────────────────
    ControllerConfig("L-509 #1",  "C-663.12", "L-509.021100V6",
                     unit="mm", pos_min=0, pos_max=26,
                     vel_default=3.0,  vel_max=10.0,  step_default=1.0,
                     decimals=4,  serial="",  axis_label="X"),
    ControllerConfig("L-509 #2",  "C-663.12", "L-509.021100V6",
                     unit="mm", pos_min=0, pos_max=26,
                     vel_default=3.0,  vel_max=10.0,  step_default=1.0,
                     decimals=4,  serial="",  axis_label="Y"),

    # ── C-663.12 → L-310.021211V6  (×1, travel = 26 mm) ─────────────────
    ControllerConfig("L-310",     "C-663.12", "L-310.021211V6",
                     unit="mm", pos_min=0, pos_max=26,
                     vel_default=2.0,  vel_max=7.5,  step_default=1.0,
                     decimals=4,  serial="",  axis_label="Z"),

    # ── C-863.12 → M-110.1VG1  (×4, travel = 5 mm) ────────────────────────
    # #1 and #2 = bottom mirror x/y positioning
    ControllerConfig("M-110 #1",  "C-863.12", "M-110.1VG1",
                     unit="mm", pos_min=0, pos_max=5,
                     vel_default=0.2,  vel_max=1.0,   step_default=0.1,
                     decimals=5,  serial="",  axis_label="X mirror"),
    ControllerConfig("M-110 #2",  "C-863.12", "M-110.1VG1",
                     unit="mm", pos_min=0, pos_max=5,
                     vel_default=0.2,  vel_max=1.0,   step_default=0.1,
                     decimals=5,  serial="",  axis_label="Y mirror"),
    # #3 and #4 = sample x/y positioning
    ControllerConfig("M-110 #3",  "C-863.12", "M-110.1VG1",
                     unit="mm", pos_min=0, pos_max=5,
                     vel_default=0.2,  vel_max=1.0,   step_default=0.1,
                     decimals=5,  serial="",  axis_label="X sample"),
    ControllerConfig("M-110 #4",  "C-863.12", "M-110.1VG1",
                     unit="mm", pos_min=0, pos_max=5,
                     vel_default=0.2,  vel_max=1.0,   step_default=0.1,
                     decimals=5,  serial="",  axis_label="Y sample"),

    # ── E-873.1AT → N-472.11V  (×6, travel = 7 mm) ──────────────────────
    # PiezoMike: incremental encoder → needs_reference=True (home after power-on)
    # #1–#3 = bottom mirror piezos
    ControllerConfig("N-472 #1",  "E-873.1AT", "N-472.11V",
                     unit="mm", pos_min=-7.0, pos_max=7.0,
                     vel_default=0.01, vel_max=0.033,  step_default=0.05,
                     decimals=6,  serial="",  axis_label="bottom1",  needs_reference=False, is_piezo=True),
    ControllerConfig("N-472 #2",  "E-873.1AT", "N-472.11V",
                     unit="mm", pos_min=-7.0, pos_max=7.0,
                     vel_default=0.01, vel_max=0.033,  step_default=0.05,
                     decimals=6,  serial="",  axis_label="bottom2",  needs_reference=False, is_piezo=True),
    ControllerConfig("N-472 #3",  "E-873.1AT", "N-472.11V",
                     unit="mm", pos_min=-7.0, pos_max=7.0,
                     vel_default=0.01, vel_max=0.033,  step_default=0.05,
                     decimals=6,  serial="",  axis_label="bottom3",  needs_reference=False, is_piezo=True),
    # #4–#6 = top mirror piezos
    ControllerConfig("N-472 #4",  "E-873.1AT", "N-472.11V",
                     unit="mm", pos_min=-7.0, pos_max=7.0,
                     vel_default=0.01, vel_max=0.033,  step_default=0.05,
                     decimals=6,  serial="",  axis_label="top4",  needs_reference=False, is_piezo=True),
    ControllerConfig("N-472 #5",  "E-873.1AT", "N-472.11V",
                     unit="mm", pos_min=-7.0, pos_max=7.0,
                     vel_default=0.01, vel_max=0.033,  step_default=0.05,
                     decimals=6,  serial="",  axis_label="top5",  needs_reference=False, is_piezo=True),
    ControllerConfig("N-472 #6",  "E-873.1AT", "N-472.11V",
                     unit="mm", pos_min=-7.0, pos_max=7.0,
                     vel_default=0.01, vel_max=0.033,  step_default=0.05,
                     decimals=6,  serial="",  axis_label="top6",  needs_reference=False, is_piezo=True),
]

# ─── Tab layout ───────────────────────────────────────────────────────────
# GROUPS: tab_name → list of rows; each row is a list of CONTROLLERS indices.
GROUPS: Dict[str, List[List[int]]] = {
    "Coarse  (C-663.12)":  [[0, 1, 2]],            # L-509 X/Y + L-310 Z in one row
    "M-110  (C-863.12)":   [[3, 4], [5, 6]],        # bottom mirror row / sample row
    "N-472  (E-873.1AT)":  [[7, 8, 9], [10, 11, 12]],  # bottom mirror row / top mirror row
}

# TAB_COMPONENTS: maps each tab to its schematic type and which card indices
# belong to each drawable component.  Each key maps to exactly ONE card so
# individual elements in the schematic light up independently.
TAB_COMPONENTS: Dict[str, tuple] = {
    "Coarse  (C-663.12)": ("coarse", {
        "L509x": [0], "L509y": [1], "L310z": [2],
    }),
    "M-110  (C-863.12)": ("M110", {
        "M110_bx": [3],   # M-110 #1 → bottom mirror x
        "M110_by": [4],   # M-110 #2 → bottom mirror y
        "M110_sx": [5],   # M-110 #3 → sample x
        "M110_sy": [6],   # M-110 #4 → sample y
    }),
    "N-472  (E-873.1AT)": ("N472", {
        "N472_b1": [7],  "N472_b2": [8],  "N472_b3": [9],   # bottom mirror
        "N472_t1": [10], "N472_t2": [11], "N472_t3": [12],  # top mirror
    }),
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
                self.device.ConnectUSB(self.config.controller)
            self.connected = True
            if self.config.is_piezo:
                self.device.SVO(AXIS, 0)   # ensure servo off on connect
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

    def reference(self):
        """Drive to negative limit switch and set position to zero (FNL)."""
        if not self.connected:
            return
        try:
            self.device.FNL(AXIS)   # Find Negative Limit — standard PI homing
        except Exception as exc:
            print(f"[{self.config.display_name}] FNL error: {exc}")
            
    def set_servo(self, on: bool):
        """Enable (True) or disable (False) closed-loop control."""
        if not self.connected:
            return
        try:
            self.device.SVO(AXIS, 1 if on else 0)
        except Exception as exc:
            print(f"[{self.config.display_name}] SVO error: {exc}")
    
    def set_zero(self):
        """Define the current physical position as 0.
        E-873.1AT: servo must be OFF to redefine the position counter."""
        if not self.connected:
            return
        try:
            self.device.SVO(AXIS, 0)       # open loop
            self.device.POS(AXIS, 0)       # redefine current position = 0
            self.device.SVO(AXIS, 1)       # closed loop again
        except Exception as exc:
            print(f"[{self.config.display_name}] SetZero error: {exc}")


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
        self._servo    = False 
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

    def reference(self):
        """Simulate homing: move to pos_min and zero the position."""
        self.move_absolute(self.config.pos_min)
        
    def set_servo(self, on: bool):
        self._servo = on   # (add `self._servo = False` in __init__)
    
    def set_zero(self):
        self._pos    = 0.0
        self._target = 0.0


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

    CARD_W = 295

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

        # Axis badge — colored chip showing the movement direction (X or Y only)
        if self.config.axis_label:
            badge = QLabel(self.config.axis_label)
            badge.setAlignment(Qt.AlignCenter)
            badge.setFixedHeight(18)
            badge.setMinimumWidth(28)
            color = {
                "X mirror": "#c0392b",
                "Y mirror": "#27ae60",
                "X sample": "#c0392b",
                "Y sample": "#27ae60",
                "X": "#c0392b",
                "Y": "#27ae60",
                "Z": "#2980b9",
                "bottom1": "#1a8fe3",
                "bottom2": "#6a0dad",
                "bottom3": "#a855f7",
                "top4": "#1a8fe3",
                "top5": "#6a0dad",
                "top6": "#a855f7",
            }.get(self.config.axis_label, "#555577")
            badge.setStyleSheet(
                f"background:{color}; color:white; border-radius:3px;"
                f"font-size:8pt; font-weight:bold; padding:0 5px;"
            )
            hdr.addWidget(badge)

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

        # Reference (FNL) — only for stages with a limit switch ──────────────
        if self.config.needs_reference:
            self.btn_ref = QPushButton("⌂  Reference (FNL)")
            self.btn_ref.setEnabled(False)
            self.btn_ref.setToolTip(
                "Drive to negative limit switch and set position to zero.\n"
                "Do this once after every power-on before moving."
            )
            self.btn_ref.setStyleSheet(
                "QPushButton { background:#1a3a5c; color:#66bbff; "
                "font-weight:bold; border-radius:3px; border:1px solid #2255aa; }"
                "QPushButton:hover { background:#1e4a78; }"
                "QPushButton:disabled { background:#151d28; color:#334466; border-color:#1a2233; }"
            )
            self.btn_ref.clicked.connect(self._on_reference)
            root.addWidget(self.btn_ref)
        else:
            self.btn_ref = None   # piezos — no reference needed

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

        # ── Limits / Zero ────────────────────────────────────────────────────────
        if self.config.is_piezo:
            # "Go to zero" button
            row_limits = QHBoxLayout()
            self.btn_to_start = QPushButton("⟨ Go to 0")
            self.btn_to_start.setToolTip("Move to position 0 (closed-loop)")
            self.btn_to_start.setEnabled(False)
            self.btn_to_start.clicked.connect(self._on_move_to_start)
            row_limits.addWidget(self.btn_to_start, 1)
        
            # "Set as Zero" button
            self.btn_set_zero = QPushButton("◎  Set as Zero")
            self.btn_set_zero.setToolTip(
                "Disable servo, define current position = 0, re-enable servo.\n"
                "Use this after manually positioning the piezo to your reference point."
            )
            self.btn_set_zero.setEnabled(False)
            self.btn_set_zero.setStyleSheet(
                "QPushButton { background:#1a4a2a; color:#55ee88; font-weight:bold; "
                "border-radius:3px; border:1px solid #227744; }"
                "QPushButton:hover { background:#1e5c33; }"
                "QPushButton:disabled { background:#151d18; color:#334433; border-color:#1a2233; }"
            )
            self.btn_set_zero.clicked.connect(self._on_set_zero_clicked)
            row_limits.addWidget(self.btn_set_zero, 1)
        
            # Servo toggle
            self.btn_servo = QPushButton("Servo ON")
            self.btn_servo.setCheckable(True)
            self.btn_servo.setChecked(False)
            self.btn_servo.setEnabled(False)
            self.btn_servo.setToolTip("Toggle closed-loop servo (SVO)")
            self.btn_servo.setStyleSheet(
                "QPushButton         { background:#2a2a3a; color:#888899; border-radius:3px;"
                "                      border:1px solid #444455; }"
                "QPushButton:checked { background:#1a4a2a; color:#55ee88; font-weight:bold;"
                "                      border:2px solid #33cc55; }"
                "QPushButton:disabled{ background:#151520; color:#333344; border:1px solid #222233; }"
            )
            self.btn_servo.clicked.connect(self._on_servo_toggle)
            self.btn_servo.clicked.connect(self._on_servo_toggle)
            row_limits.addWidget(self.btn_servo, 1)
        
            root.addLayout(row_limits)
            self.btn_to_end = None   # not used for piezos
        
        else:
            # Original Start / End buttons for motor stages
            row_limits = QHBoxLayout()
            row_limits.addWidget(self._lbl("Limits:"))
            self.btn_to_start = QPushButton("⟨ Start")
            self.btn_to_start.setToolTip(f"Move to start  ({self.config.pos_min} {self.config.unit})")
            self.btn_to_start.setEnabled(False)
            self.btn_to_start.clicked.connect(self._on_move_to_start)
            row_limits.addWidget(self.btn_to_start, 1)
            self.btn_to_end = QPushButton("End ⟩")
            self.btn_to_end.setToolTip(f"Move to end  ({self.config.pos_max} {self.config.unit})")
            self.btn_to_end.setEnabled(False)
            self.btn_to_end.clicked.connect(self._on_move_to_end)
            row_limits.addWidget(self.btn_to_end, 1)
            root.addLayout(row_limits)

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
    
    def _on_servo_toggle(self, checked: bool):
        self.backend.set_servo(checked)
        self.btn_servo.setText("Servo ON" if checked else "Servo OFF")
    
    def _on_set_zero_clicked(self):
        reply = QMessageBox.question(
            self,
            "Confirm Set Zero",
            f"Are you sure you want to set position = 0.{'0' * self.config.decimals} "
            f"{self.config.unit}?\n\n"
            "The current physical position will be redefined as the new zero.\n"
            "This cannot be undone without re-referencing.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,          # ← default to No so Enter doesn't confirm accidentally
        )
        if reply == QMessageBox.Yes:
            self.backend.set_zero()

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
        widgets = [self.btn_move, self.btn_minus, self.btn_plus,
                   self.btn_set_vel, self.btn_halt, self.btn_to_start]
        if getattr(self, 'btn_to_end', None):
            widgets.append(self.btn_to_end)
        if getattr(self, 'btn_set_zero', None):
            widgets.append(self.btn_set_zero)
        if getattr(self, 'btn_servo', None):
            widgets.append(self.btn_servo)
        for w in widgets:
            w.setEnabled(en)
        if self.btn_ref is not None:
            self.btn_ref.setEnabled(en)

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
                # ← new: auto-enable servo for piezos
                if self.config.is_piezo:
                    self.backend.set_servo(False)
                    self.btn_servo.setChecked(False)
                    self.btn_servo.setText("Servo OFF")
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

    def _on_move_to_start(self):
        self.backend.move_absolute(self.config.pos_min)

    def _on_move_to_end(self):
        self.backend.move_absolute(self.config.pos_max)

    def _on_reference(self):
        self.backend.reference()

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
# SchematicWidget — side-view of the optical cavity assembly
# ═══════════════════════════════════════════════════════════════════════════

class SchematicWidget(QWidget):
    """
    Side-view schematic of the optical cavity assembly.

    Highlighting rules:
    - Mirror rectangles (Top / Bottom) and the Sample block are always drawn
      dim — they are structural/passive elements and do not react to
      controller connections.
    - Individual component indicators (piezo squares, M-110 x/y squares,
      coarse stage boxes) highlight independently: only the one connected
      controller lights up.

    Component key conventions
    ──────────────────────────
      L509x, L509y, L310z        — coarse stages (one card each)
      M110_bx, M110_by           — bottom-mirror M-110 x / y
      M110_sx, M110_sy           — sample M-110 x / y
      N472_b1, N472_b2, N472_b3 — bottom-mirror piezos (one card each)
      N472_t1, N472_t2, N472_t3 — top-mirror piezos (one card each)
    """

    # Base accent color per key
    _C: Dict[str, QColor] = {
        "L509x":   QColor(220,  50,  50),
        "L509y":   QColor(50,  205,  80),
        "L310z":   QColor(35,  105, 215),
        "M110_bx": QColor(220,  50,  50),
        "M110_by": QColor(50,  205,  80),
        "M110_sx": QColor(220,  50,  50),
        "M110_sy": QColor(50,  205,  80),
        "N472_b1": QColor(0,   120, 215),
        "N472_b2": QColor(75,    0, 130),
        "N472_b3": QColor(160,  60, 200),
        "N472_t1": QColor(0,   120, 215),
        "N472_t2": QColor(75,    0, 130),
        "N472_t3": QColor(160,  60, 200),
    }
    _DIM_BORDER = QColor(62,  62,  82)
    _DIM_FILL   = QColor(38,  38,  52)
    _DIM_TEXT   = QColor(82,  82, 108)
    _BG         = QColor(20,  20,  32)
    _ACTIVE_TXT = QColor(190, 190, 220)
    _STRUCT     = QColor(58,  58,  80)

    def __init__(self, tab_type: str, components: Dict[str, list], parent=None):
        super().__init__(parent)
        self.tab_type   = tab_type
        self.components = components   # {key: [ControllerCard]}  — one card each
        self.setFixedWidth(210)
        self.setMinimumHeight(400)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)

    # ── Per-key state ────────────────────────────────────────────────────────

    def _state(self, key: str):
        cards = self.components.get(key, [])
        if not cards:
            return False, False
        connected = any(c.backend.connected for c in cards)
        moving    = any(c.backend.connected and c.backend.is_moving() for c in cards)
        return connected, moving

    def _border_color(self, key: str) -> QColor:
        connected, moving = self._state(key)
        if not connected:
            return QColor(self._DIM_BORDER)
        base = QColor(self._C.get(key, QColor(100, 100, 140)))
        return base.lighter(165) if moving else base

    def _fill_color(self, key: str) -> QColor:
        connected, moving = self._state(key)
        if not connected:
            return QColor(self._DIM_FILL)
        base = QColor(self._C.get(key, QColor(100, 100, 140)))
        base.setAlpha(85 if moving else 42)
        return base

    def _pen(self, key: str, w_on: int = 2, w_off: int = 1) -> QPen:
        connected, _ = self._state(key)
        return QPen(self._border_color(key), w_on if connected else w_off)

    def _text_color(self, key: str) -> QColor:
        connected, _ = self._state(key)
        return QColor(self._ACTIVE_TXT) if connected else QColor(self._DIM_TEXT)

    # ── Primitive helpers ────────────────────────────────────────────────────

    def _draw_rect(self, p, x, y, w, h, key, label="", font_size=7):
        """Rectangle whose color reflects the state of a single key."""
        p.setPen(self._pen(key))
        p.setBrush(QBrush(self._fill_color(key)))
        p.drawRect(x, y, w, h)
        if label:
            f = QFont(); f.setPointSize(font_size)
            p.setFont(f); p.setPen(self._text_color(key))
            p.drawText(x, y, w, h, Qt.AlignCenter, label)

    def _draw_small_sq(self, p, cx, cy, size, key):
        """Individual piezo square — one card, one key."""
        s = size
        p.setPen(self._pen(key, 2, 1))
        p.setBrush(QBrush(self._fill_color(key)))
        p.drawRect(cx - s // 2, cy - s // 2, s, s)

    def _draw_static_rounded(self, p, x, y, w, h, label="", font_size=7, bold=False):
        """Rounded rect always drawn dim — for structural/passive elements."""
        p.setPen(QPen(self._DIM_BORDER, 1))
        p.setBrush(QBrush(self._DIM_FILL))
        p.drawRoundedRect(x, y, w, h, 5, 5)
        if label:
            f = QFont(); f.setPointSize(font_size); f.setBold(bold)
            p.setFont(f); p.setPen(self._DIM_TEXT)
            p.drawText(x, y, w, h, Qt.AlignCenter, label)

    # ── Main paint ───────────────────────────────────────────────────────────

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        W  = self.width()
        H  = self.height()
        cx = W // 2

        p.fillRect(0, 0, W, H, self._BG)

        # Title
        f_title = QFont(); f_title.setPointSize(8); f_title.setBold(True)
        p.setFont(f_title)
        p.setPen(QColor(100, 100, 145))
        p.drawText(0, 4, W, 16, Qt.AlignHCenter, "SCHEMATIC")

        # ── Geometry ──────────────────────────────────────────────────────
        mir_w = 148; mir_h = 26
        mir_l = (W - mir_w) // 2
        mir_r = mir_l + mir_w

        top_y   = 28
        cav_top = top_y + mir_h
        bot_y   = cav_top + 128
        cav_bot = bot_y
        cav_mid = (cav_top + cav_bot) // 2

        px_l = mir_l + 18
        px_r = mir_r - 18

        post_top = bot_y + mir_h
        coarse_y = post_top + 42

        cbox_w = 134; cbox_h = 26; cbox_gap = 4
        cbox_l = (W - cbox_w) // 2

        m_size = 13
        f_tiny = QFont(); f_tiny.setPointSize(6)
        piezo_xs = [mir_l + int(mir_w * f) for f in [0.22, 0.50, 0.78]]

        top_keys = ["N472_t1", "N472_t2", "N472_t3"]
        bot_keys = ["N472_b1", "N472_b2", "N472_b3"]

        # ── N-472 top — individual piezo squares above top mirror ─────────
        for key, px in zip(top_keys, piezo_xs):
            self._draw_small_sq(p, px, top_y - 9, 7, key)

        # ── Top mirror — always dim (structural) ──────────────────────────
        self._draw_static_rounded(p, mir_l, top_y, mir_w, mir_h,
                                  "Top Mirror", bold=True)

        # ── Cavity: dashed posts ──────────────────────────────────────────
        p.setPen(QPen(self._STRUCT, 1, Qt.DashLine))
        p.drawLine(px_l, cav_top, px_l, cav_bot)
        p.drawLine(px_r, cav_top, px_r, cav_bot)

        # "optical cavity" label
        f_ital = QFont(); f_ital.setPointSize(7); f_ital.setItalic(True)
        p.setFont(f_ital)
        p.setPen(QColor(68, 68, 98))
        p.drawText(0, cav_top + 4, W, 14, Qt.AlignHCenter, "optical cavity")

        # ── Sample block — always dim (structural) ────────────────────────
        samp_w = 58; samp_h = 22
        samp_x = (W - samp_w) // 2
        samp_y = cav_mid - samp_h // 2
        self._draw_static_rounded(p, samp_x, samp_y, samp_w, samp_h, "SAMPLE")

        # M-110 sample indicators — stacked vertically to the right of sample
        samp_cy = samp_y + samp_h // 2
        sx_x = samp_x + samp_w + 4
        sx_y = samp_cy - m_size - 1   # x on top
        sy_y = samp_cy + 1            # y on bottom
        self._draw_rect(p, sx_x, sx_y, m_size, m_size, "M110_sx")
        self._draw_rect(p, sx_x, sy_y, m_size, m_size, "M110_sy")
        p.setFont(f_tiny)
        p.setPen(self._text_color("M110_sx"))
        p.drawText(sx_x, sx_y, m_size, m_size, Qt.AlignCenter, "x")
        p.setPen(self._text_color("M110_sy"))
        p.drawText(sx_x, sy_y, m_size, m_size, Qt.AlignCenter, "y")

        # ── M-110 bottom-mirror indicators — stacked vertically to the right
        mir_cy2 = bot_y + mir_h // 2
        bx_x = mir_r + 4
        bx_y = mir_cy2 - m_size - 1   # x on top
        by_y = mir_cy2 + 1             # y on bottom
        self._draw_rect(p, bx_x, bx_y, m_size, m_size, "M110_bx")
        self._draw_rect(p, bx_x, by_y, m_size, m_size, "M110_by")
        p.setFont(f_tiny)
        p.setPen(self._text_color("M110_bx"))
        p.drawText(bx_x, bx_y, m_size, m_size, Qt.AlignCenter, "x")
        p.setPen(self._text_color("M110_by"))
        p.drawText(bx_x, by_y, m_size, m_size, Qt.AlignCenter, "y")

        # ── Bottom mirror — always dim (structural) ───────────────────────
        self._draw_static_rounded(p, mir_l, bot_y, mir_w, mir_h,
                                  "Bottom Mirror", bold=True)

        # ── N-472 bottom — individual piezo squares below bottom mirror ───
        for key, px in zip(bot_keys, piezo_xs):
            self._draw_small_sq(p, px, bot_y + mir_h + 9, 7, key)

        # ── Center post → coarse stack ────────────────────────────────────
        p.setPen(QPen(self._STRUCT, 2, Qt.SolidLine))
        p.drawLine(cx, post_top + 16, cx, coarse_y)

        # ── Coarse boxes: L-310 Z on top, L-509 Y middle, L-509 X at base ─
        coarse_items = [
            ("L310z", "L-310  Z"),
            ("L509y", "L-509  Y"),
            ("L509x", "L-509  X"),
        ]
        for idx, (key, lbl) in enumerate(coarse_items):
            by = coarse_y + idx * (cbox_h + cbox_gap)
            self._draw_rect(p, cbox_l, by, cbox_w, cbox_h, key, lbl, font_size=7)

        # ── Base line ─────────────────────────────────────────────────────
        base_y = coarse_y + 3 * (cbox_h + cbox_gap) + 4
        p.setPen(QPen(self._STRUCT.lighter(120), 2))
        p.setBrush(Qt.NoBrush)
        p.drawLine((W - 162) // 2, base_y, (W + 162) // 2, base_y)

        # ── Legend ────────────────────────────────────────────────────────
        leg_y = base_y + 10
        if leg_y + 14 < H:
            f_leg = QFont(); f_leg.setPointSize(6)
            p.setFont(f_leg)
            for lx, (bc, fc, lbl) in enumerate([
                (QColor(55, 185, 75),  QColor(55, 185, 75,  55), "connected"),
                (QColor(255, 195, 45), QColor(255, 195, 45, 75), "moving"),
            ]):
                ox = 8 + lx * 72
                p.setPen(QPen(bc, 1)); p.setBrush(QBrush(fc))
                p.drawEllipse(ox, leg_y + 2, 7, 7)
                p.setPen(QColor(105, 105, 148)); p.setBrush(Qt.NoBrush)
                p.drawText(ox + 10, leg_y - 1, 60, 12,
                           Qt.AlignLeft | Qt.AlignVCenter, lbl)

        p.end()


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

        self.schematics: List[SchematicWidget] = []

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

        self.btn_ref_all = QPushButton("⌂  Reference All")
        self.btn_ref_all.setFixedHeight(28)
        self.btn_ref_all.setToolTip(
            "Run FNL on every connected stage that has a limit switch.\n"
            "Piezos (N-472) are skipped automatically."
        )
        self.btn_ref_all.setStyleSheet(
            "QPushButton { background:#1a3a5c; color:#66bbff; font-weight:bold; padding:0 12px; }"
            "QPushButton:hover { background:#1e4a78; }"
        )
        self.btn_ref_all.clicked.connect(self._reference_all)
        tb.addWidget(self.btn_ref_all)

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
        self.schematics.clear()

        for group_name, rows in GROUPS.items():
            # Look up schematic info for this tab
            tab_type, comp_indices = TAB_COMPONENTS[group_name]
            # Build {key: [ControllerCard, ...]} for the schematic
            components: Dict[str, list] = {
                key: [self.cards[i] for i in idx_list]
                for key, idx_list in comp_indices.items()
            }

            tab_widget = QWidget()
            # Horizontal layout: scroll area (cards) on left, schematic on right
            tab_layout = QHBoxLayout(tab_widget)
            tab_layout.setContentsMargins(0, 0, 0, 0)
            tab_layout.setSpacing(0)

            # Scroll area wrapping the card rows
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.NoFrame)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

            container = QWidget()
            container.setStyleSheet("background: transparent;")
            col = QVBoxLayout(container)
            col.setAlignment(Qt.AlignLeft | Qt.AlignTop)
            col.setContentsMargins(8, 10, 8, 10)
            col.setSpacing(12)

            # Build each row of cards
            for row_indices in rows:
                row_layout = QHBoxLayout()
                row_layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)
                row_layout.setSpacing(10)
                for i in row_indices:
                    row_layout.addWidget(self.cards[i])
                row_layout.addStretch()
                col.addLayout(row_layout)

            col.addStretch()
            scroll.setWidget(container)
            tab_layout.addWidget(scroll, 1)

            # Schematic widget fixed to the right
            schematic = SchematicWidget(tab_type, components)
            self.schematics.append(schematic)
            tab_layout.addWidget(schematic)

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
        # Repaint schematics so per-component state updates are visible
        for s in self.schematics:
            s.update()

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

    def _reference_all(self):
        """Run FNL on every connected stage that needs referencing (skips piezos)."""
        for card in self.cards:
            if card.backend.connected and card.config.needs_reference:
                card.backend.reference()

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
    bg    = QColor(0,   30,  42)
    mid   = QColor(45,  45,  60)
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

    demo_mode = True  # args.demo or not HAS_PIPYTHON
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