import numpy as np


def update_noise_profile(noise_profile, magnitude, level_db, gate_threshold_db):
    if level_db < gate_threshold_db + 8:
        return 0.92 * noise_profile + 0.08 * magnitude

    return 0.995 * noise_profile + 0.005 * magnitude


def apply_spectral_noise_reduction(
    processed,
    noise_profile,
    noise_reduction,
    gate_threshold_db,
    block_size,
):
    rms = float(np.sqrt(np.mean(processed**2) + 1e-12))
    peak = float(np.max(np.abs(processed)) + 1e-12)
    level_db = 20 * np.log10(rms + 1e-12)

    spectrum = np.fft.rfft(processed)
    magnitude = np.abs(spectrum)
    phase = np.angle(spectrum)

    updated_profile = update_noise_profile(
        noise_profile=noise_profile,
        magnitude=magnitude,
        level_db=level_db,
        gate_threshold_db=gate_threshold_db,
    )

    cleaned_magnitude = np.maximum(
        magnitude - (updated_profile * (0.15 + noise_reduction * 1.85)),
        0.0,
    )
    cleaned = np.fft.irfft(cleaned_magnitude * np.exp(1j * phase), n=block_size)

    gate_linear = 10 ** (gate_threshold_db / 20.0)
    if rms < gate_linear:
        attenuation = max(0.03, rms / (gate_linear + 1e-12))
        cleaned *= attenuation

    return cleaned, updated_profile, rms, peak
