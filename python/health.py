"""End-user health summary: four plain statuses computed on the device.

The homeowner does not need anomaly scores. They need to know, per part of the
heat pump, whether it is fine, worth watching, or needs action:

    coil        clean / getting dirty / clean it      (fouling tracker, state["coil"])
    fan         from the fault detector, when the reasons point at the fan
    compressor  from the fault detector, when the reasons point at the compressor
    defrost     frost risk from the Thermo + icing from the camera (state["icing"])

Each component gets a level ("ok", "watch", "alert", "unknown") and one sentence.
Only "alert" is pushed to the phone. Everything is decided here on the edge; the
cloud only stores and shows it.
"""
LEVELS = ["unknown", "ok", "watch", "alert"]

# Which part of the unit a detector feature points at
FAN_FEATURES = {"mod_air", "mod_air_peak_db", "mod_high", "mod_high_peak_db", "kurt_high", "crest",
                "flatness", "centroid_hz", "band_1600_3200_db", "band_3200_6400_db",
                "band_400_800_db", "band_800_1600_db"}
COMPRESSOR_FEATURES = {"comp_f0_hz", "comb_db", "inharm_db", "n_tones", "tone_prom_db", "tonality_db",
                       "band_30_100_db", "band_100_200_db", "band_200_400_db"}

TEXT = {
    "coil": {"ok": "Coil clean", "watch": "Coil getting dirty: plan a cleaning",
             "alert": "Clean the coil: it is costing you energy", "unknown": "Coil: learning"},
    "fan": {"ok": "Fan OK", "watch": "Fan sounds unusual: we are watching it",
            "alert": "Fan problem: check for ice, leaves or a loose part", "unknown": "Fan: learning"},
    "compressor": {"ok": "Compressor OK", "watch": "Compressor sounds unusual: we are watching it",
                   "alert": "Compressor problem: contact your installer", "unknown": "Compressor: learning"},
    "defrost": {"ok": "Defrost OK", "watch": "Frost weather: defrost is working hard",
                "alert": "Ice is building up on the coil: defrost may not be working",
                "unknown": "Defrost: no data"},
}


def _part(feature):
    if feature in FAN_FEATURES:
        return "fan"
    if feature in COMPRESSOR_FEATURES:
        return "compressor"
    return None


def _coil_level(coil):
    if not coil or coil.get("status") == "learning" or coil.get("cleanliness_pct") is None:
        return "unknown"
    pct = coil["cleanliness_pct"]
    if pct < coil.get("clean_pct", 50):
        return "alert"
    return "watch" if pct < coil.get("watch_pct", 70) else "ok"


def _sound_levels(det, mic_ok):
    """Fan and compressor levels from the fault detector and its reasons."""
    if not mic_ok or not det or det.get("mode") != "monitoring":
        return "unknown", "unknown"
    over = det.get("score") is not None and det.get("threshold") is not None and det["score"] > det["threshold"]
    if not over:
        return "ok", "ok"
    level = "alert" if det.get("alarm") else "watch"
    parts = [_part(r["feature"]) for r in det.get("reasons", [])]
    parts = [p for p in parts if p]
    if not parts:  # abnormal but unclear where: watch both, alert neither
        return "watch", "watch"
    top = parts[0]
    return (level if top == "fan" else ("watch" if "fan" in parts else "ok"),
            level if top == "compressor" else ("watch" if "compressor" in parts else "ok"))


def _defrost_level(temp_c, rh, icing):
    """Icing seen by the camera is the alert; frost weather alone is only 'watch'."""
    if icing is not None:
        if icing >= 0.6:
            return "alert"
        if icing >= 0.3:
            return "watch"
    if temp_c is None or rh is None:
        return "unknown" if icing is None else "ok"
    frost_weather = -10 <= temp_c <= 5 and rh >= 70
    return "watch" if frost_weather else "ok"


def summarize(state):
    """{"overall": level, "components": {name: {"level", "text"}}} from the app state."""
    fan, comp = _sound_levels(state.get("detector"), state.get("mic_ok"))
    levels = {
        "coil": _coil_level(state.get("coil")),
        "fan": fan,
        "compressor": comp,
        "defrost": _defrost_level(state.get("temp_c"), state.get("rh"), state.get("icing")),
    }
    known = [lv for lv in levels.values() if lv != "unknown"]
    overall = max(known, key=LEVELS.index) if known else "unknown"
    return {"overall": overall,
            "components": {k: {"level": lv, "text": TEXT[k][lv]} for k, lv in levels.items()}}
