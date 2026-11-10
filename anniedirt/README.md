# anniedirt stage

Propagates each GENIE event's final-state particles from the interaction point to the tank with Geant4
([ANNIEsoft/anniedirt](https://github.com/ANNIEsoft/anniedirt), g4dirt image). One job per GENIE file.

**Inputs**: `gntp.N.ghep.root` (default: the GENIE stage's persistent `genie/ghep`), the same `annie_v07.gdml`,
and the GDML schema files (`common/geometry/gdml_schema.tar.gz`).

**Worker** (`worker/anniedirt_job.sh` → `anniedirt_container.sh`): runs the same command as the image's
`/home/run_g4dirt.sh` (`g4annie_dirt_flux --batch -n 20000 --physics=FTFP_BERT_HP`), plus a seed macro
(`/random/setSeeds`). `run_g4dirt.sh` never seeds Geant4, so old productions used the engine's default sequence
in every job.

Expect about 1300–1400 events per file for world v07 (about 600 with the older, larger geometry), or about 20 000
for tank samples.

**Outputs** (always kept)

| File | Persistent dir |
|---|---|
| `annie_tank_flux.N.root` | `anniedirt/annie` |
| `annie_tank_flux.N.log.gz`, manifests | `anniedirt/logs` |
