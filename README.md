# Apt-Task
Safely remove and install Ubuntu Linux task and/or metapackage packages installed via apt or tasksel.

Metapackages and tasks are groups of packages easily installed via apt or tasksel commands (e.g. kubuntu-desktop, elementary-desktop, xubuntu-desktop, etc.). Given the overlap with other metapackages and tasks there is no safe way to remove metapackages and tasks from apt or tasksel without removing required packages and possibly breaking the installation.

Apt-Task is a Python script to report on installed metapackages and tasks, list installed packages and overlaps, install and repair incomplete metapackages and tasks, and safely remove metapackages and tasks. The Apt-Task safe remove option will only select packages that are not part of any other installed metapackage or task. 

Importantly, Apt-Task only generates the command text and will not make any changes to the system. It remains the responsibility of the sudo user to review, copy, paste, and edit the command as required. Caution is advised.

## Setup
```sudo python3 ./apt-task.py --setup```

## Usage

```
usage: apt-task.py [-h] [-v] [-i] [-r] [-l] [--remove-independent] [-s] [-a]
                   [-R] [-o] [--setup]
                   [task]

apt-task.py version 1.0. Safely remove and install Ubuntu Linux task and/or
metapackage packages.

positional arguments:
  task                  task or metapackage

optional arguments:
  -h, --help            show this help message and exit
  -v, --version         display version and exit
  -i, --install         install/complete installation of task and/or
                        metapackage packages
  -r, --remove          safely remove task and/or metapackage packages
  -l, --list            list installed tasks and metapackages
  --remove-independent  caution: remove packages not in metapackages or tasks
  -s, --show            show task and/or metapackage packages installed,
                        available, and overlapping.
  -a, --available       list all available tasks and metapackages
  -R, --report          default: report on installed tasks and metapackages
  -o, --report-orphans  report on orphan packages from not installed tasks or
                        metapackages
  --setup               install to Linux destination path (default:
                        /usr/local/bin)
```

## Use Cases

### Remove task or metapackage:
```apt-task -r kubuntu-desktop```

Effectively removing a metapackage or task may require removal of other overlapping metapackages or tasks first. Refer to the Apt-Task report or use the ```apt-task --show``` option for further metapackage or task information.

### Factory installation only:
Remove all but required metapackages and tasks, then remove remaining packages outside any installed metapackages or tasks (danger awaits):

```apt-task --outsiders```

### Complete/fix installation:
```apt-task -i ubuntu-desktop```
