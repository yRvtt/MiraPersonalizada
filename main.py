import sys
import os
import json
import ctypes
from ctypes import wintypes
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QLabel, QPushButton, QColorDialog, QComboBox, QSlider, QGroupBox,
    QCheckBox, QMessageBox
)
from PyQt5.QtGui import QPainter, QPen, QColor, QPalette, QFont, QIcon
from PyQt5.QtCore import Qt, QPoint

CONFIG_FILE = "crosshair_config.json"
MONITOR_CONFIG_FILE = "monitor_config.json"

# Configurações para acesso à API do Windows
user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

class WindowsMonitorControl:
    @staticmethod
    def set_brightness(value):
        """Define o brilho do monitor usando a API do Windows"""
        try:
            # Tenta usar a API do Windows para ajustar o brilho
            hdc = user32.GetDC(0)
            gamma_ramp = WindowsMonitorControl._create_gamma_ramp(value / 100)
            success = gdi32.SetDeviceGammaRamp(hdc, ctypes.byref(gamma_ramp))
            user32.ReleaseDC(0, hdc)
            return bool(success)
        except Exception as e:
            print(f"Erro ao ajustar brilho: {e}")
            return False

    @staticmethod
    def _create_gamma_ramp(brightness_factor):
        """Cria uma rampa gamma para ajustar o brilho"""
        class GammaRamp(ctypes.Structure):
            _fields_ = [('red', (wintypes.WORD * 256)),
                       ('green', (wintypes.WORD * 256)),
                       ('blue', (wintypes.WORD * 256))]
        
        ramp = GammaRamp()
        
        for i in range(256):
            # Ajusta cada componente de cor com o fator de brilho
            ramp.red[i] = int(min(65535, max(0, i * 257 * brightness_factor)))
            ramp.green[i] = int(min(65535, max(0, i * 257 * brightness_factor)))
            ramp.blue[i] = int(min(65535, max(0, i * 257 * brightness_factor)))
        
        return ramp

    @staticmethod
    def set_high_contrast_mode(enabled):
        """Ativa/desativa o modo de alto contraste do Windows"""
        try:
            if enabled:
                # Configurações de alto contraste (preto no branco)
                os.system('reg add "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Themes" /v CurrentTheme /t REG_EXPAND_SZ /d "" /f')
                os.system('reg add "HKCU\\Control Panel\\Colors" /v Window /t REG_SZ /d "255 255 255" /f')
                os.system('reg add "HKCU\\Control Panel\\Colors" /v WindowText /t REG_SZ /d "0 0 0" /f')
                os.system('reg add "HKCU\\Control Panel\\Colors" /v Highlight /t REG_SZ /d "0 0 255" /f')
                os.system('reg add "HKCU\\Control Panel\\Colors" /v HighlightText /t REG_SZ /d "255 255 255" /f')
            else:
                # Restaura as configurações padrão
                os.system('reg delete "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Themes" /v CurrentTheme /f')
                os.system('reg delete "HKCU\\Control Panel\\Colors" /v Window /f')
                os.system('reg delete "HKCU\\Control Panel\\Colors" /v WindowText /f')
                os.system('reg delete "HKCU\\Control Panel\\Colors" /v Highlight /f')
                os.system('reg delete "HKCU\\Control Panel\\Colors" /v HighlightText /f')
            
            # Força a atualização do sistema
            user32.SystemParametersInfoW(0x0015, 0, None, 0)  # SPI_SETWORKAREA
            return True
        except Exception as e:
            print(f"Erro ao ajustar contraste: {e}")
            return False

    @staticmethod
    def set_night_light(enabled, intensity=80):
        """Configura o modo noturno/luz noturna do Windows"""
        try:
            if enabled:
                # Ativa o modo noturno com intensidade especificada
                os.system(f'reg add "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\CloudStore\\Store\\DefaultAccount\\Current\\default$windows.data.bluelightreduction.bluelightreductionstate" /v Data /t REG_BINARY /d "02{intensity:02x}0000000000" /f')
            else:
                # Desativa o modo noturno
                os.system('reg add "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\CloudStore\\Store\\DefaultAccount\\Current\\default$windows.data.bluelightreduction.bluelightreductionstate" /v Data /t REG_BINARY /d "0200000000000000" /f')
            
            return True
        except Exception as e:
            print(f"Erro ao ajustar modo noturno: {e}")
            return False

    @staticmethod
    def set_color_profile(profile_type):
        """Aplica um perfil de cor pré-definido"""
        try:
            if profile_type == "vibrant":
                # Perfil vibrante - cores saturadas
                for i in range(256):
                    # Aumenta a saturação das cores
                    pass  # Implementação simplificada
            elif profile_type == "night_vision":
                # Perfil para visão noturna - verde intenso
                hdc = user32.GetDC(0)
                ramp = WindowsMonitorControl._create_night_vision_ramp()
                success = gdi32.SetDeviceGammaRamp(hdc, ctypes.byref(ramp))
                user32.ReleaseDC(0, hdc)
                return bool(success)
            
            return True
        except Exception as e:
            print(f"Erro ao ajustar perfil de cor: {e}")
            return False

    @staticmethod
    def _create_night_vision_ramp():
        """Cria uma rampa gamma para modo de visão noturna (verde)"""
        class GammaRamp(ctypes.Structure):
            _fields_ = [('red', (wintypes.WORD * 256)),
                       ('green', (wintypes.WORD * 256)),
                       ('blue', (wintypes.WORD * 256))]
        
        ramp = GammaRamp()
        
        for i in range(256):
            # Reduz vermelho e azul, mantém verde
            ramp.red[i] = int(i * 100)  # Vermelho reduzido
            ramp.green[i] = int(i * 257 * 1.5)  # Verde intensificado
            ramp.blue[i] = int(i * 100)  # Azul reduzido
        
        return ramp


class Crosshair(QWidget):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.resize(200, 200)
        self.show()
        self.update_position()

    def update_position(self):
        screen = QApplication.primaryScreen().geometry()
        x = screen.center().x() - self.width() // 2
        y = screen.center().y() - self.height() // 2
        self.move(x, y)

    def set_config(self, config):
        self.config = config
        self.update()

    def paintEvent(self, event):
        self.update_position()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        center = self.rect().center()

        size = self.config.get("size", 10)
        gap = self.config.get("gap", 4)
        thickness = self.config.get("thickness", 2)
        opacity = self.config.get("opacity", 100)
        style = self.config.get("style", "Clássico")
        color = QColor(self.config.get("color", "#00FF00"))
        color.setAlphaF(opacity / 100)

        pen_main = QPen(color, thickness)
        pen_shadow = QPen(QColor(0, 0, 0, 160), thickness + 1)

        def draw_line(x1, y1, x2, y2):
            painter.setPen(pen_shadow)
            painter.drawLine(x1, y1, x2, y2)
            painter.setPen(pen_main)
            painter.drawLine(x1, y1, x2, y2)

        if style == "Clássico":
            draw_line(center.x(), center.y() - gap - size, center.x(), center.y() - gap)
            draw_line(center.x(), center.y() + gap, center.x(), center.y() + gap + size)
            draw_line(center.x() - gap - size, center.y(), center.x() - gap, center.y())
            draw_line(center.x() + gap, center.y(), center.x() + gap + size, center.y())

        elif style == "Círculo":
            painter.setPen(pen_shadow)
            painter.drawEllipse(center, size + 1, size + 1)
            painter.setPen(pen_main)
            painter.drawEllipse(center, size, size)

        elif style == "Ponto":
            painter.setPen(Qt.NoPen)
            painter.setBrush(color)
            painter.drawEllipse(center, size, size)

        elif style == "Retícula":
            draw_line(center.x(), center.y() - gap - size, center.x(), center.y() - gap)
            draw_line(center.x(), center.y() + gap, center.x(), center.y() + gap + size)
            draw_line(center.x() - gap - size, center.y(), center.x() - gap, center.y())
            draw_line(center.x() + gap, center.y(), center.x() + gap + size, center.y())


class SettingsWindow(QWidget):
    def __init__(self, crosshair_widget):
        super().__init__()
        self.crosshair_widget = crosshair_widget
        self.monitor_config = load_monitor_config()
        self.setWindowTitle("Mira + Controles de Monitor - Visibilidade Noturna")
        self.setWindowIcon(QIcon("icon.ico"))
        self.setFixedSize(600, 700)
        self.set_dark_theme()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        
        # Criar abas
        tabs = QTabWidget()
        
        # Aba de Controles de Monitor (PRINCIPAL)
        monitor_tab = QWidget()
        monitor_layout = QVBoxLayout()
        monitor_tab.setLayout(monitor_layout)
        
        # Grupo de controles de brilho
        brightness_group = QGroupBox("CONTROLES DE BRILHO (Máxima Visibilidade)")
        brightness_group.setStyleSheet("QGroupBox { color: yellow; font-weight: bold; border: 2px solid yellow; }")
        brightness_layout = QVBoxLayout()
        
        self.brightness_slider = self._create_monitor_slider(brightness_layout, "BRILHO", 0, 100, 
                                                           self.monitor_config.get("brightness", 80),
                                                           self.apply_brightness)
        brightness_group.setLayout(brightness_layout)
        monitor_layout.addWidget(brightness_group)
        
        # Grupo de controles de contraste
        contrast_group = QGroupBox("CONTROLES DE CONTRASTE (Melhor Detecção)")
        contrast_group.setStyleSheet("QGroupBox { color: cyan; font-weight: bold; border: 2px solid cyan; }")
        contrast_layout = QVBoxLayout()
        
        self.contrast_slider = self._create_monitor_slider(contrast_layout, "CONTRASTE", 0, 100,
                                                         self.monitor_config.get("contrast", 80),
                                                         self.apply_contrast)
        contrast_group.setLayout(contrast_layout)
        monitor_layout.addWidget(contrast_group)
        
        # Modos especiais
        special_modes_group = QGroupBox("MODOS ESPECIAIS (Visibilidade Noturna)")
        special_modes_group.setStyleSheet("QGroupBox { color: #ff7700; font-weight: bold; border: 2px solid #ff7700; }")
        special_modes_layout = QVBoxLayout()
        
        # Modo de alto contraste
        self.high_contrast_checkbox = QCheckBox("MÁXIMO CONTRASTE (Preto/Branco)")
        self.high_contrast_checkbox.setChecked(self.monitor_config.get("high_contrast", False))
        self.high_contrast_checkbox.stateChanged.connect(self.toggle_high_contrast)
        special_modes_layout.addWidget(self.high_contrast_checkbox)
        
        # Modo visão noturna
        self.night_vision_checkbox = QCheckBox("VISÃO NOTURNA (Ênfase em Verde)")
        self.night_vision_checkbox.setChecked(self.monitor_config.get("night_vision", False))
        self.night_vision_checkbox.stateChanged.connect(self.toggle_night_vision)
        special_modes_layout.addWidget(self.night_vision_checkbox)
        
        # Modo noturno (luz azul)
        self.night_light_checkbox = QCheckBox("LUZ NOTURNA (Reduzir Luz Azul)")
        self.night_light_checkbox.setChecked(self.monitor_config.get("night_light", False))
        self.night_light_checkbox.stateChanged.connect(self.toggle_night_light)
        special_modes_layout.addWidget(self.night_light_checkbox)
        
        special_modes_group.setLayout(special_modes_layout)
        monitor_layout.addWidget(special_modes_group)
        
        # Botões de preset
        preset_group = QGroupBox("PRESETS RÁPIDOS")
        preset_group.setStyleSheet("QGroupBox { color: #aa55ff; font-weight: bold; border: 2px solid #aa55ff; }")
        preset_layout = QHBoxLayout()
        
        night_preset_btn = QPushButton("PRESET NOITE (Recomendado)")
        night_preset_btn.setStyleSheet("QPushButton { background-color: #aa55ff; color: white; font-weight: bold; }")
        night_preset_btn.clicked.connect(self.apply_night_preset)
        preset_layout.addWidget(night_preset_btn)
        
        extreme_preset_btn = QPushButton("MÁXIMA VISIBILIDADE")
        extreme_preset_btn.setStyleSheet("QPushButton { background-color: red; color: white; font-weight: bold; }")
        extreme_preset_btn.clicked.connect(self.apply_extreme_preset)
        preset_layout.addWidget(extreme_preset_btn)
        
        default_preset_btn = QPushButton("PADRÃO")
        default_preset_btn.setStyleSheet("QPushButton { background-color: #333; color: white; }")
        default_preset_btn.clicked.connect(self.apply_default_preset)
        preset_layout.addWidget(default_preset_btn)
        
        preset_group.setLayout(preset_layout)
        monitor_layout.addWidget(preset_group)
        
        # Aviso
        warning_label = QLabel("AVISO: Estas configurações podem deixar as cores exageradas, mas melhoram a visibilidade noturna!")
        warning_label.setStyleSheet("color: red; font-weight: bold; background-color: black; padding: 5px;")
        warning_label.setWordWrap(True)
        monitor_layout.addWidget(warning_label)
        
        tabs.addTab(monitor_tab, "MONITOR (Principal)")
        
        # Aba da Mira (secundária)
        crosshair_tab = QWidget()
        crosshair_layout = QVBoxLayout()
        crosshair_tab.setLayout(crosshair_layout)
        
        self.size_input = self._create_slider(crosshair_layout, "Tamanho", 1, 100, "size")
        self.gap_input = self._create_slider(crosshair_layout, "Espaçamento (Gap)", 0, 50, "gap")
        self.thickness_input = self._create_slider(crosshair_layout, "Espessura", 1, 10, "thickness")
        self.opacity_input = self._create_slider(crosshair_layout, "Opacidade", 10, 100, "opacity")

        color_button = QPushButton("Escolher Cor da Mira")
        color_button.clicked.connect(self.choose_color)
        crosshair_layout.addWidget(color_button)

        style_layout = QHBoxLayout()
        style_label = QLabel("Formato:")
        style_label.setStyleSheet("color: white;")
        style_layout.addWidget(style_label)

        self.style_box = QComboBox()
        self.style_box.addItems(["Clássico", "Círculo", "Ponto", "Retícula"])
        self.style_box.setCurrentText(self.crosshair_widget.config.get("style", "Clássico"))
        self.style_box.currentTextChanged.connect(self.apply_crosshair_settings)
        style_layout.addWidget(self.style_box)
        crosshair_layout.addLayout(style_layout)
        
        tabs.addTab(crosshair_tab, "Mira")
        
        layout.addWidget(tabs)
        
        # Botão de sobre
        about_button = QPushButton("Sobre e Ajuda")
        about_button.clicked.connect(self.open_about)
        layout.addWidget(about_button)

        self.setLayout(layout)
        
        # Aplicar configurações iniciais
        self.apply_monitor_settings()

    def _create_slider(self, layout, label_text, min_val, max_val, config_key):
        label = QLabel(label_text)
        label.setStyleSheet("color: white;")
        layout.addWidget(label)

        slider = QSlider(Qt.Horizontal)
        slider.setMinimum(min_val)
        slider.setMaximum(max_val)
        slider.setValue(self.crosshair_widget.config.get(config_key, min_val))
        slider.valueChanged.connect(self.apply_crosshair_settings)
        layout.addWidget(slider)

        setattr(self, f"{config_key}_slider", slider)
        return slider
    
    def _create_monitor_slider(self, layout, label_text, min_val, max_val, default_val, callback):
        label = QLabel(f"{label_text}: {default_val}%")
        label.setStyleSheet("color: white; font-weight: bold;")
        layout.addWidget(label)

        slider = QSlider(Qt.Horizontal)
        slider.setMinimum(min_val)
        slider.setMaximum(max_val)
        slider.setValue(default_val)
        slider.valueChanged.connect(lambda value: self._on_monitor_slider_change(value, label, label_text, callback))
        layout.addWidget(slider)

        return slider
    
    def _on_monitor_slider_change(self, value, label, label_text, callback):
        label.setText(f"{label_text}: {value}%")
        callback(value)

    def choose_color(self):
        dialog = QColorDialog(self)
        dialog.setOption(QColorDialog.ShowAlphaChannel, False)
        if dialog.exec_():
            selected_color = dialog.selectedColor()
            if selected_color.isValid():
                self.crosshair_widget.config["color"] = selected_color.name()
                self.apply_crosshair_settings()

    def apply_crosshair_settings(self):
        config = self.crosshair_widget.config
        config["size"] = self.size_slider.value()
        config["gap"] = self.gap_slider.value()
        config["thickness"] = self.thickness_slider.value()
        config["opacity"] = self.opacity_slider.value()
        config["style"] = self.style_box.currentText()
        self.crosshair_widget.set_config(config)
        self.save_crosshair_config()
    
    def apply_brightness(self, value):
        self.monitor_config["brightness"] = value
        WindowsMonitorControl.set_brightness(value/100)
        self.save_monitor_config()
    
    def apply_contrast(self, value):
        self.monitor_config["contrast"] = value
        # Para Windows, usamos o modo de alto contraste como alternativa
        if value > 80:
            WindowsMonitorControl.set_high_contrast_mode(True)
        self.save_monitor_config()
    
    def toggle_high_contrast(self, state):
        enabled = state == Qt.Checked
        self.monitor_config["high_contrast"] = enabled
        WindowsMonitorControl.set_high_contrast_mode(enabled)
        self.save_monitor_config()
    
    def toggle_night_vision(self, state):
        enabled = state == Qt.Checked
        self.monitor_config["night_vision"] = enabled
        if enabled:
            WindowsMonitorControl.set_color_profile("night_vision")
            # Desativa outros modos
            self.night_light_checkbox.setChecked(False)
            self.high_contrast_checkbox.setChecked(False)
        self.save_monitor_config()
    
    def toggle_night_light(self, state):
        enabled = state == Qt.Checked
        self.monitor_config["night_light"] = enabled
        WindowsMonitorControl.set_night_light(enabled, 80)
        self.save_monitor_config()
    
    def apply_night_preset(self):
        """Preset recomendado para jogos noturnos"""
        self.brightness_slider.setValue(85)
        self.contrast_slider.setValue(90)
        self.night_vision_checkbox.setChecked(True)
        self.night_light_checkbox.setChecked(True)
        self.high_contrast_checkbox.setChecked(False)
    
    def apply_extreme_preset(self):
        """Preset de máxima visibilidade (cores exageradas)"""
        self.brightness_slider.setValue(100)
        self.contrast_slider.setValue(100)
        self.high_contrast_checkbox.setChecked(True)
        self.night_vision_checkbox.setChecked(False)
        self.night_light_checkbox.setChecked(False)
    
    def apply_default_preset(self):
        """Restaura configurações padrão"""
        self.brightness_slider.setValue(50)
        self.contrast_slider.setValue(50)
        self.high_contrast_checkbox.setChecked(False)
        self.night_vision_checkbox.setChecked(False)
        self.night_light_checkbox.setChecked(False)
        WindowsMonitorControl.set_high_contrast_mode(False)
        WindowsMonitorControl.set_night_light(False)
        WindowsMonitorControl.set_brightness(0.5)
    
    def apply_monitor_settings(self):
        # Aplicar configurações salvas ao iniciar
        WindowsMonitorControl.set_brightness(self.monitor_config.get("brightness", 80)/100)
        if self.monitor_config.get("high_contrast", False):
            WindowsMonitorControl.set_high_contrast_mode(True)
        if self.monitor_config.get("night_light", False):
            WindowsMonitorControl.set_night_light(True, 80)
        if self.monitor_config.get("night_vision", False):
            WindowsMonitorControl.set_color_profile("night_vision")

    def save_crosshair_config(self):
        with open(CONFIG_FILE, "w") as f:
            json.dump(self.crosshair_widget.config, f, indent=4)
    
    def save_monitor_config(self):
        with open(MONITOR_CONFIG_FILE, "w") as f:
            json.dump(self.monitor_config, f, indent=4)

    def open_about(self):
        QMessageBox.information(self, "Sobre", 
            "Mira Overlay com Controles de Monitor para Windows\n\n"
            "Foco em máxima visibilidade para jogos noturnos\n\n"
            "RECOMENDAÇÕES:\n"
            "- Use o 'PRESET NOITE' para melhor visibilidade\n"
            "- 'MÁXIMA VISIBILIDADE' para situações extremas\n"
            "- As cores podem ficar exageradas mas melhoram a detecção\n\n"
            "Desenvolvido para funcionar no Windows 7/10/11")

    def set_dark_theme(self):
        # Tema escuro simples para melhor contraste
        self.setStyleSheet("""
            QWidget {
                background-color: #222222;
                color: #ffffff;
            }
            QTabWidget::pane {
                border: 1px solid #444444;
            }
            QTabBar::tab {
                background: #333333;
                color: #ffffff;
                padding: 8px;
            }
            QTabBar::tab:selected {
                background: #444444;
                border-bottom: 2px solid #aa55ff;
            }
            QSlider::groove:horizontal {
                border: 1px solid #444444;
                height: 8px;
                background: #333333;
                margin: 2px 0;
            }
            QSlider::handle:horizontal {
                background: #aa55ff;
                border: 1px solid #777777;
                width: 18px;
                margin: -2px 0;
                border-radius: 3px;
            }
            QSlider::sub-page:horizontal {
                background: #aa55ff;
            }
            QCheckBox {
                color: #ffffff;
                spacing: 5px;
            }
            QCheckBox::indicator {
                width: 15px;
                height: 15px;
            }
            QCheckBox::indicator:unchecked {
                border: 1px solid #777777;
                background: #333333;
            }
            QCheckBox::indicator:checked {
                border: 1px solid #777777;
                background: #aa55ff;
            }
        """)


def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {
        "size": 15,
        "gap": 5,
        "thickness": 3,
        "opacity": 100,
        "color": "#00FF00",  # Verde bem visível
        "style": "Clássico"
    }


def load_monitor_config():
    if os.path.exists(MONITOR_CONFIG_FILE):
        with open(MONITOR_CONFIG_FILE, "r") as f:
            return json.load(f)
    return {
        "brightness": 80,
        "contrast": 80,
        "high_contrast": False,
        "night_vision": False,
        "night_light": True
    }


if __name__ == "__main__":
    # Verificar se é Windows
    if not sys.platform.startswith('win'):
        QMessageBox.critical(None, "Erro", "Este aplicativo é apenas para Windows!")
        sys.exit(1)
    
    app = QApplication(sys.argv)
    config = load_config()
    crosshair = Crosshair(config)
    settings = SettingsWindow(crosshair)

    crosshair.show()
    settings.show()

    sys.exit(app.exec_())