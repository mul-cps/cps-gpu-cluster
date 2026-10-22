# Same-policy A5/B10 MPS preparation

`prepare_mps.py` is inert by default. Offline preparation authenticates the frozen original MPS runner, engine, mapper and probe and the reviewed unequal producer before emitting a new sibling source bundle:

```sh
python prepare_mps.py --prepare --output /absolute/new-mps-sources
```

Run the generated `run_mps.py` with the original explicit manifest/raw hash, runner raw hash, independently reviewed Root mapper argv/raw hash, output directory and `--execute`. Only side A is supported: MPS remains the original 5120 MiB probe; the opposite ordinary peer uses the generated transport's actual 10240 MiB cap. The fresh protected host intents must both bind Source policy `332d14fb9e510b9810feffb8d40b408743f9679ebd13ca1ba0e1077d666e9281` before any CUDA dispatch. Original thresholds, process absence checks, cleanup and final observer proofs remain unchanged. This prepares source only and makes no hardware or production qualification claim. Original MPS source/evidence files remain untouched.
