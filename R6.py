Deps: pip install pynput
Run as administrator for raw input access.

import ctypes
import ctypes.wintypes as wt
import threading
import time
import tkinter as tk
import queue
from ctypes import wintypes

# ─────────────────────────────────────────────────────────
# Windows timer resolution — 1ms instead of default 15ms.
# Without this, time.sleep(0.068) wakes up anywhere from
# 68ms to 83ms late. The stutter you felt was this.
# ─────────────────────────────────────────────────────────
try:
    ctypes.windll.winmm.timeBeginPeriod(1)
except Exception:
    pass

# ─────────────────────────────────────────────────────────
# SendInput — raw relative mouse move, bypasses cursor entirely
# ─────────────────────────────────────────────────────────
SendInput        = ctypes.windll.user32.SendInput
MOUSEEVENTF_MOVE = 0x0001
INPUT_MOUSE      = 0


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx",          ctypes.c_long),
        ("dy",          ctypes.c_long),
        ("mouseData",   wintypes.DWORD),
        ("dwFlags",     wintypes.DWORD),
        ("time",        wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class _INPUT_UNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("_input", _INPUT_UNION)]


def _move(dx: int, dy: int) -> None:
    if dx == 0 and dy == 0:
        return
    extra = ctypes.pointer(ctypes.c_ulong(0))
    mi    = MOUSEINPUT(dx, dy, 0, MOUSEEVENTF_MOVE, 0, extra)
    inp   = INPUT(INPUT_MOUSE, _INPUT_UNION(mi=mi))
    SendInput(1, ctypes.pointer(inp), ctypes.sizeof(inp))


# ─────────────────────────────────────────────────────────
# Tuning anchor
# pixel_y = comp_y * (BASE_SENS / your_v_sens) * strength
# pixel_x = comp_x * (BASE_SENS / your_h_sens) * strength
#
# comp_x SIGN CONVENTION:
#   positive → pushes right
#   negative → pushes left  ← use this to counter rightward R6S drift
#
# At H=19, V=14, strength=2.5, R4-C (comp_y=18, comp_x=-3):
#   dy = 18 * (9/14) * 2.5 = 28.9px  (heavy downward pull)
#   dx = -3 * (9/19) * 2.5 = -3.6px  (left correction for rightward kick)
# ─────────────────────────────────────────────────────────
BASE_SENS = 9.0

# ─────────────────────────────────────────────────────────
# Weapon profiles — (rpm, comp_y, comp_x, spray_len, ramp_ticks)
#
# comp_x sign: negative = left, positive = right
# ARs that drift right in R6S → comp_x negative (push left)
# Weapons with random H-spread → comp_x = 0
# ─────────────────────────────────────────────────────────
WEAPON_DATA: dict[str, tuple] = {
    # ASSAULT RIFLES — comp_x negative (leftward correction)
    "R4-C":        (880,  18, -3, 30, 2),
    "AK-12":       (650,  16, -2, 30, 2),
    "C7E":         (800,  18, -3, 30, 2),
    "F2":          (980,  20, -3, 30, 2),
    "L85A2":       (670,  16, -2, 30, 2),
    "AR33":        (750,  18, -2, 30, 2),
    "556xi":       (690,  16, -2, 30, 2),
    "M4":          (750,  18, -2, 30, 2),
    "V308":        (700,  16, -2, 30, 2),
    "SPEAR .308":  (700,  16, -2, 30, 2),
    "Type-89":     (850,  18, -2, 30, 2),
    "M762":        (730,  18, -3, 30, 2),
    "C8-SFW":      (780,  18, -2, 30, 2),
    "ARX200":      (700,  16, -2, 30, 2),
    "F90":         (780,  18, -2, 30, 2),
    "POF-9":       (700,  16, -2, 30, 2),
    # SMGs — random H-spread, comp_x = 0
    "MP5":         (800,  13,  0, 25, 2),
    "MP7":         (950,  13,  0, 25, 2),
    "MPX":         (857,  13,  0, 25, 2),
    "P90":         (970,  13,  0, 30, 2),
    "9x19VSN":     (750,  11,  0, 25, 2),
    "Mx4 Storm":   (950,  13,  0, 25, 2),
    "PDW9":        (800,  13,  0, 25, 2),
    "Vector .45":  (1200, 16,  0, 25, 2),
    "T-5 SMG":     (900,  13,  0, 25, 2),
    "FMG-9":       (1100, 16,  0, 25, 2),
    "M12":         (550,  11,  0, 25, 2),
    "MP5SD":       (800,  13,  0, 25, 2),
    "MP5K":        (800,  13,  0, 25, 2),
    "UMP45":       (600,  11,  0, 25, 2),
    "SCORPION EVO 3 A1": (1080, 16, 0, 30, 2),
    "SPSMG9":      (980,  13,  0, 25, 2),
    "Smg12":       (1270, 16,  0, 20, 1),
    "Smg11":       (1270, 16,  0, 20, 1),
    # LMGs
    "LMG-E":       (650,  16,  0, 35, 3),
    "6P41":        (650,  16,  0, 35, 3),
    "M249":        (750,  16,  0, 35, 3),
    "ALDA 5.56":   (900,  18, -2, 35, 3),
    "T-95 LSW":    (650,  16,  0, 35, 3),
    # DMRs — semi-auto
    "MK14 EBR":    (260,  11,  0, 8,  0),
    "417":         (200,  11,  0, 8,  0),
    "SR-25":       (260,  11,  0, 8,  0),
    "CAMRS":       (300,  11,  0, 8,  0),
    "AR-15.50":    (240,  11,  0, 8,  0),
    "OTS-03":      (200,  11,  0, 8,  0),
    # SHOTGUNS
    "M590A1":      (75,   20,  0, 6,  0),
    "M1014":       (100,  20,  0, 6,  0),
    "SPAS-12":     (67,   20,  0, 6,  0),
    "SPAS-15":     (150,  20,  0, 6,  0),
    "Supernova":   (75,   20,  0, 6,  0),
    "SG-CQB":      (75,   20,  0, 6,  0),
    "SIX12":       (150,  20,  0, 6,  0),
    "SIX12 SD":    (150,  20,  0, 6,  0),
    "Super Shorty":(150,  20,  0, 6,  0),
    "FO-12":       (200,  20,  0, 6,  0),
    "ACS12":       (300,  20,  0, 8,  0),
    "TCSG12":      (150,  18,  0, 6,  0),
    "ITA12S":      (75,   20,  0, 6,  0),
    "ITA12L":      (75,   20,  0, 6,  0),
    # PISTOLS
    "P226 MK25":   (450,   9,  0, 6,  0),
    "P229":        (450,   9,  0, 6,  0),
    "P9":          (450,   9,  0, 6,  0),
    "P10C":        (450,   9,  0, 6,  0),
    "PRB92":       (450,   9,  0, 6,  0),
    "GSH-18":      (600,   9,  0, 6,  0),
    "PMM":         (600,   9,  0, 6,  0),
    "P12":         (450,   9,  0, 6,  0),
    "USP40":       (450,   9,  0, 6,  0),
    "M45 MEUSOC":  (450,   9,  0, 6,  0),
    "1911 TACOPS": (450,   9,  0, 6,  0),
    "5.7 USG":     (450,   9,  0, 6,  0),
    "D-50":        (300,  11,  0, 6,  0),
    ".44 Mag Semi-Auto": (300, 11, 0, 6, 0),
    "LFP586":      (174,  13,  0, 6,  0),
    "RG15":        (450,   9,  0, 6,  0),
    "SDP 9mm":     (450,   9,  0, 6,  0),
    "Luison":      (450,   9,  0, 6,  0),
    "MK1 9mm":     (450,   9,  0, 6,  0),
}

WEAPON_REGISTRY: dict[str, list[str]] = {
    "ASSAULT RIFLES": [
        "R4-C","AK-12","C7E","F2","L85A2","AR33","556xi","M4","V308",
        "SPEAR .308","Type-89","M762","C8-SFW","ARX200","F90","POF-9",
    ],
    "SMGs": [
        "MP5","MP7","MPX","P90","9x19VSN","Mx4 Storm","PDW9","Vector .45",
        "T-5 SMG","FMG-9","M12","MP5SD","MP5K","UMP45","SCORPION EVO 3 A1",
        "SPSMG9","Smg12","Smg11",
    ],
    "LMGs":     ["LMG-E","6P41","M249","ALDA 5.56","T-95 LSW"],
    "DMRs":     ["MK14 EBR","417","SR-25","CAMRS","AR-15.50","OTS-03"],
    "SHOTGUNS": [
        "M590A1","M1014","SPAS-12","SPAS-15","Supernova","SG-CQB",
        "SIX12","SIX12 SD","Super Shorty","FO-12","ACS12","TCSG12",
        "ITA12S","ITA12L",
    ],
    "PISTOLS": [
        "P226 MK25","P229","P9","P10C","PRB92","GSH-18","PMM","P12",
        "USP40","M45 MEUSOC","1911 TACOPS","5.7 USG","D-50",
        ".44 Mag Semi-Auto","LFP586","RG15","SDP 9mm","Luison","MK1 9mm",
    ],
}

SCOPE_MODES = ["HIP", "1.0x", "2.5x"]


def _profile(weapon: str) -> dict:
    d = WEAPON_DATA.get(weapon)
    if not d:
        return {
            "rpm": 600, "comp_y": 18.0, "comp_x": -2.0,
            "fire_rate_ms": 100.0, "spray_length": 30, "ramp_ticks": 2,
        }
    rpm, cy, cx, spray, ramp = d
    return {
        "rpm":          rpm,
        "comp_y":       float(cy),
        "comp_x":       float(cx),
        "fire_rate_ms": round(60000 / rpm, 2),
        "spray_length": spray,
        "ramp_ticks":   ramp,
    }


# ─────────────────────────────────────────────────────────
# Sensitivity config
#
# pixel_y = comp_y * (BASE_SENS / v_sens) * strength
# pixel_x = comp_x * (BASE_SENS / h_sens) * strength
#
# ADS: crosshair moves (ads_frac) as far per pixel at that scope.
# Same angular recoil needs MORE pixels → divide by fraction.
# ─────────────────────────────────────────────────────────
class SensConfig:
    def __init__(self):
        self.h         = 19.0
        self.v         = 14.0
        self.scope_1x  = 0.48
        self.scope_25x = 0.64
        self.strength  = 2.5    # default: 28.9px/tick at V=14 on ARs

    def scale(self, mode: str) -> tuple[float, float]:
        sx = (BASE_SENS / max(self.h, 0.1)) * self.strength
        sy = (BASE_SENS / max(self.v, 0.1)) * self.strength
        if mode == "1.0x":
            sx /= max(self.scope_1x,  0.01)
            sy /= max(self.scope_1x,  0.01)
        elif mode == "2.5x":
            sx /= max(self.scope_25x, 0.01)
            sy /= max(self.scope_25x, 0.01)
        return sx, sy


class KeyConfig:
    def __init__(self):
        self.scope = "s"
        self.show  = "shift_r"
        self.exit  = "f10"


# ─────────────────────────────────────────────────────────
# Raw mouse reader — message-only Win32 window
# EWMA sampler reads back actual delta post-burst
# ─────────────────────────────────────────────────────────
WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_long, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)


class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style",          wt.UINT),         ("lpfnWndProc",   WNDPROC),
        ("cbClsExtra",     ctypes.c_int),     ("cbWndExtra",    ctypes.c_int),
        ("hInstance",      wt.HINSTANCE),     ("hIcon",         ctypes.c_void_p),
        ("hCursor",        ctypes.c_void_p),  ("hbrBackground", ctypes.c_void_p),
        ("lpszMenuName",   wt.LPCWSTR),       ("lpszClassName", wt.LPCWSTR),
    ]


class RAWINPUTDEVICE(ctypes.Structure):
    _fields_ = [
        ("usUsagePage", ctypes.c_ushort), ("usUsage",    ctypes.c_ushort),
        ("dwFlags",     wt.DWORD),        ("hwndTarget", wt.HWND),
    ]


class RAWINPUTHEADER(ctypes.Structure):
    _fields_ = [
        ("dwType",  wt.DWORD),  ("dwSize",  wt.DWORD),
        ("hDevice", wt.HANDLE), ("wParam",  wt.WPARAM),
    ]


class RAWMOUSE(ctypes.Structure):
    _fields_ = [
        ("usFlags",            ctypes.c_ushort), ("usButtonFlags", ctypes.c_ushort),
        ("usButtonData",       ctypes.c_ushort), ("ulRawButtons",  ctypes.c_ulong),
        ("lLastX",             ctypes.c_long),   ("lLastY",        ctypes.c_long),
        ("ulExtraInformation", ctypes.c_ulong),
    ]


class RAWINPUT(ctypes.Structure):
    _fields_ = [("header", RAWINPUTHEADER), ("mouse", RAWMOUSE)]


class RawMouseReader:
    def __init__(self, cb):
        self._cb = cb
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        u32   = ctypes.windll.user32
        hinst = ctypes.windll.kernel32.GetModuleHandleW(None)
        cname = "RSv16_RawSink"

        def _proc(hwnd, msg, wp, lp):
            try:
                if msg == 0x00FF:
                    sz = ctypes.c_uint(0)
                    u32.GetRawInputData(lp, 0x10000003, None,
                                        ctypes.byref(sz), ctypes.sizeof(RAWINPUTHEADER))
                    buf = (ctypes.c_byte * sz.value)()
                    u32.GetRawInputData(lp, 0x10000003, buf,
                                        ctypes.byref(sz), ctypes.sizeof(RAWINPUTHEADER))
                    ri = ctypes.cast(buf, ctypes.POINTER(RAWINPUT)).contents
                    if ri.header.dwType == 0 and (ri.mouse.usFlags & 1) == 0:
                        self._cb(int(ri.mouse.lLastX), int(ri.mouse.lLastY))
                elif msg == 0x0002:
                    u32.PostQuitMessage(0)
            except Exception:
                pass
            return u32.DefWindowProcW(hwnd, msg, wp, lp)

        fn = WNDPROC(_proc)
        wc = WNDCLASSW()
        wc.lpfnWndProc   = fn
        wc.hInstance     = hinst
        wc.lpszClassName = cname
        u32.RegisterClassW(ctypes.byref(wc))
        hwnd = u32.CreateWindowExW(0, cname, None, 0, 0, 0, 0, 0,
                                   ctypes.c_void_p(-3), None, hinst, None)
        rid = RAWINPUTDEVICE(0x01, 0x02, 0x00000100, hwnd)
        u32.RegisterRawInputDevices(ctypes.byref(rid), 1, ctypes.sizeof(rid))
        msg = wt.MSG()
        while u32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            u32.TranslateMessage(ctypes.byref(msg))
            u32.DispatchMessageW(ctypes.byref(msg))


# ─────────────────────────────────────────────────────────
# EWMA sampler — adapts comp_y toward measured recoil mean
# alpha=0.25: slow enough to ignore outliers, fast enough to converge
# ─────────────────────────────────────────────────────────
class RecoilSampler:
    ALPHA   = 0.25
    MIN_PTS = 5
    DEAD    = 0.05

    def __init__(self):
        self._buf:    list[float] = []
        self._lock    = threading.Lock()
        self._active  = False
        self.last_det = 0.0

    def arm(self):
        with self._lock:
            self._buf.clear()
            self._active = True

    def push(self, dy: float):
        with self._lock:
            if self._active and dy < 0:
                self._buf.append(-dy)

    def commit(self, current_comp: float) -> float:
        with self._lock:
            buf = list(self._buf)
            self._buf.clear()
            self._active = False
        if len(buf) < self.MIN_PTS:
            return current_comp
        mean = sum(buf) / len(buf)
        if mean < self.DEAD:
            return current_comp
        self.last_det = round(mean, 2)
        return round(max(0.5, min(30.0,
               current_comp + self.ALPHA * (mean - current_comp))), 2)


# ─────────────────────────────────────────────────────────
# Anti-recoil engine
#
# Monotonic deadline scheduler:
#   next_deadline = burst_start + tick * interval
#   sleep(deadline - now)
#
# Scheduler wakeup jitter self-corrects every tick.
# timeBeginPeriod(1) at module load ensures <1ms wakeup variance.
# Move fires BEFORE sleep — zero startup lag on LMB down.
# ─────────────────────────────────────────────────────────
class AntiRecoil:
    def __init__(self, sens: SensConfig):
        self._prof  = _profile("R4-C")
        self._sens  = sens
        self._mode  = "HIP"
        self.active = False
        self._tick  = 0
        self._lock  = threading.Lock()

    def set_mode(self, m: str):      self._mode           = m
    def set_comp_y(self, v: float):  self._prof["comp_y"] = v
    def get_comp_y(self) -> float:   return self._prof["comp_y"]

    def _ramp(self, base: float, tick: int) -> float:
        r = self._prof.get("ramp_ticks", 0)
        if r == 0 or tick >= r:
            return base
        return base * ((tick + 1) / max(r, 1))

    def _run(self):
        interval  = self._prof["fire_rate_ms"] / 1000.0
        max_ticks = self._prof["spray_length"]
        sx, sy    = self._sens.scale(self._mode)

        burst_start = time.monotonic()
        tick = 0

        while self.active and tick < max_ticks:
            # move first — fires on LMB down with zero delay
            cy = self._ramp(self._prof["comp_y"], tick)
            cx = self._ramp(self._prof["comp_x"], tick)
            dy = max(1, round(cy * sy))
            dx = round(cx * sx)
            _move(dx, dy)

            tick += 1
            with self._lock:
                self._tick = tick

            # sleep only the remaining gap to the next deadline
            next_deadline = burst_start + tick * interval
            remaining     = next_deadline - time.monotonic()
            if remaining > 0:
                time.sleep(remaining)

        with self._lock:
            self.active = False

    def start_firing(self):
        with self._lock:
            if self.active:
                return
            self.active = True
            self._tick  = 0
        threading.Thread(target=self._run, daemon=True).start()

    def stop_firing(self):
        with self._lock:
            self.active = False
            self._tick  = 0

    def set_profile(self, w: str):
        self.stop_firing()
        self._prof = _profile(w)

    def comp_display(self) -> tuple[str, str]:
        sx, sy = self._sens.scale(self._mode)
        cy = self._prof["comp_y"]
        cx = self._prof["comp_x"]
        sign = "←" if cx < 0 else ("→" if cx > 0 else "─")
        return (
            f"{cy:.1f}→{cy * sy:.1f}px",
            f"{sign}{abs(cx):.1f}→{abs(cx * sx):.1f}px",
        )


# ─────────────────────────────────────────────────────────
# Coordinator — RMB arms, LMB fires, release either stops
# ─────────────────────────────────────────────────────────
class RecoilSystem:
    def __init__(self, log_cb=None, comp_cb=None):
        self._log_cb   = log_cb
        self._comp_cb  = comp_cb
        self.sessions  = 0
        self.sens      = SensConfig()
        self.keys      = KeyConfig()
        self.ar        = AntiRecoil(self.sens)
        self.sampler   = RecoilSampler()
        self._scope_idx = 0
        self._rmb_held  = False
        self._lmb_held  = False
        RawMouseReader(self._on_raw)

    def _on_raw(self, dx: int, dy: int):
        if self.ar.active:
            self.sampler.push(float(dy))

    def _log(self, m: str):
        print(m)
        if self._log_cb:
            self._log_cb(m)

    def set_weapon(self, w: str):
        self.ar.set_profile(w)
        p = _profile(w)
        _, sy = self.sens.scale(self.ar._mode)
        self._log(
            f"[WPN] {w}  {p['rpm']}RPM  "
            f"comp_y={p['comp_y']}  px/tick={p['comp_y'] * sy:.1f}  "
            f"comp_x={p['comp_x']}  mode={self.ar._mode}"
        )
        return p

    def cycle_scope(self) -> str:
        self._scope_idx = (self._scope_idx + 1) % len(SCOPE_MODES)
        mode = SCOPE_MODES[self._scope_idx]
        self.ar.set_mode(mode)
        self._log(f"[SCOPE] {mode}")
        return mode

    def on_rmb_down(self):
        self._rmb_held = True
        self.sampler.arm()

    def on_rmb_up(self):
        self._rmb_held = False
        self._stop_if_firing()

    def on_lmb_down(self):
        self._lmb_held = True
        if self._rmb_held:
            self.ar.start_firing()

    def on_lmb_up(self):
        self._lmb_held = False
        self._stop_if_firing()

    def _stop_if_firing(self):
        if self.ar.active:
            self.ar.stop_firing()
            old = self.ar.get_comp_y()
            new = self.sampler.commit(old)
            if new != old:
                self.sessions += 1
                self.ar.set_comp_y(new)
                self._log(
                    f"[EWMA] #{self.sessions}  "
                    f"det={self.sampler.last_det:.2f}  "
                    f"{old:.1f}→{new:.1f} "
                    f"{'↑' if new > old else '↓'}"
                )
                if self._comp_cb:
                    self._comp_cb(new)


# ─────────────────────────────────────────────────────────
# GUI palette — darker and more ghost than v13
# ─────────────────────────────────────────────────────────
BG      = "#050509"
BG2     = "#0a0a14"
BG3     = "#111120"
BG4     = "#181828"
FG      = "#b8bedd"
FG2     = "#42465e"
FG3     = "#6870a0"
RED     = "#e03a55"
GREEN   = "#24c070"
BLUE    = "#3880f8"
AMBER   = "#e89820"
PURPLE  = "#9060f0"
TEAL    = "#20c8c0"
BORDER  = "#181828"
BORDER2 = "#222238"

MONO   = ("Consolas", 9)
MONOS  = ("Consolas", 8)
MONOB  = ("Consolas", 9, "bold")

SCOPE_COLORS = {"HIP": FG3, "1.0x": BLUE, "2.5x": PURPLE}
STATUS = {
    "idle":   (FG2,   "IDLE",   "Hold RMB"),
    "armed":  (AMBER, "ARMED",  "Press LMB"),
    "firing": (RED,   "FIRING", "Pulling ▼"),
}


# ─────────────────────────────────────────────────────────
# Win32 TOOLWINDOW flag — strips overlay from taskbar + alt-tab.
# R6S never sees this window as a competing foreground app.
# Applied 150ms after mainloop starts so HWND is fully registered.
# ─────────────────────────────────────────────────────────
def _apply_toolwindow(root: tk.Tk) -> None:
    GWL_EXSTYLE      = -20
    WS_EX_TOOLWINDOW = 0x00000080
    WS_EX_APPWINDOW  = 0x00040000
    hwnd  = ctypes.windll.user32.GetParent(root.winfo_id())
    style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    style = (style | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW
    ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
    ctypes.windll.user32.SetWindowPos(
        hwnd, ctypes.c_void_p(-1), 0, 0, 0, 0,
        0x0001 | 0x0002 | 0x0010   # SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE
    )


def launch_gui():
    from pynput import mouse as pm, keyboard as pk

    sys_obj = RecoilSystem()

    root = tk.Tk()
    root.title("R6S · v16")
    root.configure(bg=BG)
    root.resizable(False, False)
    root.wm_attributes("-topmost", True)
    root.wm_attributes("-alpha",   0.68)   # more ghost
    root.overrideredirect(True)

    # ── GUI event queue (pynput runs off the Tk thread) ───
    _q: queue.Queue = queue.Queue()

    def _pump():
        try:
            while True:
                _q.get_nowait()()
        except queue.Empty:
            pass
        root.after(14, _pump)

    root.after(14, _pump)
    def gui(fn): _q.put(fn)

    # ── drag ──────────────────────────────────────────────
    _drag = {"x": 0, "y": 0}
    def _ds(e): _drag["x"] = e.x_root - root.winfo_x(); _drag["y"] = e.y_root - root.winfo_y()
    def _dm(e): root.geometry(f"+{e.x_root - _drag['x']}+{e.y_root - _drag['y']}")

    # ── widget factories ──────────────────────────────────
    def L(p, t="", f=MONO, fg=FG2, bg=BG, **kw):
        return tk.Label(p, text=t, font=f, fg=fg, bg=bg, **kw)
    def F(p, bg=BG, **kw):
        return tk.Frame(p, bg=bg, **kw)
    def B(p, t, cmd, fg=FG2, bg=BG, f=MONOS, **kw):
        return tk.Button(p, text=t, command=cmd, font=f, fg=fg, bg=bg,
                         activebackground=BG3, activeforeground=FG,
                         relief="flat", bd=0, cursor="hand2", **kw)
    def divider(p, color=BORDER2):
        tk.Frame(p, bg=color, height=1).pack(fill="x")

    # ══════════════════════════════════════════════════════
    # TITLE BAR
    # ══════════════════════════════════════════════════════
    tbar = F(root, bg=BG2, highlightthickness=1, highlightbackground=BORDER2)
    tbar.pack(fill="x")
    tbar.bind("<Button-1>", _ds)
    tbar.bind("<B1-Motion>", _dm)

    L(tbar, "◈", f=("Consolas", 12, "bold"), fg=RED, bg=BG2).pack(side="left", padx=(8, 3), pady=5)
    L(tbar, "R6S  RECOIL  v16", f=MONOB, fg=FG, bg=BG2).pack(side="left", pady=5)

    ctrl = F(tbar, bg=BG2)
    ctrl.pack(side="right", padx=4, pady=3)

    _min = [False]
    _cfg = [False]
    body_frame = None
    cfg_frame  = None

    def _toggle_min():
        if _min[0]:
            body_frame.pack(fill="x")
            if _cfg[0]: cfg_frame.pack(fill="x")
            _min[0] = False
        else:
            body_frame.pack_forget()
            if _cfg[0]: cfg_frame.pack_forget()
            _min[0] = True
        root.update_idletasks()

    def _toggle_cfg():
        if cfg_frame is None: return
        if _cfg[0]:
            cfg_frame.pack_forget()
            _cfg[0] = False
        else:
            if not _min[0]: cfg_frame.pack(fill="x")
            _cfg[0] = True
        root.update_idletasks()

    B(ctrl, "─", _toggle_min, fg=FG2, bg=BG2, padx=7).pack(side="left")
    B(ctrl, "⚙", _toggle_cfg, fg=FG3, bg=BG2, padx=7).pack(side="left")
    B(ctrl, "✕", root.destroy, fg=RED,  bg=BG2, padx=7).pack(side="left")

    divider(root, BORDER2)

    # ══════════════════════════════════════════════════════
    # BODY
    # ══════════════════════════════════════════════════════
    body_frame = F(root, bg=BG)
    body_frame.pack(fill="x")

    # ── row 1: status ─────────────────────────────────────
    r1 = F(body_frame, bg=BG)
    r1.pack(fill="x", padx=8, pady=(7, 1))

    arm_dot   = L(r1, "●", f=("Consolas", 13, "bold"), fg=FG2, bg=BG)
    arm_dot.pack(side="left", padx=(0, 5))
    arm_state = L(r1, "IDLE",     f=MONOB, fg=FG2, bg=BG, width=7,  anchor="w")
    arm_state.pack(side="left")
    arm_sub   = L(r1, "Hold RMB", f=MONOS, fg=FG2, bg=BG, width=10, anchor="w")
    arm_sub.pack(side="left", padx=(0, 6))

    L(r1, "│", fg=BORDER2, bg=BG).pack(side="left", padx=3)
    scope_lbl = L(r1, "HIP", f=MONOB, fg=FG3, bg=BG, width=4, anchor="w")
    scope_lbl.pack(side="left")
    L(r1, "│", fg=BORDER2, bg=BG).pack(side="left", padx=3)

    wpn_lbl = L(r1, "R4-C", f=MONOB, fg=FG, bg=BG, width=20, anchor="w")
    wpn_lbl.pack(side="left")
    rpm_lbl = L(r1, "880 RPM", f=MONOS, fg=FG2, bg=BG)
    rpm_lbl.pack(side="right", padx=(0, 2))

    # ── row 2: comp readout ───────────────────────────────
    r2 = F(body_frame, bg=BG)
    r2.pack(fill="x", padx=8, pady=(0, 1))

    L(r2, "Y", f=MONOS, fg=FG2, bg=BG).pack(side="left")
    cy_lbl = L(r2, "─", f=MONOB, fg=BLUE,  bg=BG, width=12, anchor="w")
    cy_lbl.pack(side="left", padx=(2, 10))

    L(r2, "X", f=MONOS, fg=FG2, bg=BG).pack(side="left")
    cx_lbl = L(r2, "─", f=MONOB, fg=AMBER, bg=BG, width=12, anchor="w")
    cx_lbl.pack(side="left", padx=(2, 0))

    sess_lbl = L(r2, "0 adapt", f=MONOS, fg=GREEN, bg=BG)
    sess_lbl.pack(side="right", padx=(0, 2))

    # ── row 3: strength slider ────────────────────────────
    r3 = F(body_frame, bg=BG3, highlightthickness=1, highlightbackground=BORDER2)
    r3.pack(fill="x", padx=8, pady=(2, 2))

    L(r3, "STR", f=MONOS, fg=FG2, bg=BG3, width=4).pack(side="left", padx=(6, 2), pady=4)

    str_var = tk.DoubleVar(value=sys_obj.sens.strength)
    str_val = L(r3, f"{sys_obj.sens.strength:.2f}×", f=MONOB, fg=TEAL, bg=BG3, width=6)
    str_val.pack(side="right", padx=(0, 6))

    def _on_strength(v):
        val = round(float(v), 2)
        sys_obj.sens.strength = val
        str_val.configure(text=f"{val:.2f}×")
        _refresh_comp()

    tk.Scale(
        r3, variable=str_var, from_=0.5, to=3.0, resolution=0.05,
        orient="horizontal", length=200, showvalue=False,
        bg=BG3, troughcolor=BG4, activebackground=TEAL,
        highlightthickness=0, bd=0, command=_on_strength,
    ).pack(side="left", padx=4, pady=3, fill="x", expand=True)

    # ── row 4: weapon dropdowns + scope btn ──────────────
    r4 = F(body_frame, bg=BG3, highlightthickness=1, highlightbackground=BORDER2)
    r4.pack(fill="x", padx=8, pady=(0, 7))

    cat_var = tk.StringVar(value="ASSAULT RIFLES")
    wpn_var = tk.StringVar(value="R4-C")

    def _mk_om(parent, var, vals, w=16):
        m = tk.OptionMenu(parent, var, *vals)
        m.configure(font=MONOS, fg=FG, bg=BG3,
                    activebackground=BG2, activeforeground=TEAL,
                    relief="flat", bd=0, highlightthickness=0,
                    indicatoron=True, width=w)
        m["menu"].configure(font=MONOS, fg=FG, bg=BG3,
                            activebackground=RED, activeforeground=FG)
        return m

    cat_menu = _mk_om(r4, cat_var, list(WEAPON_REGISTRY.keys()), w=14)
    cat_menu.pack(side="left", padx=(4, 0), pady=3)

    wpn_menu = _mk_om(r4, wpn_var, WEAPON_REGISTRY["ASSAULT RIFLES"], w=20)
    wpn_menu.pack(side="left", padx=2, pady=3)

    def _rebuild_weapons(cat):
        m = wpn_menu["menu"]
        m.delete(0, "end")
        for w in WEAPON_REGISTRY[cat]:
            m.add_command(label=w, command=lambda v=w: wpn_var.set(v))
        wpn_var.set(WEAPON_REGISTRY[cat][0])

    def _on_cat(*_): _rebuild_weapons(cat_var.get())
    def _on_wpn(*_):
        w = wpn_var.get()
        if not w: return
        p = sys_obj.set_weapon(w)
        wpn_lbl.configure(text=w)
        rpm_lbl.configure(text=f"{p['rpm']} RPM")
        _refresh_comp()

    cat_var.trace_add("write", _on_cat)
    wpn_var.trace_add("write", _on_wpn)
    _rebuild_weapons("ASSAULT RIFLES")

    scope_btn = B(r4, "SCOPE: HIP", lambda: None, fg=FG3, bg=BG4, f=MONOS, padx=6, pady=2)
    scope_btn.pack(side="right", padx=(0, 4), pady=3)

    def _do_scope():
        mode = sys_obj.cycle_scope()
        c = SCOPE_COLORS.get(mode, FG3)
        scope_btn.configure(text=f"SCOPE: {mode}", fg=c)
        scope_lbl.configure(text=mode, fg=c)
        _refresh_comp()

    scope_btn.configure(command=_do_scope)

    divider(root, BORDER)

    # ══════════════════════════════════════════════════════
    # CONFIG PANEL (⚙ toggle)
    # ══════════════════════════════════════════════════════
    cfg_frame = F(root, bg=BG2, highlightthickness=1, highlightbackground=BORDER2)

    L(cfg_frame, "SENSITIVITY", f=MONOB, fg=TEAL, bg=BG2).pack(anchor="w", padx=10, pady=(8, 2))

    sens_fields: dict[str, tk.StringVar] = {}

    def _srow(label, key, default, color=AMBER):
        r = F(cfg_frame, bg=BG2)
        r.pack(fill="x", padx=10, pady=2)
        L(r, label, f=MONOS, fg=FG2, bg=BG2, width=24, anchor="w").pack(side="left")
        var = tk.StringVar(value=default)
        sens_fields[key] = var
        tk.Entry(r, textvariable=var, font=MONOB, fg=color, bg=BG3,
                 insertbackground=color, relief="flat",
                 highlightthickness=1, highlightbackground=BORDER2,
                 width=7, justify="center").pack(side="left")

    _srow("Horizontal Sens",   "h",   "19", AMBER)
    _srow("Vertical Sens",     "v",   "14", AMBER)
    _srow("1.0x ADS  (% hip)", "s1",  "48", BLUE)
    _srow("2.5x ADS  (% hip)", "s25", "64", PURPLE)

    sens_ok = L(cfg_frame, "", f=MONOS, fg=GREEN, bg=BG2)
    sens_ok.pack(anchor="w", padx=10)

    def _apply_sens():
        try:
            h   = float(sens_fields["h"].get())
            v   = float(sens_fields["v"].get())
            s1  = float(sens_fields["s1"].get())
            s25 = float(sens_fields["s25"].get())
            assert 0.1 <= h   <= 100
            assert 0.1 <= v   <= 100
            assert 1   <= s1  <= 100
            assert 1   <= s25 <= 100
        except Exception:
            sens_ok.configure(text="✕  Invalid", fg=RED)
            return
        sys_obj.sens.h         = h
        sys_obj.sens.v         = v
        sys_obj.sens.scope_1x  = s1  / 100.0
        sys_obj.sens.scope_25x = s25 / 100.0
        sens_ok.configure(text=f"✓  H={h}  V={v}  1x={s1}%  2.5x={s25}%", fg=GREEN)
        sys_obj._log(f"[SENS] H={h} V={v} 1x={s1/100:.2f} 2.5x={s25/100:.2f}")
        _refresh_comp()

    B(cfg_frame, "APPLY SENS", _apply_sens, fg=BG, bg=TEAL, f=MONOB,
      padx=12, pady=4).pack(anchor="w", padx=10, pady=(4, 6))

    divider(cfg_frame, BORDER2)

    L(cfg_frame, "KEYBINDS", f=MONOB, fg=TEAL, bg=BG2).pack(anchor="w", padx=10, pady=(6, 2))

    key_vars: dict[str, tk.StringVar] = {}
    for attr, lbl_txt, default in [
        ("scope", "Cycle Scope",  sys_obj.keys.scope),
        ("show",  "Show / Hide",  sys_obj.keys.show),
        ("exit",  "Exit",         sys_obj.keys.exit),
    ]:
        r = F(cfg_frame, bg=BG2)
        r.pack(fill="x", padx=10, pady=2)
        L(r, lbl_txt, f=MONOS, fg=FG2, bg=BG2, width=14, anchor="w").pack(side="left")
        var = tk.StringVar(value=default)
        key_vars[attr] = var
        ent = tk.Entry(r, textvariable=var, font=MONOB, fg=AMBER, bg=BG3,
                       insertbackground=AMBER, relief="flat",
                       highlightthickness=1, highlightbackground=BORDER2,
                       width=12, justify="center")
        ent.pack(side="left")
        ent.bind("<KeyPress>", lambda e, v=var: (v.set(e.keysym.lower()), "break")[1])

    key_ok = L(cfg_frame, "", f=MONOS, fg=GREEN, bg=BG2)
    key_ok.pack(anchor="w", padx=10)

    def _apply_keys():
        for attr in key_vars:
            setattr(sys_obj.keys, attr, key_vars[attr].get().strip())
        key_ok.configure(text="✓  Applied", fg=GREEN)
        sys_obj._log(f"[KEYS] scope={sys_obj.keys.scope} show={sys_obj.keys.show} exit={sys_obj.keys.exit}")

    B(cfg_frame, "APPLY KEYS", _apply_keys, fg=BG, bg=TEAL, f=MONOB,
      padx=12, pady=4).pack(anchor="w", padx=10, pady=(4, 10))

    # ── live refresh ──────────────────────────────────────
    def _refresh_comp():
        cy_s, cx_s = sys_obj.ar.comp_display()
        cy_lbl.configure(text=cy_s)
        cx_lbl.configure(text=cx_s)

    def _set_arm(state: str):
        c, t, s = STATUS[state]
        arm_dot.configure(fg=c)
        arm_state.configure(text=t, fg=c)
        arm_sub.configure(text=s)

    def _tick():
        sess_lbl.configure(text=f"{sys_obj.sessions} adapt")
        _refresh_comp()
        root.after(400, _tick)

    root.after(400, _tick)

    _vis = [True]
    def _toggle_vis():
        if _vis[0]:
            root.withdraw(); _vis[0] = False
        else:
            root.deiconify(); root.lift()
            root.wm_attributes("-topmost", True); _vis[0] = True

    # ── pynput listeners ──────────────────────────────────
    def _kname(key):
        try:
            if hasattr(key, "char") and key.char: return key.char.lower()
        except Exception: pass
        try: return key.name.lower()
        except Exception: pass
        return None

    def on_click(x, y, button, pressed):
        try:
            from pynput.mouse import Button
            if button == Button.right:
                if pressed:
                    gui(sys_obj.on_rmb_down)
                    gui(lambda: _set_arm("armed"))
                else:
                    gui(sys_obj.on_rmb_up)
                    gui(lambda: _set_arm("idle"))
            elif button == Button.left:
                if pressed:
                    gui(sys_obj.on_lmb_down)
                    if sys_obj._rmb_held: gui(lambda: _set_arm("firing"))
                else:
                    gui(sys_obj.on_lmb_up)
                    if sys_obj._rmb_held: gui(lambda: _set_arm("armed"))
        except Exception: pass

    def on_key(key):
        try:
            name = _kname(key)
            if not name: return
            k = sys_obj.keys
            if   name == k.scope: gui(_do_scope)
            elif name == k.show:  gui(_toggle_vis)
            elif name == k.exit:
                gui(root.destroy)
                return False
        except Exception: pass

    ml = pm.Listener(on_click=on_click)
    kl = pk.Listener(on_press=on_key)
    ml.daemon = kl.daemon = True
    ml.start(); kl.start()

    # ── startup ───────────────────────────────────────────
    sys_obj.set_weapon("R4-C")
    _refresh_comp()

    root.update_idletasks()
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    root.geometry(f"+{(sw - root.winfo_width()) // 2}+{(sh - root.winfo_height()) // 2}")

    root.after(150, lambda: _apply_toolwindow(root))
    root.mainloop()

    # clean up timer resolution on exit
    try:
        ctypes.windll.winmm.timeEndPeriod(1)
    except Exception:
        pass


if __name__ == "__main__":
    launch_gui()
