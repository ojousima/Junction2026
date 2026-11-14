# data/audio

Audio for Edge Impulse training and testing. Only this README and the folder
structure are in git; the WAV files and raw downloads are git-ignored.

Fetch the public data (about 2.5 GB download, needs `ffmpeg`):

```bash
python3 tools/fetch_audio.py
```

All clips are converted to 16 kHz mono 16-bit WAV, the same format the UNO Q mic
pipeline uses. Raw downloads are cached in `raw/`, so re-runs only convert.
`--per-class N` changes the subset size and `--only <source>` fetches one source.

## Layout

```
data/audio/
  candas/        small DC cooling fans, magnets on blades (imbalance)
    training/normal/   balanced fan (config 1)
    testing/normal/    held-out balanced clips
    testing/anomaly/   configs 2..5, light to severe imbalance
  mimii_fan/     industrial fans with factory noise (DCASE 2020 Task 2)
    training/normal/  testing/normal/  testing/anomaly/
  rig/           OUR desk-fan recordings, same layout (record these on the UNO Q)
  heatpump_ref/  real air-to-water heat pump, healthy (RWTH listening test)
  noise/         outdoor background noise (ESC-50 subset)
  raw/           download cache
```

File names carry the source and the condition, for example
`candas_A3_9V_cfg5_abnormal_000123.wav` (fan A3, 9 V supply, imbalance config 5).

## How to use it

Anomaly detection only needs healthy sound. Train on `training/normal`, then check
that `testing/anomaly` scores higher than `testing/normal`. Keep one Edge Impulse
project per source: public fans validate the method, `rig/` is the model we deploy.

```bash
npm install -g edge-impulse-cli
edge-impulse-uploader --category training --label normal  data/audio/candas/training/normal/*.wav
edge-impulse-uploader --category testing  --label normal  data/audio/candas/testing/normal/*.wav
edge-impulse-uploader --category testing  --label anomaly data/audio/candas/testing/anomaly/*.wav
```

In Edge Impulse: audio MFE block, then a K-means or GMM anomaly block trained on
`normal` only. `heatpump_ref/` and `noise/` are for listening, the pitch, and
checking that background noise does not raise the anomaly score.

## Sources and licenses

| Folder | Source | License |
|---|---|---|
| `candas/` | [CANDAS](https://huggingface.co/datasets/IoTDataAtelier/CANDAS), Lima et al., ENIAC 2025, [doi:10.5753/eniac.2025.13864](https://doi.org/10.5753/eniac.2025.13864) | MIT |
| `mimii_fan/` | [DCASE 2020 Task 2 dev set](https://zenodo.org/records/3678171) (MIMII fan), Purohit et al., DCASE 2019 | CC BY-NC-SA 4.0 |
| `heatpump_ref/` | [Heat Pump Noise stimuli](https://zenodo.org/records/18619500), Stürenburg et al., Acta Acustica 2026, [doi:10.1051/aacus/2026016](https://doi.org/10.1051/aacus/2026016) | CC BY 4.0 |
| `noise/` | [ESC-50](https://github.com/karolpiczak/ESC-50), Piczak, ACM MM 2015 | CC BY-NC 3.0 |

MIMII and ESC-50 are non-commercial: fine for the hackathon, but do not
redistribute the audio or use it in a commercial product.
