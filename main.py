import sys
import os
import json
import platform
import subprocess
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QLabel, QPushButton, QColorDialog, QComboBox, QSlider, QGroupBox,
    QCheckBox, QMessageBox
)
from PyQt5.QtGui import QPainter, QPen, QColor, QPalette, QFont, QIcon
from PyQt5.QtCore import Qt, QPoint

CONFIG_FILE = "crosshair_config.json"
MONITOR_CONFIG_FILE = "monitor_config.json"

class MonitorControl:
    @staticmethod
    def get_os():
        """Retorna o sistema operacional atual"""
        return platform.system()
    
    @staticmethod
    def set_brightness(value):
        """Define o brilho do monitor"""
        os_type = MonitorControl.get_os()
        try:
            if os_type == "Windows":
                # Para Windows, tentamos usar métodos alternativos
                MonitorControl._set_brightness_windows(value)
            elif os_type == "Linux":
                MonitorControl._set_brightness_linux(value)
            elif os_type == "Darwin":  # macOS
                MonitorControl._set_brightness_macos(value)
            return True
        except Exception as e:
            print(f"Erro ao ajustar brilho: {e}")
            return False
    
    @staticmethod
    def _set_brightness_windows(value):
        """Define brilho no Windows"""
        try:
            # Método 1: Usando PowerShell
            brightness = max(0, min(100, value))
            ps_command = f"(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1,{brightness})"
            subprocess.run(["powershell", "-Command", ps_command], capture_output=True)
        except:
            try:
                # Método 2: Usando utility externa (se disponível)
                subprocess.run(["nircmd.exe", "setbrightness", str(value)], capture_output=True)
            except:
                # Método 3: Mensagem para usuário
                print("No Windows, ajuste o brilho manualmente pelas configurações de display")
    
    @staticmethod
    def _set_brightness_linux(value):
        """Define brilho no Linux"""
        try:
            # Tenta encontrar a interface de brilho
            brightness_path = None
            possible_paths = [
                "/sys/class/backlight/intel_backlight/brightness",
                "/sys/class/backlight/acpi_video0/brightness",
                "/sys/class/backlight/nvidia_backlight/brightness",
                "/sys/class/backlight/amdgpu_bl0/brightness",
                "/sys/class/backlight/radeon_bl0/brightness"
            ]
            
            for path in possible_paths:
                if os.path.exists(path):
                    brightness_path = path
                    break
            
            if brightness_path:
                # Encontra o valor máximo de brilho
                max_brightness_path = brightness_path.replace("brightness", "max_brightness")
                if os.path.exists(max_brightness_path):
                    with open(max_brightness_path, 'r') as f:
                        max_brightness = int(f.read().strip())
                    
                    # Calcula o valor absoluto baseado na porcentagem
                    absolute_value = int((value / 100) * max_brightness)
                    
                    # Escreve o valor (precisa de permissões sudo)
                    try:
                        with open(brightness_path, 'w') as f:
                            f.write(str(absolute_value))
                    except PermissionError:
                        # Se não tiver permissão, usa xrandr como fallback
                        display = MonitorControl._get_display_name_linux()
                        brightness = value / 100
                        subprocess.run(['xrandr', '--output', display, '--brightness', str(brightness)], 
                                      capture_output=True)
            else:
                # Fallback para xrandr (ajusta gamma, não brilho real)
                display = MonitorControl._get_display_name_linux()
                brightness = max(0.1, min(3.0, value / 50))  # Converter para escala do xrandr
                subprocess.run(['xrandr', '--output', display, '--brightness', str(brightness)], 
                              capture_output=True)
        except Exception as e:
            print(f"Erro ao ajustar brilho no Linux: {e}")
    
    @staticmethod
    def _set_brightness_macos(value):
        """Define brilho no macOS"""
        try:
            brightness = max(0, min(100, value))
            script = f'''
            tell application "System Events"
                set brightness to {brightness / 100}
            end tell
            '''
            subprocess.run(['osascript', '-e', script], capture_output=True)
        except:
            print("Não foi possível ajustar o brilho no macOS")
    
    @staticmethod
    def _get_display_name_linux():
        """Obtém o nome do display no Linux"""
        try:
            result = subprocess.run(['xrandr', '--query'], capture_output=True, text=True)
            lines = result.stdout.split('\n')
            for line in lines:
                if ' connected' in line:
                    return line.split()[0]
        except:
            pass
        return "eDP-1"  # Valor padrão comum
    
    @staticmethod
    def set_contrast(value):
        """Define o contraste do monitor"""
        os_type = MonitorControl.get_os()
        try:
            if os_type == "Linux":
                # No Linux, usa xgamma para ajustar contraste
                gamma = 1.0 + (value - 50) / 100  # Converter para escala do gamma
                subprocess.run(['xgamma', '-gamma', str(gamma)], capture_output=True)
            else:
                # Windows/macOS - mensagem informativa
                print(f"Ajuste o contraste para {value}% manualmente nas configurações do monitor")
            return True
        except Exception as e:
            print(f"Erro ao ajustar contraste: {e}")
            return False
    
    @staticmethod
    def set_night_mode(enabled):
        """Ativa/desativa o modo noturno"""
        os_type = MonitorControl.get_os()
        try:
            if os_type == "Linux":
                if enabled:
                    subprocess.run(['redshift', '-O', '4500'], capture_output=True)
                else:
                    subprocess.run(['redshift', '-x'], capture_output=True)
            elif os_type == "Windows":
                if enabled:
                    subprocess.run(['reg', 'add', 
                                   'HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\CloudStore\\Store\\DefaultAccount\\Current\\default$windows.data.bluelightreduction.bluelightreductionstate', 
                                   '/v', 'Data', '/t', 'REG_BINARY', '/d', '0250000000000000', '/f'], 
                                  capture_output=True)
                else:
                    subprocess.run(['reg', 'add', 
                                   'HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\CloudStore\\Store\\DefaultAccount\\Current\\default$windows.data.bluelightreduction.bluelightreductionstate', 
                                   '/v', 'Data', '/t', 'REG_BINARY', '/d', '0200000000000000', '/f'], 
                                  capture_output=True)
            elif os_type == "Darwin":
                if enabled:
                    subprocess.run(['osascript', '-e', 
                                  'tell application "System Events" to tell appearance preferences to set dark mode to true'], 
                                  capture_output=True)
                else:
                    subprocess.run(['osascript', '-e', 
                                  'tell application "System Events" to tell appearance preferences to set dark mode to false'], 
                                  capture_output=True)
            return True
        except Exception as e:
            print(f"Erro ao ajustar modo noturno: {e}")
            return False
    
    @staticmethod
    def set_gamma(value):
        """Ajusta o gamma da tela"""
        os_type = MonitorControl.get_os()
        try:
            if os_type == "Linux":
                gamma = value / 50  # Converter para escala do xgamma
                subprocess.run(['xgamma', '-gamma', str(gamma)], capture_output=True)
            else:
                print(f"Ajuste gamma para {value}% manualmente se disponível")
            return True
        except Exception as e:
            print(f"Erro ao ajustar gamma: {e}")
            return False

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
        self.setWindowTitle("Mira Personalizada • Multiplataforma")
        self.setFixedSize(600, 700)
        self.set_dark_theme()
        self.init_ui()
        
        # Mostrar informações do sistema
        self.show_system_info()

    def show_system_info(self):
        """Mostra informações do sistema operacional"""
        os_name = platform.system()
        os_info = f"Sistema: {os_name}"
        if os_name == "Linux":
            try:
                distro = platform.freedesktop_os_release().get('PRETTY_NAME', 'Linux')
                os_info = f"Sistema: {distro}"
            except:
                pass
        print(os_info)

    def init_ui(self):
        layout = QVBoxLayout()
        
        # Título com informação do OS
        os_name = platform.system()
        title_label = QLabel(f"Mira Personalizada - {os_name}")
        title_label.setStyleSheet("color: #aa55ff; font-weight: bold; font-size: 16px;")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # Criar abas
        tabs = QTabWidget()
        
        # Aba de Controles de Monitor
        monitor_tab = QWidget()
        monitor_layout = QVBoxLayout()
        monitor_tab.setLayout(monitor_layout)
        
        # Informações do sistema
        info_label = QLabel(self.get_os_specific_info())
        info_label.setStyleSheet("color: #ff7700; background-color: #222; padding: 5px;")
        info_label.setWordWrap(True)
        monitor_layout.addWidget(info_label)
        
        # Grupo de controles de brilho
        brightness_group = QGroupBox("CONTROLES DE BRILHO")
        brightness_group.setStyleSheet("QGroupBox { color: yellow; font-weight: bold; }")
        brightness_layout = QVBoxLayout()
        
        self.brightness_slider = self._create_monitor_slider(brightness_layout, "BRILHO", 0, 100, 
                                                           self.monitor_config.get("brightness", 50),
                                                           self.apply_brightness)
        brightness_group.setLayout(brightness_layout)
        monitor_layout.addWidget(brightness_group)
        
        # Grupo de controles de contraste
        contrast_group = QGroupBox("CONTROLES DE CONTRASTE")
        contrast_group.setStyleSheet("QGroupBox { color: cyan; font-weight: bold; }")
        contrast_layout = QVBoxLayout()
        
        self.contrast_slider = self._create_monitor_slider(contrast_layout, "CONTRASTE", 0, 100,
                                                         self.monitor_config.get("contrast", 50),
                                                         self.apply_contrast)
        contrast_group.setLayout(contrast_layout)
        monitor_layout.addWidget(contrast_group)
        
        # Grupo de controles de gamma
        gamma_group = QGroupBox("CONTROLES DE GAMMA")
        gamma_group.setStyleSheet("QGroupBox { color: #ff77ff; font-weight: bold; }")
        gamma_layout = QVBoxLayout()
        
        self.gamma_slider = self._create_monitor_slider(gamma_layout, "GAMMA", 0, 100,
                                                      self.monitor_config.get("gamma", 50),
                                                      self.apply_gamma)
        gamma_group.setLayout(gamma_layout)
        monitor_layout.addWidget(gamma_group)
        
        # Modo noturno
        night_mode_group = QGroupBox("MODO NOTURNO")
        night_mode_group.setStyleSheet("QGroupBox { color: #ff7700; font-weight: bold; }")
        night_mode_layout = QVBoxLayout()
        
        self.night_mode_checkbox = QCheckBox("Ativar Modo Noturno (Reduz Luz Azul)")
        self.night_mode_checkbox.setChecked(self.monitor_config.get("night_mode", False))
        self.night_mode_checkbox.stateChanged.connect(self.toggle_night_mode)
        night_mode_layout.addWidget(self.night_mode_checkbox)
        
        night_mode_group.setLayout(night_mode_layout)
        monitor_layout.addWidget(night_mode_group)
        
        # Botões de preset
        preset_group = QGroupBox("PRESETS RÁPIDOS")
        preset_group.setStyleSheet("QGroupBox { color: #aa55ff; font-weight: bold; }")
        preset_layout = QHBoxLayout()
        
        night_preset_btn = QPushButton("Preset Noite")
        night_preset_btn.setStyleSheet("QPushButton { background-color: #aa55ff; color: white; }")
        night_preset_btn.clicked.connect(self.apply_night_preset)
        preset_layout.addWidget(night_preset_btn)
        
        default_preset_btn = QPushButton("Padrão")
        default_preset_btn.setStyleSheet("QPushButton { background-color: #333; color: white; }")
        default_preset_btn.clicked.connect(self.apply_default_preset)
        preset_layout.addWidget(default_preset_btn)
        
        preset_group.setLayout(preset_layout)
        monitor_layout.addWidget(preset_group)
        
        tabs.addTab(monitor_tab, "Monitor")
        
        # Aba da Mira
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

    def get_os_specific_info(self):
        """Retorna informações específicas do sistema operacional"""
        os_name = platform.system()
        if os_name == "Linux":
            return "Linux: Use os controles deslizantes para ajustar brilho, contraste e gamma. Certifique-se de ter xgamma e xrandr instalados."
        elif os_name == "Windows":
            return "Windows: Alguns controles podem requerer ajuste manual nas configurações de display."
        elif os_name == "Darwin":
            return "macOS: Controles funcionam via AppleScript. Pode precisar de permissões."
        else:
            return f"{os_name}: Controles podem ter funcionalidade limitada."

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
        label.setStyleSheet("color: white;")
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
        MonitorControl.set_brightness(value)
        self.save_monitor_config()
    
    def apply_contrast(self, value):
        self.monitor_config["contrast"] = value
        MonitorControl.set_contrast(value)
        self.save_monitor_config()
    
    def apply_gamma(self, value):
        self.monitor_config["gamma"] = value
        MonitorControl.set_gamma(value)
        self.save_monitor_config()
    
    def toggle_night_mode(self, state):
        enabled = state == Qt.Checked
        self.monitor_config["night_mode"] = enabled
        MonitorControl.set_night_mode(enabled)
        self.save_monitor_config()
    
    def apply_night_preset(self):
        """Preset recomendado para jogos noturnos"""
        self.brightness_slider.setValue(70)
        self.contrast_slider.setValue(80)
        self.gamma_slider.setValue(60)
        self.night_mode_checkbox.setChecked(True)
    
    def apply_default_preset(self):
        """Restaura configurações padrão"""
        self.brightness_slider.setValue(50)
        self.contrast_slider.setValue(50)
        self.gamma_slider.setValue(50)
        self.night_mode_checkbox.setChecked(False)
        # Aplicar as configurações
        self.apply_brightness(50)
        self.apply_contrast(50)
        self.apply_gamma(50)
        MonitorControl.set_night_mode(False)
    
    def apply_monitor_settings(self):
        # Aplicar configurações salvas ao iniciar
        MonitorControl.set_brightness(self.monitor_config.get("brightness", 50))
        MonitorControl.set_contrast(self.monitor_config.get("contrast", 50))
        MonitorControl.set_gamma(self.monitor_config.get("gamma", 50))
        MonitorControl.set_night_mode(self.monitor_config.get("night_mode", False))

    def save_crosshair_config(self):
        with open(CONFIG_FILE, "w") as f:
            json.dump(self.crosshair_widget.config, f, indent=4)
    
    def save_monitor_config(self):
        with open(MONITOR_CONFIG_FILE, "w") as f:
            json.dump(self.monitor_config, f, indent=4)

    def open_about(self):
        os_name = platform.system()
        message = f"""
        Mira Overlay com Controles de Monitor - Multiplataforma
        
        Sistema: {os_name}
        
        Funcionalidades:
        - Mira personalizável para jogos
        - Controles de brilho, contraste e gamma
        - Modo noturno para reduzir luz azul
        - Presets para configurações rápidas
        
        Notas:
        • No Linux: Instale x11-xserver-utils para funcionalidade completa
        • No Windows: Alguns controles podem precisar de ajuste manual
        • No macOS: Funcionalidade via AppleScript
        
        Desenvolvido para funcionar em Windows, Linux e macOS
        """
        
        QMessageBox.information(self, "Sobre", message)

    def set_dark_theme(self):
        # Tema escuro simples
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
            QCheckBox {
                color: #ffffff;
                spacing: 5px;
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
        "color": "#00FF00",
        "style": "Clássico"
    }


def load_monitor_config():
    if os.path.exists(MONITOR_CONFIG_FILE):
        with open(MONITOR_CONFIG_FILE, "r") as f:
            return json.load(f)
    return {
        "brightness": 50,
        "contrast": 50,
        "gamma": 50,
        "night_mode": False
    }


if __name__ == "__main__":
    app = QApplication(sys.argv)
    config = load_config()
    crosshair = Crosshair(config)
    settings = SettingsWindow(crosshair)

    crosshair.show()
    settings.show()

    sys.exit(app.exec_())