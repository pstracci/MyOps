# modules/common/terminal_widget.py

import subprocess
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QLineEdit, QLabel
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtGui import QFont, QPalette, QColor

class TerminalOutputReader(QThread):
    """
    Thread dedicada a ler a saída de um processo externo sem bloquear a UI.
    """
    # Sinal que emite cada nova linha de texto recebida
    newLine = pyqtSignal(str)
    # Sinal emitido quando o processo termina
    finished = pyqtSignal(int)

    def __init__(self, process):
        super().__init__()
        self.process = process

    def run(self):
        # Lemos a saída padrão (stdout) linha por linha enquanto o processo estiver rodando
        for line in iter(self.process.stdout.readline, ''):
            self.newLine.emit(line.strip())

        # Lemos a saída de erro (stderr) da mesma forma
        for line in iter(self.process.stderr.readline, ''):
            self.newLine.emit(f"ERROR: {line.strip()}")

        self.process.wait()
        self.finished.emit(self.process.returncode)

class EmbeddedTerminal(QWidget):
    """
    Um widget que simula um terminal, com área de output e linha de input.
    """
    processFinished = pyqtSignal(int, str) # Sinal emitido com o código de saída e todo o texto

    def __init__(self, parent=None):
        super().__init__(parent)
        self.process = None
        self.reader_thread = None
        self.full_output = []

        # --- Configuração da UI do Terminal ---
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self.output_view = QTextEdit(self)
        self.output_view.setReadOnly(True)
        self.output_view.setFont(QFont("Consolas", 10))

        # Estilo "dark" para o terminal
        palette = self.output_view.palette()
        palette.setColor(QPalette.ColorRole.Base, QColor(20, 20, 20))
        palette.setColor(QPalette.ColorRole.Text, QColor(220, 220, 220))
        self.output_view.setPalette(palette)

        self.input_line = QLineEdit(self)
        self.input_line.setFont(QFont("Consolas", 10))
        self.input_line.returnPressed.connect(self.send_input)
        self.input_line.setPalette(palette)

        layout.addWidget(self.output_view)
        layout.addWidget(self.input_line)

    def execute(self, command):
        """Inicia a execução de um comando externo."""
        if self.process and self.process.poll() is None:
            self.append_output("--- Um processo já está em execução. ---")
            return

        self.output_view.clear()
        self.full_output = []
        self.append_output(f"> {command}\n")

        # Inicia o processo
        self.process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE,
            text=True, # Trabalha com strings em vez de bytes
            encoding='utf-8',
            errors='replace',
            bufsize=1 # Line-buffered
        )

        # Inicia a thread para ler a saída do processo
        self.reader_thread = TerminalOutputReader(self.process)
        self.reader_thread.newLine.connect(self.append_output)
        self.reader_thread.finished.connect(self.on_process_finished)
        self.reader_thread.start()

    def send_input(self):
        """Envia o texto da linha de input para o processo."""
        if self.process and self.process.poll() is None:
            user_input = self.input_line.text()
            self.input_line.clear()
            # Anexa a entrada do usuário ao output para visualização
            self.append_output(user_input, is_input=True) 

            # Envia o comando para o stdin do processo
            self.process.stdin.write(user_input + '\n')
            self.process.stdin.flush()

    def append_output(self, text, is_input=False):
        """Adiciona texto à área de output."""
        if is_input:
            # Apenas mostra o que o usuário digitou, não armazena no log final
            self.output_view.append(f"<em>&gt; {text}</em>") # Mostra em itálico
        else:
            self.output_view.append(text)
            self.full_output.append(text)

        # Rola para o final
        self.output_view.verticalScrollBar().setValue(self.output_view.verticalScrollBar().maximum())

    def on_process_finished(self, return_code):
        """Chamado quando a thread informa que o processo terminou."""
        self.append_output(f"\n--- Processo finalizado com código: {return_code} ---")
        self.processFinished.emit(return_code, "\n".join(self.full_output))