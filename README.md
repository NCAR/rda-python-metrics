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

## Installing rda-python-common

For local development, clone this repo alongside your project and install it
in editable mode so that changes are picked up without re-installing:

```bash
git clone https://github.com/NCAR/rda-python-common.git
cd rda-python-common
pip install -e .
```

For a regular (non-editable) install from a checkout:

```bash
pip install /path/to/rda-python-common
```

For a production install on a system that uses the published distribution:

```bash
pip install rda_python_common
```

The package brings in its own transitive dependencies (`psycopg2-binary`,
`rda-python-globus`, `unidecode`, `hvac`).

## Setuid Setup

`logarch` runs as the common user `gdexdata` via the `rda_python_setuid`
mechanism.  `rda_python_setuid` is declared as a dependency and installed
automatically with this package.

### Environment setup

#### Option A — Python venv (DECS machines)

```bash
python3 -m venv $ENVHOME          # e.g. /glade/u/home/gdexdata/gdexmsenv
source $ENVHOME/bin/activate
pip install rda_python_metrics
```

#### Option B — Conda (DAV/Casper)

```bash
conda activate pg-gdex            # e.g. /glade/work/gdexdata/conda-envs/pg-gdex
pip install rda_python_metrics
```

### Full setuid install (requires sudo access to gdexdata)

Run these steps once per environment after `pip install`:

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

After `pip install`, run `metrics-setup` at any time to display the setup guide:

```bash
metrics-setup
```

The guide is also shown automatically if `setuid_logarch` is invoked directly
before the setuid wrapper has been configured.
