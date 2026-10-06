<div align="center">

# 🎯 MiraPersonalizada

**Mira sobreposta e filtro de visão noturna para jogos no Windows, feitos em Python + PyQt5.**

<p>
  <img src="https://img.shields.io/badge/Python-3.8%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.8+" />
  <img src="https://img.shields.io/badge/PyQt5-41CD52?style=for-the-badge&logo=qt&logoColor=white" alt="PyQt5" />
  <img src="https://img.shields.io/badge/Windows-10%20%7C%2011-0078D6?style=for-the-badge&logo=windows&logoColor=white" alt="Windows" />
  <img src="https://img.shields.io/badge/licen%C3%A7a-MIT-00e5ff?style=for-the-badge" alt="Licença MIT" />
</p>

</div>

---

## ✨ O que ele faz

**Mira sobreposta**
- Sempre centralizada na tela, em qualquer resolução (com suporte a DPI por monitor).
- Quatro formatos: **Clássico**, **Círculo**, **Ponto** e **Retícula**.
- Ajuste em tempo real de tamanho, espaçamento (gap), espessura, opacidade e cor.
- A janela é *click-through*: o mouse passa direto para o jogo.
- Suas configurações são salvas automaticamente em `crosshair_config.json`.

**Filtro "Noite → Dia"**
- Clareia cenas escuras ajustando a curva de gama da tela (LUT), sem custo de desempenho.
- Quando a LUT não está disponível (ex.: sessão RDP), usa um overlay leve como alternativa.
- Filtros prontos: **Clarity**, **NVG Verde**, **Cinza** e **Frio (Lua)**, com controle de força.
- Perfis de um clique (*Noite → Dia*, *Brilho Máximo*, *Padrão*) e ajuste fino de brilho.
- Botão para desligar a Luz Noturna do Windows, que costuma interferir no filtro.
- Pode se anexar à janela do **Rust** e esconder o painel quando o jogo está em foco.

---

## 🚀 Como rodar

### Pré-requisitos
- Windows 10 ou 11
- Python 3.8 ou superior

### Instalação
```bash
git clone https://github.com/yRvtt/MiraPersonalizada.git
cd MiraPersonalizada
pip install PyQt5
python main.py
```

> **Nota:** o app pede permissão de administrador (UAC) ao abrir, porque ajusta a gama da tela e a configuração da Luz Noturna do Windows.

### Gerando o executável (.exe)
```bash
pip install pyinstaller
pyinstaller --onefile --noconsole --icon=icon.ico --name MiraPersonalizada main.py
```
O executável fica em `dist/MiraPersonalizada.exe`.

---

## 🧭 Como usar

1. Abra o app: a mira aparece no centro da tela e o painel de configurações ao lado.
2. Em **Mira**, escolha o formato e ajuste os sliders até ficar do seu jeito.
3. Em **Filtro**, escolha um tipo e a força, ou use um dos perfis de um clique.
4. Entre no jogo em modo **janela sem bordas** para o melhor resultado. Em tela cheia exclusiva, o overlay pode não aparecer.

---

## 🛠️ Tecnologias

- **Python** e **PyQt5** para a interface e o desenho da mira
- **ctypes / Win32 API** (`user32`, `gdi32`) para janelas sempre no topo, click-through e controle da gama da tela

---

## 🤝 Contribuindo

Dúvidas, ideias ou bugs? Abra uma [issue](https://github.com/yRvtt/MiraPersonalizada/issues) ou envie um pull request.

## 📄 Licença

Distribuído sob a licença MIT. Veja [LICENSE](LICENSE).

---

<div align="center">
  Feito por <a href="https://github.com/yRvtt">yRvt</a> · <a href="https://yrvt.com.br">yrvt.com.br</a>
</div>
