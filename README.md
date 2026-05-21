# rda_python_metrics

RDA Python package to gather and view data usage metrics for the
[NSF NCAR Geoscience Data Exchange (GDEX)](https://gdex.ucar.edu).

## Programs

The package provides two categories of programs:

**Run as gdexdata via setuid (requires setup below):**

| Command | Connector script | Description |
|---------|-----------------|-------------|
| `logarch` | `setuid_logarch` | Archive RDA log files (web, TDS, AWS, OSDF, dssdb) to the DECSDATA area |

**Run as current user (no setuid required):**

| Command | Description |
|---------|-------------|
| `fillawsusage` | Fill AWS usage metrics into the database |
| `fillcdgusage` | Fill CDG usage metrics into the database |
| `fillcodusage` | Fill COD usage metrics into the database |
| `fillcountry` | Fill country information into the database |
| `fillendtime` | Fill end times for usage records |
| `fillgdexusage` | Fill GDEX usage metrics into the database |
| `fillglobususage` | Fill Globus transfer usage metrics into the database |
| `fillipinfo` | Fill IP geolocation info into the database |
| `filloneorder` | Fill metrics for a single order |
| `fillosdfusage` | Fill OSDF usage metrics into the database |
| `fillrdadb` | Fill RDA database usage metrics |
| `filltdsusage` | Fill TDS (THREDDS) usage metrics into the database |
| `filluser` | Fill user information into the database |
| `fillzenodousage` | Fill Zenodo usage metrics into the database |
| `pgperson` | Retrieve user info from the UCAR People API by field |
| `pgusername` | Retrieve user info from the UCAR People API by username |
| `viewallusage` | View combined usage statistics |
| `viewawsusage` | View AWS usage statistics |
| `viewcheckusage` | View usage check results |
| `viewcodusage` | View COD usage statistics |
| `viewordusage` | View order usage statistics |
| `viewosdfusage` | View OSDF usage statistics |
| `viewrqstusage` | View request usage statistics |
| `viewtdsusage` | View TDS usage statistics |
| `viewwebfile` | View web file access records |
| `viewwebusage` | View web usage statistics |

## Environment setup

Create a Python environment first; package installs in the next section run
inside whichever environment you activate here.

### Option A — Python venv (DECS machines)

```bash
python3 -m venv $ENVHOME          # e.g. /glade/u/home/gdexdata/gdexmsenv
source $ENVHOME/bin/activate
```

### Option B — Conda (DAV/Casper)

```bash
conda create -n pg-gdex python=3.12
conda activate pg-gdex            # e.g. /glade/work/gdexdata/conda-envs/pg-gdex
```

## Installing rda-python-metrics

Pick whichever install mode fits your workflow.  All three pull in the
transitive dependencies (`rda_python_common`, `rda_python_setuid`, `geoip2`,
`ipinfo`, `httplib2`, `dnspython`, `unidecode`, `urllib3>=2.5.0`,
`requests>=2.33.0`, `idna>=3.10`) automatically.

For local development, clone this repo alongside your project and install it
in editable mode so that changes are picked up without re-installing:

```bash
git clone https://github.com/NCAR/rda-python-metrics.git
cd rda-python-metrics
pip install -e .
```

To test a specific branch (e.g. an in-progress feature or fix branch), pass
`-b/--branch` to `git clone`:

```bash
git clone -b <branch-name> https://github.com/NCAR/rda-python-metrics.git
cd rda-python-metrics
pip install -e .
```

For a regular (non-editable) install from a checkout:

```bash
pip install /path/to/rda-python-metrics
```

For a production install on a system that uses the published distribution:

```bash
pip install rda_python_metrics
```

## Setuid Setup

`logarch` runs as the common user `gdexdata` via the `rda_python_setuid`
mechanism, which is pulled in automatically as a dependency.  After
`pip install` above, choose one of the wiring options below.

### Full setuid install (requires sudo access to gdexdata)

Run these steps once per environment:

```bash
# Compile the pywrapper C binary (once per environment):
pywrapper-install -c|--compile -n|--username gdexdata

# Wire up logarch as a setuid entry (or use 'all' to link every setuid_* at once):
pywrapper-install -l|--link logarch
pywrapper-install -l|--link all
```

`pywrapper-install` with no arguments displays the full user guide.

### Simple install (no sudo required, runs as current user)

Users who do not need the setuid mechanism can create a direct symlink instead:

```bash
pywrapper-install -l|--link logarch -s|--simple
pywrapper-install -l|--link all -s|--simple   # or link every setuid_* at once
```

This creates `bin/logarch -> bin/setuid_logarch` and logarch runs as the
current user with no privilege change.

### Update an existing installation (no sudo required)

When the package is upgraded and a new `pywrapper.c` is bundled, recompile and
reinstall all setuid binaries using the existing `pgstart_*` binaries:

```bash
pywrapper-install -u|--update
```

### Setup guide

The shared setuid setup guide is shown automatically if `setuid_logarch` is
invoked directly before the setuid wrapper has been configured.
