Keys (default): S=scope cycle | RShift=show/hide | F10=exit
Deps: pip install pynput
"""

import ctypes
import ctypes.wintypes as wt
import threading
import time
import tkinter as tk
from tkinter import ttk
import queue
from ctypes import wintypes

# ─────────────────────────────────────────────────────────
# Tuning baseline — table tuned at these reference values.
# Changing BASE_H/V shifts every weapon's effective pixel output.
# ─────────────────────────────────────────────────────────
BASE_H = 9.0
BASE_V = 9.0

# ─────────────────────────────────────────────────────────
# SendInput — raw relative mouse move, bypasses GetCursorPos
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


def _move_mouse(dx: int, dy: int):
    if dx == 0 and dy == 0:
        return
    extra = ctypes.pointer(ctypes.c_ulong(0))
    mi    = MOUSEINPUT(dx, dy, 0, MOUSEEVENTF_MOVE, 0, extra)
    inp   = INPUT(INPUT_MOUSE, _INPUT_UNION(mi=mi))
    SendInput(1, ctypes.pointer(inp), ctypes.sizeof(inp))


# ─────────────────────────────────────────────────────────
# Weapon profiles — comp_y/comp_x are RAW (unscaled).
# Boosted ~40% from v10 to compensate for high-sens scaling.
# Scale applied at fire time, never stored in profile.
#
# Tuple format: (rpm, comp_y, comp_x, spray_length, ramp_ticks)
# ─────────────────────────────────────────────────────────

WEAPON_DATA = {
    # ASSAULT RIFLES
    "R4-C":        (880,  10, 1, 30, 5),
    "AK-12":       (650,   9, 1, 30, 5),
    "C7E":         (800,  10, 1, 30, 5),
    "F2":          (980,  11, 1, 30, 5),
    "L85A2":       (670,   9, 1, 30, 5),
    "AR33":        (750,  10, 1, 30, 5),
    "556xi":       (690,   9, 1, 30, 5),
    "M4":          (750,  10, 1, 30, 5),
    "V308":        (700,   9, 1, 30, 5),
    "SPEAR .308":  (700,   9, 1, 30, 5),
    "Type-89":     (850,  10, 1, 30, 5),
    "M762":        (730,  10, 2, 30, 5),
    "C8-SFW":      (780,  10, 1, 30, 5),
    "ARX200":      (700,   9, 1, 30, 5),
    "F90":         (780,  10, 1, 30, 5),
    "POF-9":       (700,   9, 1, 30, 5),
    # SMGs
    "MP5":         (800,   7, 0, 25, 3),
    "MP7":         (950,   7, 0, 25, 3),
    "MPX":         (857,   7, 0, 25, 3),
    "P90":         (970,   7, 0, 30, 3),
    "9x19VSN":     (750,   6, 0, 25, 3),
    "Mx4 Storm":   (950,   7, 0, 25, 3),
    "PDW9":        (800,   7, 0, 25, 3),
    "Vector .45":  (1200,  9, 1, 25, 3),
    "T-5 SMG":     (900,   7, 0, 25, 3),
    "FMG-9":       (1100,  9, 0, 25, 3),
    "M12":         (550,   6, 0, 25, 3),
    "MP5SD":       (800,   7, 0, 25, 3),
    "MP5K":        (800,   7, 0, 25, 3),
    "UMP45":       (600,   6, 0, 25, 3),
    "SCORPION EVO 3 A1": (1080, 9, 1, 30, 3),
    "SPSMG9":      (980,   7, 0, 25, 3),
    "Smg12":       (1270,  9, 0, 20, 2),
    "Smg11":       (1270,  9, 0, 20, 2),
    # LMGs
    "LMG-E":       (650,   9, 0, 35, 6),
    "6P41":        (650,   9, 0, 35, 6),
    "M249":        (750,   9, 0, 35, 6),
    "ALDA 5.56":   (900,  10, 1, 35, 6),
    "T-95 LSW":    (650,   9, 0, 35, 6),
    # DMRs
    "MK14 EBR":    (260,   6, 0, 8,  0),
    "417":         (200,   6, 0, 8,  0),
    "SR-25":       (260,   6, 0, 8,  0),
    "CAMRS":       (300,   6, 0, 8,  0),
    "AR-15.50":    (240,   6, 0, 8,  0),
    "OTS-03":      (200,   6, 0, 8,  0),
    # SHOTGUNS
    "M590A1":      (75,   11, 0, 6,  0),
    "M1014":       (100,  11, 0, 6,  0),
    "SPAS-12":     (67,   11, 0, 6,  0),
    "SPAS-15":     (150,  11, 0, 6,  0),
    "Supernova":   (75,   11, 0, 6,  0),
    "SG-CQB":      (75,   11, 0, 6,  0),
    "SIX12":       (150,  11, 0, 6,  0),
    "SIX12 SD":    (150,  11, 0, 6,  0),
    "Super Shorty":(150,  11, 0, 6,  0),
    "FO-12":       (200,  11, 0, 6,  0),
    "ACS12":       (300,  11, 0, 8,  0),
    "TCSG12":      (150,  10, 0, 6,  0),
    "ITA12S":      (75,   11, 0, 6,  0),
    "ITA12L":      (75,   11, 0, 6,  0),
    # PISTOLS
    "P226 MK25":   (450,   5, 0, 6,  0),
    "P229":        (450,   5, 0, 6,  0),
    "P9":          (450,   5, 0, 6,  0),
    "P10C":        (450,   5, 0, 6,  0),
    "PRB92":       (450,   5, 0, 6,  0),
    "GSH-18":      (600,   5, 0, 6,  0),
    "PMM":         (600,   5, 0, 6,  0),
    "P12":         (450,   5, 0, 6,  0),
    "USP40":       (450,   5, 0, 6,  0),
    "M45 MEUSOC":  (450,   5, 0, 6,  0),
    "1911 TACOPS": (450,   5, 0, 6,  0),
    "5.7 USG":     (450,   5, 0, 6,  0),
    "D-50":        (300,   6, 0, 6,  0),
    ".44 Mag Semi-Auto": (300, 6, 0, 6, 0),
    "LFP586":      (174,   7, 0, 6,  0),
    "RG15":        (450,   5, 0, 6,  0),
    "SDP 9mm":     (450,   5, 0, 6,  0),
}

WEAPON_REGISTRY = {
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
        ".44 Mag Semi-Auto","LFP586","RG15","SDP 9mm",
    ],
}

SCOPE_MODES = ["HIP", "1.0x", "2.5x"]


def _profile(weapon: str) -> dict:
    d = WEAPON_DATA.get(weapon)
    if not d:
        return {
            "rpm": 600, "comp_y": 9.0, "comp_x": 0.0,
            "fire_rate_ms": 100.0, "spray_length": 30, "ramp_ticks": 4,
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
# scope_1x / scope_25x are 0.0–1.0 multipliers matching
# the in-game ADS sliders as a fraction (e.g. 48% → 0.48)
# ─────────────────────────────────────────────────────────

class SensConfig:
    def __init__(self):
        self.h         = 9.0
        self.v         = 9.0
        self.scope_1x  = 0.70
        self.scope_25x = 0.55

    def scale(self, mode: str) -> tuple[float, float]:
        sh = BASE_H / max(self.h, 0.1)
        sv = BASE_V / max(self.v, 0.1)
        m  = {"HIP": 1.0, "1.0x": self.scope_1x, "2.5x": self.scope_25x}.get(mode, 1.0)
        return sh * m, sv * m


# ─────────────────────────────────────────────────────────
# Keybind config — only 3 binds remain (scope, show, exit)
# ─────────────────────────────────────────────────────────

class KeyConfig:
    def __init__(self):
        self.scope = "s"
        self.show  = "shift_r"
        self.exit  = "f10"


# ─────────────────────────────────────────────────────────
# Raw mouse reader — message-only window
# ─────────────────────────────────────────────────────────

WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_long, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)


class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style",          wt.UINT),     ("lpfnWndProc",    WNDPROC),
        ("cbClsExtra",     ctypes.c_int), ("cbWndExtra",    ctypes.c_int),
        ("hInstance",      wt.HINSTANCE), ("hIcon",         ctypes.c_void_p),
        ("hCursor",        ctypes.c_void_p), ("hbrBackground", ctypes.c_void_p),
        ("lpszMenuName",   wt.LPCWSTR),  ("lpszClassName",  wt.LPCWSTR),
    ]


class RAWINPUTDEVICE(ctypes.Structure):
    _fields_ = [
        ("usUsagePage", ctypes.c_ushort), ("usUsage",  ctypes.c_ushort),
        ("dwFlags",     wt.DWORD),        ("hwndTarget", wt.HWND),
    ]


class RAWINPUTHEADER(ctypes.Structure):
    _fields_ = [
        ("dwType",  wt.DWORD), ("dwSize", wt.DWORD),
        ("hDevice", wt.HANDLE), ("wParam", wt.WPARAM),
    ]


class RAWMOUSE(ctypes.Structure):
    _fields_ = [
        ("usFlags",       ctypes.c_ushort), ("usButtonFlags", ctypes.c_ushort),
        ("usButtonData",  ctypes.c_ushort), ("ulRawButtons",  ctypes.c_ulong),
        ("lLastX",        ctypes.c_long),   ("lLastY",        ctypes.c_long),
        ("ulExtraInformation", ctypes.c_ulong),
    ]


class RAWINPUT(ctypes.Structure):
    _fields_ = [("header", RAWINPUTHEADER), ("mouse", RAWMOUSE)]


class RawMouseReader:
    def __init__(self, cb):
        self.cb = cb
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        u32   = ctypes.windll.user32
        hinst = ctypes.windll.kernel32.GetModuleHandleW(None)
        cname = "RSv11_RawSink"

        def _proc(hwnd, msg, wp, lp):
            try:
                if msg == 0x00FF:
                    sz = ctypes.c_uint(0)
                    u32.GetRawInputData(lp, 0x10000003, None,
                                        ctypes.byref(sz),
                                        ctypes.sizeof(RAWINPUTHEADER))
                    buf = (ctypes.c_byte * sz.value)()
                    u32.GetRawInputData(lp, 0x10000003, buf,
                                        ctypes.byref(sz),
                                        ctypes.sizeof(RAWINPUTHEADER))
                    ri = ctypes.cast(buf, ctypes.POINTER(RAWINPUT)).contents
                    if ri.header.dwType == 0 and (ri.mouse.usFlags & 1) == 0:
                        self.cb(int(ri.mouse.lLastX), int(ri.mouse.lLastY))
                elif msg == 0x0002:
                    u32.PostQuitMessage(0)
            except Exception:
                pass
            return u32.DefWindowProcW(hwnd, msg, wp, lp)

        fn = WNDPROC(_proc)
        wc = WNDCLASSW()
        wc.lpfnWndProc  = fn
        wc.hInstance    = hinst
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
# Recoil sampler — EWMA post-burst adapt
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
        return round(max(0.5, min(20.0,
               current_comp + self.ALPHA * (mean - current_comp))), 2)


# ─────────────────────────────────────────────────────────
# Anti-recoil engine
# comp_y/comp_x float — clamped to min 1px AFTER rounding
# ─────────────────────────────────────────────────────────

class AntiRecoil:
    def __init__(self, sens: SensConfig):
        self._prof   = _profile("R4-C")
        self._sens   = sens
        self._mode   = "HIP"
        self.active  = False
        self._tick   = 0
        self._lock   = threading.Lock()
        self._thread: threading.Thread | None = None

    def set_mode(self, m: str):    self._mode  = m
    def set_comp_y(self, v: float): self._prof["comp_y"] = v

    def _ramp(self, base: float) -> float:
        r = self._prof.get("ramp_ticks", 0)
        if r == 0 or self._tick >= r:
            return base
        return base * (self._tick / max(r, 1))

    def _run(self):
        rate = self._prof["fire_rate_ms"] / 1000.0
        maxT = self._prof["spray_length"]
        sx, sy = self._sens.scale(self._mode)

        while self.active and self._tick < maxT:
            raw_cy = self._ramp(self._prof["comp_y"]) * sy
            raw_cx = self._ramp(self._prof["comp_x"]) * sx

            dy = max(1, round(raw_cy))
            dx = round(raw_cx)

            _move_mouse(dx, dy)

            with self._lock:
                self._tick += 1
            time.sleep(rate)

        with self._lock:
            self.active = False

    def start_firing(self):
        with self._lock:
            if self.active:
                return
            self.active = True
            self._tick  = 0
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

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
        return (f"Y={cy:.1f} → {cy*sy:.1f}px",
                f"X={cx:.1f} → {cx*sx:.1f}px")


# ─────────────────────────────────────────────────────────
# Coordinator
# RMB = arm. LMB = fire. Both must be held to pull down.
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
        self._rmb_held  = False   # RMB = arm gate
        self._lmb_held  = False   # LMB = fire trigger
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
        p   = _profile(w)
        sx, sy = self.sens.scale(self.ar._mode)
        self._log(
            f"[WPN] {w}  {p['rpm']} RPM  "
            f"raw_y={p['comp_y']}  px_y={p['comp_y']*sy:.1f}  "
            f"mode={self.ar._mode}"
        )
        return p

    def cycle_scope(self) -> str:
        self._scope_idx = (self._scope_idx + 1) % len(SCOPE_MODES)
        mode = SCOPE_MODES[self._scope_idx]
        self.ar.set_mode(mode)
        self._log(f"[SCOPE] {mode}")
        return mode

    # ── RMB / LMB state machine ───────────────────────────

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
            old = self.ar._prof["comp_y"]
            new = self.sampler.commit(old)
            if new != old:
                self.sessions += 1
                self.ar.set_comp_y(new)
                self._log(
                    f"[AUTO] #{self.sessions}  "
                    f"det={self.sampler.last_det:.2f}  "
                    f"comp_y {old:.1f}→{new:.1f} "
                    f"{'↑' if new > old else '↓'}"
                )
                if self._comp_cb:
                    self._comp_cb(new)


# ─────────────────────────────────────────────────────────
# GUI — dark glass aesthetic, 15% transparent
# ─────────────────────────────────────────────────────────

BG      = "#07070d"
BG2     = "#0e0e18"
BG3     = "#161622"
BG4     = "#1c1c2e"
FG      = "#c8cde8"
FG2     = "#565a78"
FG3     = "#8890b8"
RED     = "#e84560"
GREEN   = "#27c97a"
BLUE    = "#3d8eff"
AMBER   = "#f0a025"
PURPLE  = "#9d6fff"
TEAL    = "#22d4c8"
BORDER  = "#1e1e30"
BORDER2 = "#2a2a40"

MONO    = ("Consolas", 9)
MONO_S  = ("Consolas", 8)
MONO_L  = ("Consolas", 11, "bold")
MONO_XL = ("Consolas", 13, "bold")

SCOPE_COLORS = {"HIP": FG, "1.0x": BLUE, "2.5x": PURPLE}
ARM_COLOR    = {"armed": GREEN, "idle": FG2}


def launch_gui():
    from pynput import mouse as pm, keyboard as pk

    sys_obj = RecoilSystem()

    root = tk.Tk()
    root.title("R6S · RecoilSystem v11")
    root.configure(bg=BG)
    root.resizable(False, False)
    root.wm_attributes("-topmost",  True)
    root.wm_attributes("-alpha",    0.85)   # 15% transparent

    _q: queue.Queue = queue.Queue()

    def _pump():
        try:
            while True:
                _q.get_nowait()()
        except queue.Empty:
            pass
        root.after(16, _pump)

    root.after(16, _pump)

    def gui(fn):
        _q.put(fn)

    # ── notebook styles ────────────────────────────────────
    style = ttk.Style()
    style.theme_use("default")
    style.configure("TNotebook",
                    background=BG, borderwidth=0, tabmargins=[0, 0, 0, 0])
    style.configure("TNotebook.Tab",
                    background=BG3, foreground=FG2,
                    font=("Consolas", 9, "bold"),
                    padding=[16, 6], borderwidth=0)
    style.map("TNotebook.Tab",
              background=[("selected", BG2)],
              foreground=[("selected", TEAL)])
    style.configure("TFrame", background=BG)

    nb = ttk.Notebook(root)
    nb.pack(fill="both", expand=True)

    tab_main = ttk.Frame(nb, style="TFrame")
    tab_sens = ttk.Frame(nb, style="TFrame")
    tab_keys = ttk.Frame(nb, style="TFrame")
    tab_log  = ttk.Frame(nb, style="TFrame")

    nb.add(tab_main, text="  MAIN  ")
    nb.add(tab_sens, text="  SENS  ")
    nb.add(tab_keys, text=" KEYBINDS ")
    nb.add(tab_log,  text="  LOG  ")

    def sep(parent, color=BORDER2):
        tk.Frame(parent, bg=color, height=1).pack(fill="x", padx=10, pady=4)

    def label(parent, text, font=MONO_S, fg=FG2, **kw):
        return tk.Label(parent, text=text, font=font, fg=fg, bg=BG, **kw)

    # ══════════════════════════════════════════════════════
    # TAB: MAIN
    # ══════════════════════════════════════════════════════

    # header bar
    hbar = tk.Frame(tab_main, bg=BG, pady=0)
    hbar.pack(fill="x", padx=12, pady=(12, 2))
    tk.Label(hbar, text="◈", font=("Consolas", 14, "bold"),
             fg=RED, bg=BG).pack(side="left")
    tk.Label(hbar, text="  RECOIL SYSTEM  v11",
             font=MONO_XL, fg=FG, bg=BG).pack(side="left")

    # thin accent line under header
    tk.Frame(tab_main, bg=RED, height=1).pack(fill="x", padx=12, pady=(2, 6))

    # ── arm status indicator ───────────────────────────────
    arm_frame = tk.Frame(tab_main, bg=BG2, highlightthickness=1,
                         highlightbackground=BORDER2)
    arm_frame.pack(fill="x", padx=12, pady=(0, 8))

    arm_inner = tk.Frame(arm_frame, bg=BG2)
    arm_inner.pack(fill="x", padx=10, pady=8)

    arm_dot = tk.Label(arm_inner, text="●", font=("Consolas", 18, "bold"),
                       fg=FG2, bg=BG2)
    arm_dot.pack(side="left", padx=(0, 8))

    arm_right = tk.Frame(arm_inner, bg=BG2)
    arm_right.pack(side="left", fill="x", expand=True)

    arm_title = tk.Label(arm_right, text="RECOIL SYSTEM",
                         font=("Consolas", 10, "bold"), fg=FG, bg=BG2, anchor="w")
    arm_title.pack(anchor="w")
    arm_sub = tk.Label(arm_right, text="Hold RMB to arm  ·  LMB fires",
                       font=("Consolas", 8), fg=FG2, bg=BG2, anchor="w")
    arm_sub.pack(anchor="w")

    def _set_arm_ui(state: str):
        # state: "idle" | "armed" | "firing"
        colors = {
            "idle":   (FG2,  "IDLE",   "Hold RMB to arm  ·  LMB fires"),
            "armed":  (AMBER,"ARMED",  "RMB held  ·  Press LMB to fire"),
            "firing": (RED,  "FIRING", "Compensating recoil…"),
        }
        c, title, sub = colors.get(state, colors["idle"])
        arm_dot.configure(fg=c)
        arm_title.configure(text=f"RECOIL  ·  {title}", fg=c)
        arm_sub.configure(text=sub)

    sep(tab_main)

    # ── scope mode ────────────────────────────────────────
    scope_var = tk.StringVar(value="◈  MODE: HIP")
    scope_btn = tk.Button(
        tab_main, textvariable=scope_var,
        font=("Consolas", 9, "bold"),
        fg=FG, bg=BG2,
        activebackground=BG3, activeforeground=FG,
        relief="flat", bd=0,
        highlightthickness=1, highlightbackground=BORDER2,
        height=1, cursor="hand2", padx=10, pady=4,
    )
    scope_btn.pack(fill="x", padx=12, pady=(0, 8))

    def _do_scope():
        mode = sys_obj.cycle_scope()
        c = SCOPE_COLORS.get(mode, FG)
        scope_var.set(f"◈  MODE: {mode}")
        scope_btn.configure(fg=c, highlightbackground=c)
        _refresh_disp()

    scope_btn.configure(command=_do_scope)

    sep(tab_main)

    # ── weapon selectors ──────────────────────────────────
    wf = tk.Frame(tab_main, bg=BG)
    wf.pack(fill="x", padx=12, pady=4)

    label(wf, "CATEGORY", anchor="w").pack(anchor="w")
    cat_var  = tk.StringVar(value="ASSAULT RIFLES")
    cat_menu = tk.OptionMenu(wf, cat_var, *WEAPON_REGISTRY.keys())
    cat_menu.configure(
        font=MONO, fg=FG, bg=BG3,
        activebackground=BG4, activeforeground=FG,
        relief="flat", bd=0,
        highlightthickness=1, highlightbackground=BORDER2,
        width=32,
    )
    cat_menu["menu"].configure(
        font=MONO, fg=FG, bg=BG3,
        activebackground=RED, activeforeground=FG,
    )
    cat_menu.pack(fill="x", pady=(2, 8))

    label(wf, "WEAPON", anchor="w").pack(anchor="w")
    wpn_var  = tk.StringVar()
    wpn_menu = tk.OptionMenu(wf, wpn_var, "")
    wpn_menu.configure(
        font=MONO, fg=FG, bg=BG3,
        activebackground=BG4, activeforeground=FG,
        relief="flat", bd=0,
        highlightthickness=1, highlightbackground=BORDER2,
        width=32,
    )
    wpn_menu["menu"].configure(
        font=MONO, fg=FG, bg=BG3,
        activebackground=RED, activeforeground=FG,
    )
    wpn_menu.pack(fill="x")

    def _rebuild_weapons(cat: str):
        m = wpn_menu["menu"]
        m.delete(0, "end")
        for w in WEAPON_REGISTRY[cat]:
            m.add_command(label=w, command=lambda v=w: wpn_var.set(v))
        wpn_var.set(WEAPON_REGISTRY[cat][0])

    def _on_cat(*_): _rebuild_weapons(cat_var.get())

    def _on_wpn(*_):
        w = wpn_var.get()
        if not w:
            return
        p = sys_obj.set_weapon(w)
        rpm_lbl.configure(text=f"{p['rpm']} RPM")
        _refresh_disp()

    cat_var.trace_add("write", _on_cat)
    wpn_var.trace_add("write", _on_wpn)
    _rebuild_weapons("ASSAULT RIFLES")

    sep(tab_main)

    # ── status strip ──────────────────────────────────────
    srow = tk.Frame(tab_main, bg=BG)
    srow.pack(fill="x", padx=12, pady=6)

    def _stat_col(parent, lbl_text, init, color=FG):
        col = tk.Frame(parent, bg=BG)
        tk.Label(col, text=lbl_text, font=("Consolas", 7),
                 fg=FG2, bg=BG).pack()
        lbl = tk.Label(col, text=init,
                       font=("Consolas", 10, "bold"), fg=color, bg=BG)
        lbl.pack()
        col.pack(side="left", expand=True)
        return lbl

    rpm_lbl  = _stat_col(srow, "RPM",         "880 RPM", FG3)
    cy_lbl   = _stat_col(srow, "COMP Y",      "—",       BLUE)
    cx_lbl   = _stat_col(srow, "COMP X",      "—",       AMBER)
    sess_lbl = _stat_col(srow, "ADAPTATIONS", "0",       GREEN)

    def _refresh_disp():
        cy_s, cx_s = sys_obj.ar.comp_display()
        cy_lbl.configure(text=cy_s)
        cx_lbl.configure(text=cx_s)

    def _tick():
        sess_lbl.configure(text=str(sys_obj.sessions))
        _refresh_disp()
        root.after(400, _tick)

    root.after(400, _tick)

    # ══════════════════════════════════════════════════════
    # TAB: SENS
    # ══════════════════════════════════════════════════════

    label(tab_sens, "SENSITIVITY SETTINGS",
          font=MONO_L, fg=TEAL).pack(anchor="w", padx=14, pady=(12, 6))

    sens_fields: dict[str, tk.StringVar] = {}

    def _sens_row(parent, text: str, key: str, default: str, color=AMBER):
        row = tk.Frame(parent, bg=BG)
        row.pack(fill="x", padx=14, pady=3)
        tk.Label(row, text=text, font=MONO_S, fg=FG2, bg=BG,
                 width=22, anchor="w").pack(side="left")
        var = tk.StringVar(value=default)
        sens_fields[key] = var
        ent = tk.Entry(
            row, textvariable=var,
            font=("Consolas", 10, "bold"), fg=color, bg=BG3,
            insertbackground=color, relief="flat",
            highlightthickness=1, highlightbackground=BORDER2,
            width=8, justify="center",
        )
        ent.pack(side="left")
        return var

    _sens_row(tab_sens, "Horizontal Sens",   "h",   "9")
    _sens_row(tab_sens, "Vertical Sens",     "v",   "9")

    sep(tab_sens)
    label(tab_sens, "ADS SCOPE SENS  (% of hip — match in-game slider)",
          fg=FG2).pack(anchor="w", padx=14, pady=(4, 2))

    _sens_row(tab_sens, "1.0x Sights  (%)", "s1",  "70", BLUE)
    _sens_row(tab_sens, "2.5x Scopes  (%)", "s25", "55", PURPLE)

    sep(tab_sens)

    sens_status = label(tab_sens, "", fg=GREEN)
    sens_status.pack(anchor="w", padx=14, pady=2)

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
            sens_status.configure(text="✕  Invalid — check ranges", fg=RED)
            return
        sys_obj.sens.h         = h
        sys_obj.sens.v         = v
        sys_obj.sens.scope_1x  = s1  / 100.0
        sys_obj.sens.scope_25x = s25 / 100.0
        sens_status.configure(
            text=f"✓  Applied  H={h}  V={v}  1x={s1}%  2.5x={s25}%", fg=GREEN)
        sys_obj._log(f"[SENS] H={h} V={v} 1x={s1/100:.2f} 2.5x={s25/100:.2f}")
        _refresh_disp()

    tk.Button(
        tab_sens, text="APPLY SENSITIVITY",
        font=("Consolas", 10, "bold"),
        fg=BG, bg=TEAL, activebackground="#30e8e0", activeforeground=BG,
        relief="flat", bd=0, padx=16, pady=6, cursor="hand2",
        command=_apply_sens,
    ).pack(padx=14, pady=6, anchor="w")

    label(tab_sens,
          "Match H/V to your R6 mouse sensitivity value.\n"
          "Scope % = the ADS slider in R6 settings (48 = 48%).",
          fg=FG2, justify="left",
          ).pack(anchor="w", padx=14, pady=(0, 10))

    # ══════════════════════════════════════════════════════
    # TAB: KEYBINDS (scope, show, exit only)
    # ══════════════════════════════════════════════════════

    label(tab_keys, "KEYBIND SETTINGS",
          font=MONO_L, fg=TEAL).pack(anchor="w", padx=14, pady=(12, 4))
    label(tab_keys,
          "Click a field, press any key to rebind.\n"
          "Letters, or: shift_r  f1–f12  ctrl_l  alt_l  …",
          fg=FG2, justify="left",
          ).pack(anchor="w", padx=14, pady=(0, 6))

    sep(tab_keys)

    key_vars: dict[str, tk.StringVar] = {}
    key_status = label(tab_keys, "", fg=GREEN)

    KEY_DEFS = [
        ("scope", "Cycle Scope Mode",  "s"),
        ("show",  "Show / Hide GUI",   "shift_r"),
        ("exit",  "Exit Script",       "f10"),
    ]

    for attr, lbl_text, default in KEY_DEFS:
        row = tk.Frame(tab_keys, bg=BG)
        row.pack(fill="x", padx=14, pady=3)
        tk.Label(row, text=lbl_text, font=MONO_S, fg=FG2, bg=BG,
                 width=22, anchor="w").pack(side="left")
        var = tk.StringVar(value=getattr(sys_obj.keys, attr))
        key_vars[attr] = var
        ent = tk.Entry(
            row, textvariable=var,
            font=("Consolas", 10, "bold"), fg=AMBER, bg=BG3,
            insertbackground=AMBER, relief="flat",
            highlightthickness=1, highlightbackground=BORDER2,
            width=12, justify="center",
        )
        ent.pack(side="left")

        def _on_key_press(event, a=attr, v=var):
            v.set(event.keysym.lower())
            return "break"

        ent.bind("<KeyPress>", _on_key_press)

    def _apply_keys():
        for attr in key_vars:
            setattr(sys_obj.keys, attr, key_vars[attr].get().strip())
        key_status.configure(text="✓  Keybinds applied", fg=GREEN)
        sys_obj._log(
            f"[KEYS] scope={sys_obj.keys.scope}  "
            f"show={sys_obj.keys.show}  exit={sys_obj.keys.exit}"
        )

    tk.Button(
        tab_keys, text="APPLY KEYBINDS",
        font=("Consolas", 10, "bold"),
        fg=BG, bg=TEAL, activebackground="#30e8e0", activeforeground=BG,
        relief="flat", bd=0, padx=16, pady=6, cursor="hand2",
        command=_apply_keys,
    ).pack(padx=14, pady=8, anchor="w")

    key_status.pack(anchor="w", padx=14)

    # ══════════════════════════════════════════════════════
    # TAB: LOG
    # ══════════════════════════════════════════════════════

    label(tab_log, "SYSTEM LOG",
          font=MONO_L, fg=TEAL).pack(anchor="w", padx=14, pady=(12, 4))

    log_box = tk.Text(
        tab_log,
        font=("Consolas", 8), fg="#5a6080", bg="#040409",
        relief="flat", bd=0,
        highlightthickness=1, highlightbackground=BORDER,
        state="disabled",
        insertbackground=FG2,
    )
    log_box.pack(fill="both", expand=True, padx=14, pady=(0, 12))

    def _append(msg: str):
        log_box.configure(state="normal")
        log_box.insert("end", msg + "\n")
        log_box.see("end")
        log_box.configure(state="disabled")

    sys_obj._log_cb = lambda m: gui(lambda m=m: _append(m))

    # ── visibility toggle ─────────────────────────────────
    _visible = [True]

    def _toggle_vis():
        if _visible[0]:
            root.withdraw()
            _visible[0] = False
        else:
            root.deiconify()
            root.lift()
            root.focus_force()
            root.wm_attributes("-topmost", True)
            _visible[0] = True

    # ── pynput listeners ──────────────────────────────────

    def _key_name(key) -> str | None:
        try:
            if hasattr(key, "char") and key.char:
                return key.char.lower()
        except Exception:
            pass
        try:
            return key.name.lower()
        except Exception:
            pass
        return None

    def on_click(x, y, btn, pressed):
        try:
            from pynput.mouse import Button
            if btn == Button.right:
                if pressed:
                    gui(sys_obj.on_rmb_down)
                    gui(lambda: _set_arm_ui("armed"))
                else:
                    gui(sys_obj.on_rmb_up)
                    gui(lambda: _set_arm_ui("idle"))
            elif btn == Button.left:
                if pressed:
                    gui(sys_obj.on_lmb_down)
                    if sys_obj._rmb_held:
                        gui(lambda: _set_arm_ui("firing"))
                else:
                    gui(sys_obj.on_lmb_up)
                    if sys_obj._rmb_held:
                        gui(lambda: _set_arm_ui("armed"))
        except Exception:
            pass

    def on_key(key):
        try:
            name = _key_name(key)
            if name is None:
                return
            k = sys_obj.keys
            if   name == k.scope: gui(_do_scope)
            elif name == k.show:  gui(_toggle_vis)
            elif name == k.exit:
                gui(root.destroy)
                return False
        except Exception:
            pass

    ml = pm.Listener(on_click=on_click)
    kl = pk.Listener(on_press=on_key)
    ml.daemon = kl.daemon = True
    ml.start()
    kl.start()

    # ── startup log ───────────────────────────────────────
    _append("[SYSTEM]  v11 ready.")
    _append("[INPUT]   Hold RMB to arm — press LMB to fire.")
    _append("[PULL]    comp_y boosted ~40% across all weapons.")
    _append("[KEYS]    S=scope  RShift=show/hide  F10=exit")
    _append("[SENS]    Set in SENS tab and hit Apply.")

    sys_obj.set_weapon("R4-C")

    root.geometry("460x520")
    root.mainloop()


if __name__ == "__main__":
    launch_gui()
