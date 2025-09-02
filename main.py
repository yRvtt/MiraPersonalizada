# -*- coding: utf-8 -*-
import sys, os, json, platform, ctypes, subprocess
from ctypes import wintypes
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QColorDialog, QComboBox, QSlider, QGroupBox, QMessageBox, QFrame,
    QSizePolicy, QCheckBox
)
from PyQt5.QtGui import QPainter, QPen, QColor
from PyQt5.QtCore import Qt, QRect, QTimer

CONFIG_FILE = "crosshair_config.json"

# ---------------------------
# Admin (UAC) sempre
# ---------------------------
def ensure_admin():
    if platform.system() != "Windows":
        return True
    try:
        is_admin = ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        is_admin = False
    if not is_admin:
        script = os.path.abspath(sys.argv[0])
        params = '"' + script + '"'
        if len(sys.argv) > 1:
            params += " " + " ".join('"%s"' % a for a in sys.argv[1:])
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
        sys.exit(0)
    return True

def disable_windows_night_light():
    try:
        subprocess.run([
            'reg', 'add',
            r'HKCU\Software\Microsoft\Windows\CurrentVersion\CloudStore\Store\DefaultAccount\Current\default$windows.data.bluelightreduction.bluelightreductionstate',
            '/v', 'Data', '/t', 'REG_BINARY', '/d', '0200000000000000', '/f'
        ], capture_output=True)
        return True
    except Exception:
        return False

def is_rdp_session():
    return os.environ.get('SESSIONNAME', '').upper().startswith('RDP-')

# =========================
# Win32 / User32
# =========================
gdi32  = ctypes.windll.gdi32
user32 = ctypes.windll.user32

SetWindowPos = user32.SetWindowPos
SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
SetWindowPos.restype  = wintypes.BOOL
HWND_TOPMOST = ctypes.c_void_p(-1).value
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040

GWL_EXSTYLE=-20
WS_EX_LAYERED=0x00080000
WS_EX_TRANSPARENT=0x00000020
WS_EX_NOACTIVATE=0x08000000
WS_EX_TOOLWINDOW=0x00000080  # não aparece na barra de tarefas

# =========================
# LUT (Gamma Ramp)
# =========================
class GAMMARAMP(ctypes.Structure):
    _fields_ = [("Red", wintypes.WORD*256), ("Green", wintypes.WORD*256), ("Blue", wintypes.WORD*256)]

class DISPLAY_DEVICEW(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD), ("DeviceName", wintypes.WCHAR*32), ("DeviceString", wintypes.WCHAR*128),
        ("StateFlags", wintypes.DWORD), ("DeviceID", wintypes.WCHAR*128), ("DeviceKey", wintypes.WCHAR*128),
    ]

DISPLAY_DEVICE_ACTIVE = 0x00000001
DISPLAY_DEVICE_PRIMARY_DEVICE = 0x00000004

EnumDisplayDevicesW = user32.EnumDisplayDevicesW
EnumDisplayDevicesW.restype = wintypes.BOOL
EnumDisplayDevicesW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, ctypes.POINTER(DISPLAY_DEVICEW), wintypes.DWORD]

CreateDCW = gdi32.CreateDCW
CreateDCW.restype = wintypes.HDC
CreateDCW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPVOID]

DeleteDC = gdi32.DeleteDC
DeleteDC.restype = wintypes.BOOL
DeleteDC.argtypes = [wintypes.HDC]

SetDeviceGammaRamp = gdi32.SetDeviceGammaRamp
SetDeviceGammaRamp.restype = wintypes.BOOL
SetDeviceGammaRamp.argtypes = [wintypes.HDC, ctypes.POINTER(GAMMARAMP)]

def _get_primary_display_name():
    i = 0
    while True:
        dd = DISPLAY_DEVICEW(); dd.cb = ctypes.sizeof(DISPLAY_DEVICEW)
        if not EnumDisplayDevicesW(None, i, ctypes.byref(dd), 0): break
        if (dd.StateFlags & DISPLAY_DEVICE_ACTIVE) and (dd.StateFlags & DISPLAY_DEVICE_PRIMARY_DEVICE):
            return dd.DeviceName
        i += 1
    return r"\\.\DISPLAY1"

def _apply_lut_to_primary(ramp):
    hscr = user32.GetDC(0)
    try:
        if bool(SetDeviceGammaRamp(hscr, ctypes.byref(ramp))):
            return True
    finally:
        user32.ReleaseDC(0, hscr)
    # fallback DC nomeado
    dev = _get_primary_display_name()
    hdc = CreateDCW("DISPLAY", dev, None, None)
    if not hdc: return False
    try:
        return bool(SetDeviceGammaRamp(hdc, ctypes.byref(ramp)))
    finally:
        DeleteDC(hdc)

# =========================
# LUT “filtro” (Noite→Dia)
# =========================
def _build_lut(bright_pct=84, contr_pct=70, gamma_pct=90, sat_fake_pct=58,
               daymax=True, clarity=1.2, filter_type="Clarity"):
    import math
    B = (bright_pct-50)/100.0
    C = 0.55 + (contr_pct/100.0)*0.9
    g_eff = 1.35 - (gamma_pct/100.0)*0.8
    g_eff = max(0.30, min(3.0, g_eff))
    S = (sat_fake_pct-50)/50.0
    S = max(-1.0, min(1.0, S))
    sat_base = 0.20 * S

    toe_lift         = 0.18*clarity
    mid_boost        = 0.22*clarity
    k_hl             = 0.45*clarity
    sat_shadow_boost = 0.16*clarity

    if filter_type == "NVG Verde":
        red_warm, green_push, blue_cut = -0.02*clarity, 0.22*clarity, 0.35*clarity
        sat_extra = -0.05*clarity
    elif filter_type == "Cinza":
        red_warm, green_push, blue_cut = 0.0, 0.0, 0.0
        sat_extra = -0.25*clarity
    elif filter_type == "Frio (Lua)":
        red_warm, green_push, blue_cut = -0.06*clarity, 0.06*clarity, 0.12*clarity
        sat_extra = -0.05*clarity
    else:
        red_warm, green_push, blue_cut = 0.03*clarity, 0.07*clarity, 0.12*clarity
        sat_extra = 0.0

    r=(wintypes.WORD*256)(); g=(wintypes.WORD*256)(); b=(wintypes.WORD*256)()
    for i in range(256):
        x = i/255.0
        x1 = ((x-0.5)*C + 0.5) + B
        x1 = 0.0 if x1<0.0 else (1.0 if x1>1.0 else x1)
        y  = pow(x1, 1.0/g_eff)
        if daymax:
            y += toe_lift * (1.0 - math.exp(-y/(0.12+0.08*clarity))); y = max(0.0, min(1.0, y))
            m = (y-0.5); y += mid_boost*m*(1.0-abs(m))*2.0; y = max(0.0, min(1.0, y))
            y = (y*(1.0+k_hl))/(y+k_hl); y = max(0.0, min(1.0, y))
        sat_var = sat_base + (sat_shadow_boost*pow(1.0-y,0.8) if daymax else 0.0) + sat_extra
        xr = y + sat_var*(y-0.5); xg = y + sat_var*(0.5-y); xb = y + sat_var*(xr-xg)*0.5
        if daymax:
            xr *= (1.0 + red_warm); xg *= (1.0 + green_push); xb *= (1.0 - blue_cut)
        xr = max(0.0, min(1.0, xr)); xg = max(0.0, min(1.0, xg)); xb = max(0.0, min(1.0, xb))
        r[i]=int(xr*65535+0.5); g[i]=int(xg*65535+0.5); b[i]=int(xb*65535+0.5)
    ramp=GAMMARAMP(); ramp.Red[:]=r[:]; ramp.Green[:]=g[:]; ramp.Blue[:]=b[:]
    return ramp

# =========================
# Nativo pass-through (não ativa, não captura)
# =========================
WM_NCHITTEST      = 0x0084
HTTRANSPARENT     = -1
WM_MOUSEACTIVATE  = 0x0021
MA_NOACTIVATE     = 3

class POINT(ctypes.Structure):
    _fields_=[("x", ctypes.c_long), ("y", ctypes.c_long)]
class MSG(ctypes.Structure):
    _fields_=[
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", POINT)
    ]

class WinNativePassThrough:
    # só responde o essencial para nunca ativar/roubar foco
    def nativeEvent(self, eventType, message):
        if platform.system()=="Windows" and eventType=="windows_generic_MSG":
            msg = MSG.from_address(message.__int__())
            if msg.message == WM_NCHITTEST:
                return True, ctypes.c_long(HTTRANSPARENT).value
            if msg.message == WM_MOUSEACTIVATE:
                return True, MA_NOACTIVATE
        return False, 0

def _make_click_through(hwnd: int):
    Get=ctypes.windll.user32.GetWindowLongW
    Set=ctypes.windll.user32.SetWindowLongW
    ex=Get(hwnd, GWL_EXSTYLE)
    ex|=(WS_EX_LAYERED|WS_EX_TRANSPARENT|WS_EX_NOACTIVATE|WS_EX_TOOLWINDOW)
    Set(hwnd, GWL_EXSTYLE, ex)
    # topmost sem ativar
    SetWindowPos(hwnd, HWND_TOPMOST, 0,0,0,0, SWP_NOACTIVATE|SWP_NOMOVE|SWP_NOSIZE|SWP_SHOWWINDOW)

# =========================
# Fullscreen / Rust attach
# =========================
MONITOR_DEFAULTTOPRIMARY = 1
GetForegroundWindow = user32.GetForegroundWindow
GetWindowRect = user32.GetWindowRect
MonitorFromWindow = user32.MonitorFromWindow
GetMonitorInfoW = user32.GetMonitorInfoW
EnumWindows = user32.EnumWindows
IsWindowVisible = user32.IsWindowVisible
GetWindowTextW = user32.GetWindowTextW
GetWindowTextLengthW = user32.GetWindowTextLengthW
IsWindow = user32.IsWindow

class MONITORINFO(ctypes.Structure):
    _fields_=[("cbSize", wintypes.DWORD),
              ("rcMonitor", wintypes.RECT),
              ("rcWork", wintypes.RECT),
              ("dwFlags", wintypes.DWORD)]

WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

def _is_foreground_fullscreen_primary():
    try:
        fg = GetForegroundWindow()
        if not fg: return False
        rect = wintypes.RECT()
        if not GetWindowRect(fg, ctypes.byref(rect)): return False
        mon = MonitorFromWindow(fg, MONITOR_DEFAULTTOPRIMARY)
        mi = MONITORINFO(); mi.cbSize = ctypes.sizeof(MONITORINFO)
        if not GetMonitorInfoW(mon, ctypes.byref(mi)): return False
        return (rect.left == mi.rcMonitor.left and rect.top == mi.rcMonitor.top and
                rect.right == mi.rcMonitor.right and rect.bottom == mi.rcMonitor.bottom)
    except Exception:
        return False

def _find_rust_hwnd():
    found = ctypes.c_void_p(0)
    def _cb(hwnd, lparam):
        try:
            if not IsWindowVisible(hwnd): return True
            length = GetWindowTextLengthW(hwnd)
            if length == 0: return True
            buf = ctypes.create_unicode_buffer(length + 1)
            GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value
            if "rust" in title.lower():
                found.value = hwnd
                return False
        except Exception:
            pass
        return True
    EnumWindows(WNDENUMPROC(_cb), 0)
    return ctypes.c_void_p(found.value).value

# =========================
# Estado
# =========================
class AppState:
    def __init__(self):
        self.current_profile="default"
        self.use_overlay=False
        self.bright_pct=self.contr_pct=self.gamma_pct=self.sat_pct=50
        self.daymax=False
        self.clarity=1.2
        self.filter_type="Clarity"
        self.overlay_alpha=70
        self.overlay_suspended=False
        self.force_overlay_fullscreen=True
        self.attach_to_rust=True
        self.rust_hwnd=None
        self.auto_hide_panel=True  # painel não rouba foco

# =========================
# Overlay (1 passe), click-through
# =========================
class FilterOverlay(WinNativePassThrough, QWidget):
    def __init__(self, state: AppState):
        super().__init__()
        self.state=state
        self.mode='off'; self.alpha_override=None; self.filter_type="Clarity"
        self.setWindowFlags(Qt.FramelessWindowHint|Qt.WindowStaysOnTopHint|Qt.Tool|Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setContextMenuPolicy(Qt.NoContextMenu)
        if hasattr(Qt,"WindowTransparentForInput"):
            self.setWindowFlag(Qt.WindowTransparentForInput, True)
        self.setFocusPolicy(Qt.NoFocus)
        _make_click_through(int(self.winId()))
        self.guard = QTimer(self); self.guard.setInterval(500); self.guard.timeout.connect(self._guard_tick); self.guard.start()
        self.track = QTimer(self); self.track.setInterval(250); self.track.timeout.connect(self._track_target); self.track.start()
        self._attach_primary_geometry()

    def _attach_primary_geometry(self):
        g=QApplication.primaryScreen().geometry()
        self.setGeometry(QRect(g.left(),g.top(),g.width(),g.height()))
        if self.mode!='off' and not self.state.overlay_suspended: self._show_noactivate()
        else: self.hide()

    def _attach_rust_geometry(self):
        hwnd = self.state.rust_hwnd
        if not hwnd:
            self._attach_primary_geometry(); return
        rect = wintypes.RECT()
        if not GetWindowRect(hwnd, ctypes.byref(rect)):
            self._attach_primary_geometry(); return
        # Fallback: se janela for pequena (launcher/splash), usa tela toda
        pg = QApplication.primaryScreen().geometry()
        sw, sh = pg.width(), pg.height()
        w = rect.right-rect.left; h = rect.bottom-rect.top
        if w < int(sw*0.7) or h < int(sh*0.7):
            self._attach_primary_geometry(); return
        self.setGeometry(QRect(rect.left, rect.top, w, h))
        if self.mode!='off' and not self.state.overlay_suspended: self._show_noactivate()

    def _show_noactivate(self):
        self.show()
        SetWindowPos(int(self.winId()), HWND_TOPMOST, 0,0,0,0,
                     SWP_NOACTIVATE|SWP_NOMOVE|SWP_NOSIZE|SWP_SHOWWINDOW)

    def _track_target(self):
        if self.state.attach_to_rust:
            if not self.state.rust_hwnd or not IsWindow(self.state.rust_hwnd):
                self.state.rust_hwnd = _find_rust_hwnd()
            self._attach_rust_geometry()
        else:
            self._attach_primary_geometry()

    def set_mode(self, mode, alpha=None, filter_type=None):
        mode=mode.lower()
        if mode not in ('day','bright','off'): mode='off'
        self.mode=mode
        if filter_type: self.filter_type=filter_type
        self.alpha_override=alpha
        if self.mode=='off': self.hide()
        else:
            if self.state.attach_to_rust and self.state.rust_hwnd: self._attach_rust_geometry()
            else: self._attach_primary_geometry()
            self._show_noactivate()
        self.update()

    def _guard_tick(self):
        if self.state.force_overlay_fullscreen:
            if self.mode!='off': self._show_noactivate()
            return
        if _is_foreground_fullscreen_primary() and self.mode!='off' and not self.state.overlay_suspended:
            self.state.overlay_suspended=True; self.hide()
        elif (not _is_foreground_fullscreen_primary()) and self.state.overlay_suspended:
            self.state.overlay_suspended=False; self._show_noactivate()

    def set_strength(self, alpha):
        self.alpha_override=max(0,min(255,int(alpha)))
        if self.mode!='off' and not self.state.overlay_suspended: self.update()

    def get_strength(self, default=70):
        return int(self.alpha_override) if self.alpha_override is not None else default

    def _color_for_filter(self):
        if self.filter_type == "NVG Verde":   return 210,255,210
        if self.filter_type == "Cinza":       return 240,240,240
        if self.filter_type == "Frio (Lua)":  return 220,235,255
        return 255,244,220  # Clarity

    def paintEvent(self, ev):
        if self.mode=='off' or self.state.overlay_suspended: return
        p=QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, False)
        p.setCompositionMode(QPainter.CompositionMode_Screen)
        r,g,b = self._color_for_filter()
        a = self.get_strength()
        p.fillRect(self.rect(), QColor(r,g,b, a))
        p.end()

# =========================
# Controle (LUT + overlay)
# =========================
class MonitorControl:
    @staticmethod
    def _apply_lut_from_state(overlay: FilterOverlay, st: AppState):
        if is_rdp_session():
            st.use_overlay = (st.current_profile != "default")
            overlay.set_mode('day' if st.current_profile=='day' else ('bright' if st.current_profile=='bright' else 'off'),
                             alpha=st.overlay_alpha, filter_type=st.filter_type)
            return False
        disable_windows_night_light()
        ramp=_build_lut(st.bright_pct, st.contr_pct, st.gamma_pct, st.sat_pct,
                        st.daymax, clarity=st.clarity, filter_type=st.filter_type)
        ok=_apply_lut_to_primary(ramp)
        st.use_overlay=not ok
        if ok: overlay.set_mode('off')
        else:
            if st.current_profile=='default': overlay.set_mode('off')
            else: overlay.set_mode('day', alpha=st.overlay_alpha, filter_type=st.filter_type)
        return ok

    @staticmethod
    def apply_profile(profile: str, overlay: FilterOverlay, st: AppState):
        st.current_profile=profile
        if profile=="day":
            st.bright_pct, st.contr_pct, st.gamma_pct, st.sat_pct = 84, 70, 90, 58
            st.daymax=True
        elif profile=="bright":
            st.bright_pct, st.contr_pct, st.gamma_pct, st.sat_pct = 100, 50, 50, 50
            st.daymax=False
        else:
            st.bright_pct = st.contr_pct = st.gamma_pct = st.sat_pct = 50
            st.daymax=False
        return MonitorControl._apply_lut_from_state(overlay, st)

    @staticmethod
    def bump_brightness(delta_steps: int, overlay: FilterOverlay, st: AppState):
        if st.current_profile=="default" and not st.use_overlay:
            st.current_profile="bright"
        if not st.use_overlay:
            st.bright_pct=max(0,min(100, st.bright_pct + 5*delta_steps))
            return MonitorControl._apply_lut_from_state(overlay, st)
        else:
            st.overlay_alpha=max(0,min(255, st.overlay_alpha + 10*delta_steps))
            overlay.set_mode('day', alpha=st.overlay_alpha, filter_type=st.filter_type)
            return True

# =========================
# Mira (click-through)
# =========================
class Crosshair(WinNativePassThrough, QWidget):
    def __init__(self, config):
        super().__init__()
        self.config=config
        self.setWindowFlags(Qt.FramelessWindowHint|Qt.WindowStaysOnTopHint|Qt.Tool|Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setContextMenuPolicy(Qt.NoContextMenu)
        self.resize(200,200); self.show()
        self.update_position()
        try: QApplication.primaryScreen().geometryChanged.connect(lambda *_: self.update_position())
        except Exception: pass
        _make_click_through(int(self.winId()))

    def update_position(self):
        g=QApplication.primaryScreen().geometry()
        self.move(g.center().x()-self.width()//2, g.center().y()-self.height()//2)

    def set_config(self, c): self.config=c; self.update()

    def paintEvent(self, e):
        p=QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        c=self.rect().center()
        size=self.config.get("size",10); gap=self.config.get("gap",4)
        thick=self.config.get("thickness",2); op=self.config.get("opacity",100)
        style=self.config.get("style","Clássico"); color=QColor(self.config.get("color","#00FF00"))
        color.setAlphaF(op/100.0)
        pen=QPen(color,thick); shadow=QPen(QColor(0,0,0,160), thick+1)
        def ln(x1,y1,x2,y2): p.setPen(shadow); p.drawLine(x1,y1,x2,y2); p.setPen(pen); p.drawLine(x1,y1,x2,y2)
        if style=="Clássico":
            ln(c.x(),c.y()-gap-size, c.x(),c.y()-gap); ln(c.x(),c.y()+gap, c.x(),c.y()+gap+size)
            ln(c.x()-gap-size,c.y(), c.x()-gap,c.y()); ln(c.x()+gap,c.y(), c.x()+gap+size,c.y())
        elif style=="Círculo":
            p.setPen(shadow); p.drawEllipse(c,size+1,size+1); p.setPen(pen); p.drawEllipse(c,size,size)
        elif style=="Ponto":
            p.setPen(Qt.NoPen); p.setBrush(color); p.drawEllipse(c,size,size)
        else:
            ln(c.x(),c.y()-gap-size, c.x(),c.y()-gap); ln(c.x(),c.y()+gap, c.x(),c.y()+gap+size)
            ln(c.x()-gap-size,c.y(), c.x()-gap,c.y()); ln(c.x()+gap,c.y(), c.x()+gap+size,c.y())
        p.end()

# =========================
# UI
# =========================
class SettingsWindow(QWidget):
    def __init__(self, crosshair_widget, overlay: FilterOverlay, state: AppState):
        super().__init__()
        self.crosshair=crosshair_widget; self.overlay=overlay; self.state=state
        self.setWindowTitle("Mira + Noite → Dia (Filtro)") 
        self.resize(800,660); self.set_dark_theme(); self.init_ui()
        self._focus_guard = QTimer(self); self._focus_guard.setInterval(300)
        self._focus_guard.timeout.connect(self._focus_guard_tick); self._focus_guard.start()

    def _hero(self,t,sub):
        b=QFrame(); b.setObjectName("Hero"); v=QVBoxLayout(b)
        T=QLabel(t); T.setAlignment(Qt.AlignCenter); T.setObjectName("HeroTitle")
        S=QLabel(sub); S.setAlignment(Qt.AlignCenter); S.setObjectName("HeroSub")
        v.addWidget(T); v.addWidget(S); return b

    def init_ui(self):
        root=QVBoxLayout(self)
        root.addWidget(self._hero("Noite → Dia (Filtro leve p/ Rust)",
                                  "LUT (zero custo) quando possível; overlay 1-passe quando necessário. Click-through total."))

        # Filtro
        card=QGroupBox("Filtro"); card.setObjectName("Card"); v=QVBoxLayout(card)
        rowf=QHBoxLayout()
        rowf.addWidget(QLabel("Tipo:"))
        self.filter_box=QComboBox(); self.filter_box.addItems(["Clarity","NVG Verde","Cinza","Frio (Lua)"])
        self.filter_box.currentTextChanged.connect(self._on_filter_changed); rowf.addWidget(self.filter_box)
        rowf.addWidget(QLabel("Força:"))
        self.clarity_slider=QSlider(Qt.Horizontal); self.clarity_slider.setMinimum(50); self.clarity_slider.setMaximum(150)
        self.clarity_slider.setValue(120); self.clarity_slider.valueChanged.connect(self._on_filter_changed)
        rowf.addWidget(self.clarity_slider); v.addLayout(rowf)

        # Perfis & brilho
        card2=QGroupBox("Perfis, Brilho e Tela Cheia"); card2.setObjectName("Card"); v2=QVBoxLayout(card2)
        r1=QHBoxLayout()
        b_day=QPushButton("🌞  Noite → Dia"); b_day.setObjectName("Primary")
        b_bri=QPushButton("💡  Brilho Máximo"); b_bri.setObjectName("Success")
        b_def=QPushButton("♻️  Padrão"); b_def.setObjectName("Muted")
        for b in (b_day,b_bri,b_def):
            b.setMinimumHeight(46); b.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Fixed); r1.addWidget(b)
        v2.addLayout(r1)

        r2=QHBoxLayout()
        b_up=QPushButton("🔺 Brilho +"); b_dn=QPushButton("🔻 Brilho −")
        b_fix=QPushButton("🔧 Night Light OFF")
        for b in (b_up,b_dn,b_fix):
            b.setMinimumHeight(42); b.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Fixed); r2.addWidget(b)
        v2.addLayout(r2)

        r3=QHBoxLayout()
        r3.addWidget(QLabel("Intensidade (overlay fallback):"))
        self.ov_slider=QSlider(Qt.Horizontal); self.ov_slider.setMinimum(0); self.ov_slider.setMaximum(255)
        self.ov_slider.setValue(70); self.ov_slider.valueChanged.connect(self._overlay_strength_changed)
        r3.addWidget(self.ov_slider); v2.addLayout(r3)

        self.cb_force = QCheckBox("Manter filtro em tela cheia (forçar) — pode não aparecer no exclusivo real")
        self.cb_force.setChecked(True); self.cb_force.stateChanged.connect(self._toggle_force_fs); v2.addWidget(self.cb_force)

        self.cb_attach = QCheckBox("Anexar filtro à janela do Rust")
        self.cb_attach.setChecked(True); self.cb_attach.stateChanged.connect(self._toggle_attach_rust); v2.addWidget(self.cb_attach)

        self.cb_autohide = QCheckBox("Ocultar este painel quando o Rust estiver em foco (recomendado)")
        self.cb_autohide.setChecked(True)
        self.cb_autohide.stateChanged.connect(lambda s: setattr(self.state, "auto_hide_panel", s==Qt.Checked))
        v2.addWidget(self.cb_autohide)

        self.status=QLabel("Pronto."); self.status.setObjectName("Status"); v2.addWidget(self.status)

        b_day.clicked.connect(lambda: self._apply("day"))
        b_bri.clicked.connect(lambda: self._apply("bright"))
        b_def.clicked.connect(lambda: self._apply("default"))
        b_up.clicked.connect(lambda: self._bump(+1))
        b_dn.clicked.connect(lambda: self._bump(-1))
        b_fix.clicked.connect(self._fix)

        root.addWidget(card); root.addWidget(card2)

        # Mira
        mira=QGroupBox("Mira"); mira.setObjectName("Card"); ml=QVBoxLayout(mira)
        self.size_s=self._add_slider(ml,"Tamanho",1,100,"size")
        self.gap_s=self._add_slider(ml,"Espaçamento (Gap)",0,50,"gap")
        self.thick_s=self._add_slider(ml,"Espessura",1,10,"thickness")
        self.opac_s=self._add_slider(ml,"Opacidade",10,100,"opacity")
        bcol=QPushButton("Cor da Mira…"); bcol.clicked.connect(self.choose_color); ml.addWidget(bcol)
        rowfmt=QHBoxLayout(); rowfmt.addWidget(QLabel("Formato:"))
        self.style_box=QComboBox(); self.style_box.addItems(["Clássico","Círculo","Ponto","Retícula"])
        self.style_box.setCurrentText(self.crosshair.config.get("style","Clássico"))
        self.style_box.currentTextChanged.connect(self.apply_crosshair)
        rowfmt.addWidget(self.style_box); ml.addLayout(rowfmt)
        root.addWidget(mira); root.addStretch(1)

        if is_rdp_session():
            QMessageBox.information(self,"Aviso","Sessão RDP: LUT não funciona. Usaremos overlay (1 passe).")

        self._on_filter_changed()

    # ---- auto-hide painel para não soltar o mouse do jogo
    def _focus_guard_tick(self):
        if not self.state.auto_hide_panel: return
        rust = self.overlay.state.rust_hwnd or _find_rust_hwnd()
        fg = GetForegroundWindow()
        if rust and fg == rust:
            if self.isVisible(): self.hide()
        else:
            if not self.isVisible(): self.show()

    # toggles
    def _toggle_force_fs(self, s):
        self.state.force_overlay_fullscreen = (s == Qt.Checked)
        if self.overlay.mode!='off': self.overlay._show_noactivate()

    def _toggle_attach_rust(self, s):
        self.state.attach_to_rust = (s == Qt.Checked)
        if not self.state.attach_to_rust:
            self.state.rust_hwnd = None
        if self.overlay.mode!='off': self.overlay._show_noactivate()

    # filtro
    def _on_filter_changed(self):
        self.state.filter_type = self.filter_box.currentText()
        self.state.clarity = self.clarity_slider.value()/100.0
        if self.overlay.mode!='off':
            self.overlay.set_mode('day', alpha=self.state.overlay_alpha, filter_type=self.state.filter_type)

    def _overlay_strength_changed(self, v):
        self.state.overlay_alpha = v
        if self.overlay.mode!='off':
            self.overlay.set_strength(v)
            self.status.setText(f"Overlay ativo ({v}/255). Se clarear demais, reduza.")

    # perfis
    def _fix(self):
        ok=disable_windows_night_light()
        QMessageBox.information(self,"Night Light","Night Light desativado." if ok else "Não foi possível alterar.")
        self.status.setText("⚙️ Ajuste aplicado. Tente o perfil novamente.")

    def _apply(self, name):
        ok=MonitorControl.apply_profile(name, self.overlay, self.state)
        tag={"day":"Noite → Dia","bright":"Brilho Máximo","default":"Padrão"}[name]
        extra=""
        if not ok: extra=" — overlay ativo (fallback)"
        self.status.setText("✅ "+tag+extra)
        if self.overlay.mode!='off':
            self.ov_slider.setValue(self.overlay.get_strength())

    def _bump(self, d):
        MonitorControl.bump_brightness(d, self.overlay, self.state)
        if self.state.use_overlay:
            v=self.overlay.get_strength(); self.ov_slider.setValue(v)
            self.status.setText(f"✅ Brilho (overlay): {v}/255")
        else:
            self.status.setText(f"✅ Brilho (LUT): {self.state.bright_pct}%")

    # mira
    def _add_slider(self, layout, label, mn, mx, key):
        layout.addWidget(QLabel(label))
        s=QSlider(Qt.Horizontal); s.setMinimum(mn); s.setMaximum(mx)
        s.setValue(self.crosshair.config.get(key, mn)); s.valueChanged.connect(self.apply_crosshair)
        layout.addWidget(s); setattr(self, f"{key}_slider", s); return s

    def choose_color(self):
        dlg=QColorDialog(self); dlg.setOption(QColorDialog.ShowAlphaChannel, False)
        if dlg.exec_():
            c=dlg.selectedColor()
            if c.isValid():
                self.crosshair.config["color"]=c.name(); self.apply_crosshair()

    def apply_crosshair(self):
        cfg=self.crosshair.config
        cfg["size"]=self.size_s.value(); cfg["gap"]=self.gap_s.value()
        cfg["thickness"]=self.thick_s.value(); cfg["opacity"]=self.opac_s.value()
        cfg["style"]=self.style_box.currentText()
        self.crosshair.set_config(cfg)
        with open(CONFIG_FILE,"w",encoding="utf-8") as f: json.dump(cfg,f,indent=4,ensure_ascii=False)

    def set_dark_theme(self):
        self.setStyleSheet("""
            QWidget { background:#0f1115; color:#e6e9ef; font-size:13px; }
            #Hero { background:qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #1f2230, stop:1 #292d3e);
                    border:1px solid #2b2f41; border-radius:12px; padding:16px; margin:8px; }
            #HeroTitle { font-size:20px; font-weight:700; color:#a2d2ff; }
            #HeroSub   { font-size:12px; color:#9aa3b2; }
            #Card { border:1px solid #2b2f41; border-radius:12px; padding:12px; margin:8px; background:#171a21; }
            #Status { color:#9dd79d; padding-top:6px; }
            QPushButton { background:#2a2f3b; color:#e6e9ef; border:1px solid #394055;
                          border-radius:8px; padding:10px 14px; }
            QPushButton:hover  { background:#32394a; }
            QPushButton:pressed{ background:#253042; }
            QPushButton#Primary{ background:#f59e0b; color:#1a1a1a; border:1px solid #c27e07; }
            QPushButton#Success{ background:#22c55e; color:#0b1b12; border:1px solid #1aa34b; }
            QPushButton#Muted  { background:#64748b; color:#0b0f16; border:1px solid #566275; }
            QGroupBox { font-weight:600; margin-top:12px; }
            QGroupBox::title { subcontrol-origin: margin; left:12px; padding:0 4px; color:#aab4c8; }
            QSlider::groove:horizontal { height:8px; background:#1f2532; border:1px solid #2b2f41; border-radius:4px; }
            QSlider::handle:horizontal { background:#a2d2ff; border:1px solid #6aa3d6; width:18px; margin:-5px 0; border-radius:9px; }
        """)

# =========================
# Config
# =========================
def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE,"r",encoding="utf-8") as f: return json.load(f)
        except Exception: pass
    return {"size":15,"gap":5,"thickness":3,"opacity":100,"color":"#00FF00","style":"Clássico"}

# =========================
# Main
# =========================
if __name__=="__main__":
    ensure_admin()
    # --- DPI (IMPORTANTÍSSIMO): faça antes do QApplication ---
    if platform.system()=="Windows":
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per-Monitor DPI Aware
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    if platform.system()!="Windows":
        print("Aviso: este app é para Windows.")
    app=QApplication(sys.argv)
    cfg=load_config()
    state=AppState()
    overlay=FilterOverlay(state)
    crosshair=Crosshair(cfg)
    settings=SettingsWindow(crosshair, overlay, state)
    settings.show(); crosshair.show()
    sys.exit(app.exec_())
