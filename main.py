import sys
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QTextEdit, QPushButton, QSlider, QLabel, QHBoxLayout, QComboBox, QFileDialog
from PyQt5.QtCore import Qt, QTimer, QUrl, QTemporaryDir, QThread, pyqtSignal
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from openai import OpenAI
import os
import shutil

# Set OPENAI_API_KEY only if it's not already in the environment
if not os.getenv("OPENAI_API_KEY"):
    from dotenv import load_dotenv
    load_dotenv()

class GenerateAudioThread(QThread):
    audio_generated = pyqtSignal(str)  # Signal to send audio file path

    def __init__(self, client, text, temp_dir):
        super().__init__()
        self.client = client
        self.text = text
        self.temp_dir = temp_dir

    def run(self):
        try:
            response = self.client.audio.speech.create(
                model="tts-1",
                voice="alloy",
                input=self.text,
            )
            
            # Create a temporary file to save audio data
            audio_file_path = os.path.join(self.temp_dir.path(), "output.mp3")
            with open(audio_file_path, "wb") as audio_file:
                audio_file.write(response.content)

            # Emit signal with the audio file path once generation is complete
            self.audio_generated.emit(audio_file_path)
        except Exception as e:
            print(f"Error generating audio: {e}")
            self.audio_generated.emit("")

class TextToSpeechApp(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY is not set.")
        self.client = OpenAI(api_key=api_key)  # Initialize OpenAI client
        self.player = QMediaPlayer()  # Audio player
        self.default_speed = 1.0
        self.temp_dir = QTemporaryDir()  # Create temporary directory
        self.audio_thread = None

    def initUI(self):
        self.setWindowTitle("Text to Speech Player")
        self.setGeometry(100, 100, 500, 400)
        
        layout = QVBoxLayout()
        
        # Text input box
        self.text_input = QTextEdit()
        self.text_input.setPlaceholderText("Enter text (Shift+Enter for newline, Enter to submit)")
        layout.addWidget(self.text_input)

        # Submit button
        self.submit_button = QPushButton("Generate and Play Audio")
        self.submit_button.clicked.connect(self.start_audio_generation)
        layout.addWidget(self.submit_button)
        
        # Playback controls
        controls_layout = QHBoxLayout()
        
        self.play_button = QPushButton("Play")
        self.play_button.clicked.connect(self.play_audio)
        controls_layout.addWidget(self.play_button)
        
        self.pause_button = QPushButton("Pause")
        self.pause_button.clicked.connect(self.pause_audio)
        controls_layout.addWidget(self.pause_button)

        # Download button
        self.download_button = QPushButton("Download Audio")
        self.download_button.clicked.connect(self.download_audio)
        controls_layout.addWidget(self.download_button)

        layout.addLayout(controls_layout)

        # Progress slider
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.sliderMoved.connect(self.set_position)
        layout.addWidget(self.slider)

        # Playback speed selection
        speed_label = QLabel("Playback Speed:")
        layout.addWidget(speed_label)
        self.speed_combo = QComboBox()
        self.speed_combo.addItems(["0.5x", "1.0x", "1.5x", "2.0x"])
        self.speed_combo.setCurrentText("1.0x")  # Set default speed
        self.speed_combo.currentIndexChanged.connect(self.change_speed)
        layout.addWidget(self.speed_combo)

        # Set layout
        self.setLayout(layout)
        
        # Timer to update the progress slider
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.update_slider)

        # Connect keyboard event
        self.text_input.installEventFilter(self)

    def eventFilter(self, source, event):
        if event.type() == event.KeyPress and source is self.text_input:
            if event.key() == Qt.Key_Return and event.modifiers() == Qt.ShiftModifier:
                self.text_input.insertPlainText("\n")
                return True
            elif event.key() == Qt.Key_Return:
                self.start_audio_generation()
                return True
        return super().eventFilter(source, event)

    def start_audio_generation(self):
        text = self.text_input.toPlainText().strip()
        if text:
            # Disable button to prevent multiple clicks
            self.submit_button.setEnabled(False)
            # Start background thread for audio generation
            self.audio_thread = GenerateAudioThread(self.client, text, self.temp_dir)
            self.audio_thread.audio_generated.connect(self.on_audio_generated)
            self.audio_thread.start()

    def on_audio_generated(self, audio_file_path):
        # Enable button again
        self.submit_button.setEnabled(True)
        
        if audio_file_path:
            # Set media content for the player
            self.player.setMedia(QMediaContent(QUrl.fromLocalFile(audio_file_path)))
            self.play_audio()
            print("Audio has been generated and saved to a temporary file")
        else:
            print("Audio generation failed")

    def play_audio(self):
        self.player.setPlaybackRate(self.default_speed)
        self.player.play()
        self.timer.start()

    def pause_audio(self):
        self.player.pause()

    def set_position(self, position):
        self.player.setPosition(int(self.player.duration() * position / 100))

    def update_slider(self):
        if self.player.duration() > 0:
            self.slider.setValue(int(self.player.position() * 100 / self.player.duration()))

    def change_speed(self):
        speed_map = {"0.5x": 0.5, "1.0x": 1.0, "1.5x": 1.5, "2.0x": 2.0}
        speed = self.speed_combo.currentText()
        self.player.setPlaybackRate(speed_map[speed])

    def download_audio(self):
        audio_file_path = os.path.join(self.temp_dir.path(), "output.mp3")
        if os.path.exists(audio_file_path):
            file_name, _ = QFileDialog.getSaveFileName(self, "Save Audio", "", "MP3 Files (*.mp3)")
            if file_name:
                # Ensure the filename has .mp3 extension
                if not file_name.endswith(".mp3"):
                    file_name += ".mp3"
                shutil.copy(audio_file_path, file_name)
                print(f"Audio saved as {file_name}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TextToSpeechApp()
    window.show()
    sys.exit(app.exec_())
