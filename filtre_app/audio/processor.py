import queue
import threading

import numpy as np
import sounddevice as sd

from filtre_app.audio.filters import apply_spectral_noise_reduction
from filtre_app.config import DEFAULT_BLOCK_SIZE, DEFAULT_SAMPLE_RATE


class AudioProcessor:
    def __init__(self, sample_rate=DEFAULT_SAMPLE_RATE, block_size=DEFAULT_BLOCK_SIZE):
        self.sample_rate = sample_rate
        self.block_size = block_size
        self._stream = None
        self.lock = threading.Lock()

        self.input_gain = 1.0
        self.output_volume = 0.7
        self.noise_reduction = 0.35
        self.gate_threshold_db = -50.0
        self.monitoring_enabled = True

        self._noise_profile = np.zeros(block_size // 2 + 1, dtype=np.float32)
        self._last_level = 0.0
        self._last_peak = 0.0
        self._last_status = "Hazir"
        self._status_queue = queue.Queue()
        self._output_channels = 1

    def set_controls(self, input_gain, output_volume, noise_reduction, gate_threshold_db):
        with self.lock:
            self.input_gain = input_gain
            self.output_volume = output_volume
            self.noise_reduction = noise_reduction
            self.gate_threshold_db = gate_threshold_db

    def set_monitoring(self, enabled):
        with self.lock:
            self.monitoring_enabled = enabled

    def get_meter_state(self):
        with self.lock:
            return self._last_level, self._last_peak, self._last_status

    def drain_status_messages(self):
        messages = []
        while True:
            try:
                messages.append(self._status_queue.get_nowait())
            except queue.Empty:
                return messages

    def start(self, input_device=None, output_device=None, sample_rate=None, output_channels=1):
        if self._stream is not None:
            return

        try:
            if sample_rate is not None:
                self.sample_rate = int(sample_rate)
            self._output_channels = max(1, int(output_channels))

            # Tek duplex akis: Windows'ta ayri giris/cikis akislari saat kaymasiyla
            # kuyruk bos kalip surekli sessizlik uretebiliyor; giris ve cikis ayni callback'te eslenir.
            self._stream = sd.Stream(
                device=(input_device, output_device),
                samplerate=self.sample_rate,
                blocksize=self.block_size,
                dtype="float32",
                channels=(1, self._output_channels),
                callback=self._duplex_callback,
                latency="high",
                prime_output_buffers_using_stream_callback=True,
            )
            self._stream.start()
            self._push_status("Dinleme basladi")
        except Exception as exc:
            self._close_streams()
            raise RuntimeError(f"Ses akisi baslatilamadi: {exc}") from exc

    def stop(self):
        if self._stream is None:
            return

        self._close_streams()
        self._push_status("Dinleme durduruldu")

    def _close_streams(self):
        if self._stream is None:
            return
        try:
            self._stream.stop()
        except Exception:
            pass
        try:
            self._stream.close()
        except Exception:
            pass
        self._stream = None

    def _push_status(self, text):
        with self.lock:
            self._last_status = text
        self._status_queue.put(text)

    def _duplex_callback(self, indata, outdata, frames, time_info, status):
        if status:
            self._push_status(f"Ses uyarisi: {status}")

        frame = np.copy(indata[:, 0])
        if frames != self.block_size:
            frame = np.pad(frame, (0, max(0, self.block_size - frames)))
            frame = frame[: self.block_size]

        with self.lock:
            input_gain = self.input_gain
            output_volume = self.output_volume
            noise_reduction = self.noise_reduction
            gate_threshold_db = self.gate_threshold_db
            monitoring_enabled = self.monitoring_enabled
            output_ch = self._output_channels

        processed = frame * input_gain
        cleaned, noise_profile, rms, peak = apply_spectral_noise_reduction(
            processed=processed,
            noise_profile=self._noise_profile,
            noise_reduction=noise_reduction,
            gate_threshold_db=gate_threshold_db,
            block_size=self.block_size,
        )
        self._noise_profile = noise_profile
        cleaned = np.clip(cleaned * output_volume, -1.0, 1.0)

        with self.lock:
            self._last_level = min(1.0, rms * 3.0)
            self._last_peak = min(1.0, peak)

        output_mono = cleaned[:frames].astype(np.float32, copy=False)
        if not monitoring_enabled:
            output_mono = np.zeros(frames, dtype=np.float32)

        mono = output_mono.reshape(-1, 1)
        outdata[:] = np.repeat(mono, output_ch, axis=1)
