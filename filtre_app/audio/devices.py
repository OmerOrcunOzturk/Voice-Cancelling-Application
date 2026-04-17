import sounddevice as sd


PREFERRED_VIRTUAL_OUTPUT_TERMS = ("cable input", "vb-cable", "virtual", "sanal")


def format_device_label(index, info):
    hostapi_name = sd.query_hostapis(info["hostapi"])["name"]
    return f"{index}: {info['name']} ({hostapi_name})"


def query_input_output_devices():
    all_devices = sd.query_devices()
    input_devices = []
    output_devices = []

    for index, info in enumerate(all_devices):
        if info["max_input_channels"] >= 1:
            input_devices.append((format_device_label(index, info), index, info))
        if info["max_output_channels"] >= 1:
            output_devices.append((format_device_label(index, info), index, info))

    return input_devices, output_devices


def pick_default_output(output_devices):
    for label, _, _ in output_devices:
        lowered = label.lower()
        if any(term in lowered for term in PREFERRED_VIRTUAL_OUTPUT_TERMS):
            return label

    return output_devices[0][0] if output_devices else ""


def find_selected_device(devices, selected_label):
    for label, index, info in devices:
        if label == selected_label:
            return index, info
    return None, None


def pick_supported_audio_config(input_device, input_info, output_device, output_info):
    output_channels = max(1, min(2, int(output_info["max_output_channels"] or 1)))
    candidate_rates = []

    for rate in (
        48000,
        int(input_info.get("default_samplerate") or 0),
        int(output_info.get("default_samplerate") or 0),
        44100,
    ):
        if rate and rate not in candidate_rates:
            candidate_rates.append(rate)

    for sample_rate in candidate_rates:
        try:
            sd.check_input_settings(
                device=input_device,
                channels=1,
                samplerate=sample_rate,
                dtype="float32",
            )
            sd.check_output_settings(
                device=output_device,
                channels=output_channels,
                samplerate=sample_rate,
                dtype="float32",
            )
            return sample_rate, output_channels
        except Exception:
            continue

    fallback_rate = int(input_info.get("default_samplerate") or output_info.get("default_samplerate") or 48000)
    return fallback_rate, output_channels
