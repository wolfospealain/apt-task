#!/usr/bin/python3
# wolfospealain, May 2018.
# https://github.com/wolfospealain/apt-task

import argparse
import sys
import os
import subprocess

version = "1.0"
install_path = "/usr/local/bin"


class Package:
    """
    Stores package data and gets depends.
    """

    def __init__(self, name, sections=[], tasks=[], installed=False, metapackage=False, size=0):
        self.name = name
        self.sections = set(sections)
        self.tasks = set(tasks)
        self.installed = installed
        self.metapackage = metapackage
        self.size = size

    def in_task(self, search):
        for task in self.tasks:
            if search in task:
                return True
        return False

    def depends(self, installed_only=False):
        apt_cache_depends_command = ["apt-cache", "depends", "--implicit", self.name]
        packages = set()
        if installed_only:
            apt_cache_depends_command += ["--installed"]
        try:
            output = subprocess.check_output(apt_cache_depends_command).decode("utf-8").splitlines()
        except:
            print("Error running \"" + ' '.join(apt_cache_depends_command) + "\"\n")
            exit(1)
        for line in output[1:]:
            if line[0] == " " and line[2] != " " and "<" not in line:
                packages.update([line.split()[1].split(":")[0]])
        return sorted(packages)


class Task:
    """
    Stores task packages, installed and available.
    """

    def __init__(self, name, packages=set(), installed=set()):
        self.name = name
        self.packages = packages
        self.installed = installed


class Apt:

    _prefix = "ubuntu-"

    def __init__(self):
        self.packages_db = self._apt_cache()
        self.metapackages = self._metapackages()
        self.installed_metapackages = self._metapackages(installed_only=True)
        self.installed_metapackages_db = {}
        for metapackage in self.installed_metapackages:
            self.installed_metapackages_db[metapackage] = Task(metapackage, self._metapackage_packages(metapackage), self._metapackage_packages(metapackage, installed_only=True))
        self.tasks = self._tasks()
        self.tasks_db = {}
        for task in self.tasks:
                self.tasks_db[task] = Task(task, self._task_packages(task), self._task_packages(task, installed_only=True))
        self.installed_tasks = self._tasks(installed_only=True)

    def _apt_cache(self):
        """
        Return package database parsed from apt-cache results.
        """
        dpkg_command = ["dpkg-query", "-W", "-f", "${Package} "]
        apt_cache_command = ["apt-cache", "show", "."]
        try:
            installed = sorted(list(set(subprocess.check_output(dpkg_command).decode("utf-8").split())))
        except:
            print("Error running \"" + ' '.join(dpkg_command) + "\"\n")
            exit(1)
        try:
            text = subprocess.check_output(apt_cache_command).decode("utf-8")
        except:
            print("Error running \"" + ' '.join(apt_cache_command) + "\"\n")
            exit(1)
        db = {}
        package = ""
        for line in text.splitlines():
            if line[:8] == "Package:":
                package = line.split()[1]
                if package not in db:
                    db[package] = Package(package, installed=package in installed)
            if line[:15] == "Installed-Size:":
                db[package].size = int(line[16:])
            if line[:5] == "Task:":
                db[package].tasks.update(line[6:].split(", "))
            if line[:8] == "Section:" and "metapackage" in line:
                db[package].metapackage = True
        return db

    def _tasks(self, installed_only=False):
        """
        List tasks, all available or installed only.
        """
        tasks = set()
        if not installed_only:
            for item in self.packages_db:
                tasks.update(self.packages_db[item].tasks)
        else:
            for task in self.tasks:
                status = self.task_status(task)
                if status[0]:
                    tasks.update([task])
        return sorted(tasks)

    def _task_packages(self, task, installed_only=False):
        """
        List task packages, all available or installed only.
        """
        packages = set()
        for item in self.packages_db:
            if not installed_only or self.packages_db[item].installed:
                if task in self.packages_db[item].tasks or (task == None and self.packages_db[item].tasks == set()):
                    packages.update([self.packages_db[item].name])
        return sorted(packages)

    def size(self, packages):
        """
        Return the combined installed size (kilobytes) of a list of pacakges.
        """
        kilobytes = 0
        for package in packages:
            kilobytes += self.packages_db[package].size
        return kilobytes

    def outside_packages(self):
        """
        List installed packages not in a task or metapackage.
        """
        taskless = set(self._task_packages(None, installed_only=True))
        depends = set()
        for package in self.installed_metapackages:
            depends.update(self.packages_db[package].depends())
        metapackagesless = set()
        for item in self.packages_db:
            if self.packages_db[item].installed and item not in depends:
                metapackagesless.update([item])
        return sorted(taskless & metapackagesless)

    def task_status(self, task):
        """
        Return task status, percentage of packages installed, and list of any extra packages from equivalent metapackage.
        """
        metapackage = self.equivalent_metapackage(task)
        metapackage_installed = False
        if metapackage:
            if self.packages_db[metapackage].installed:
                metapackage_installed = True
        percentage = len(self.tasks_db[task].installed) / len(self.tasks_db[task].packages) * 100
        if percentage == 100 or metapackage_installed:
            task_installed = True
        elif metapackage:
            task_installed = False
        else:
            task_installed = None
        if metapackage_installed:
            task_contents = set(self._task_packages(task, installed_only=True))
            metapackage_contents = set(self.installed_metapackages_db[metapackage].installed)
            return [task_installed, percentage, metapackage_contents - task_contents]
        else:
            return [task_installed, percentage]

    def metapackage_status(self, metapackage):
        """
        Return install status, percentage of packages installed, and list of any extra packages from equivalent task.
        """
        depends = self.packages_db[metapackage].depends()
        installed_depends = 0
        for package in depends:
            if package in self.packages_db:
                if self.packages_db[package].installed:
                    installed_depends += 1
        percentage = installed_depends / len(depends) * 100
        if metapackage in self.tasks:
            task = metapackage
        elif metapackage[:7]==self._prefix and metapackage[7:] in self.tasks:
            task = metapackage[7:]
        else:
            task = False
        if task:
            return [self.packages_db[metapackage].installed, percentage,
                    set(self.tasks_db[task].installed) - set(self.installed_metapackages_db[metapackage].installed)]
        else:
            return [self.packages_db[metapackage].installed, percentage]

    def _metapackages(self, installed_only=False):
        """
        List metapackages, all available or installed only.
        """
        metapackages = set()
        for item in self.packages_db:
            if not installed_only or self.packages_db[item].installed:
                if self.packages_db[item].metapackage:
                    metapackages.update([item])
        return sorted(metapackages)

    def _metapackage_packages(self, metapackage, installed_only=False):
        """
        List metapackage packages, all available or installed only.
        """
        return self.packages_db[metapackage].depends(installed_only)

    def equivalent_metapackage(self, task):
        """
        Return metapackage equivalent name for task.
        """
        if self._prefix+task in self.metapackages:
            return self._prefix+task
        elif task in self.metapackages:
            return task
        else:
            return None

    def show(self, task):
        """
        Show installed packages for task and/or metapackage, available packages, and overlapping packages.
        """
        metapackage = self.equivalent_metapackage(task)
        installed_packages = self.installed_packages(task)

        if metapackage in self.metapackages and task in self.tasks:
            metapackage_packages = self.task_status(task)[2]
            task_packages = self.metapackage_status(metapackage)[2]
            common_packages = sorted(set(installed_packages) - (set(task_packages) | set(metapackage_packages)))
            print(task, "task installed:", " ".join(task_packages), "\n")
            print(metapackage, "metapackage installed:", " ".join(metapackage_packages), "\n")
            print("common installed:", " ".join(common_packages), "\n")
        else:
            print(task, "installed: ", " ".join(installed_packages), "\n")
        print("available:", " ".join(self.installable(task)), "\n")
        overlaps = self.overlapping(task)
        print("overlapping:\n")
        for other_task in sorted(overlaps):
            overlapping = sorted(overlaps[other_task])
            if overlapping:
                print(other_task + ":", " ".join(overlapping))

    def overlapping(self, task):
        """
        Return database of other tasks and overlapping packages.
        """
        packages = set(self.installed_packages(task))
        overlaps = {}
        for other_task in self.installed_tasks:
                if other_task != task:
                    overlaps[other_task] = set(self.tasks_db[other_task].installed) & packages
        metapackage = self.equivalent_metapackage(task)
        for other_metapackage in self.installed_metapackages:
            if other_metapackage != metapackage:
                if other_metapackage not in overlaps:
                    overlaps[other_metapackage] = set()
                overlaps[other_metapackage].update(set(self.installed_metapackages_db[other_metapackage].installed) & packages)
                overlaps[other_metapackage].update([metapackage])
        return overlaps

    def installed_packages(self, task):
        """
        Return a list of installed packages for task and/or metapackage.
        """
        installed = set()
        if task in self.installed_tasks:
            installed.update(set(self.tasks_db[task].installed))
        if self._prefix+task in self.installed_metapackages:
            task = self._prefix+task
        if task in self.installed_metapackages:
            installed.update(set(self.installed_metapackages_db[task].installed))
            installed.update([task])
        return sorted(installed)

    def removable(self, task):
        """
        Return packages safely removable from task and/or metapackage without disturbing other tasks and metapackages.
        """
        if not task:
            return sorted(set(self.outside_packages()))
        elif task in self.installed_tasks or task in self.installed_metapackages \
                or self._prefix in self.installed_metapackages():
            packages = set(self.installed_packages(task))
            overlaps = self.overlapping(task)
            for other_task in overlaps:
                packages -= overlaps[other_task]
            return sorted(packages)
        else:
            return

    def remove(self, task):
        """
        Return apt remove command text.
        """
        apt_command = "sudo apt remove"
        if task and task not in self.installed_tasks and task not in self.installed_metapackages:
            return "# " + task + " is not installed."
        else:
            packages = set(self.removable(task))
            if packages == set():
                return "# No " + task + " packages to safely remove."
            else:
                return apt_command + " " + " ".join(sorted(packages))

    def installable(self, task):
        """
        Return packages installable for tasks and/or metapackage.
        """
        packages = set()
        if task in self.tasks:
            packages.update(self._task_packages(task))
        if self._prefix+task in self.metapackages:
            task = self._prefix+task
        if task in self.metapackages:
            if task in self.installed_metapackages_db:
                packages.update(self.installed_metapackages_db[task].packages)
            else:
                packages.update(self.packages_db[task].depends(installed_only=True))
            packages.update([task])
        else:
            return
        needed = set()
        for package in packages:
            if not self.packages_db[package].installed:
                needed.update([package])
        return sorted(needed)

    def install(self, task):
        """
        Return apt install command text.
        """
        apt_command = "sudo apt install"
        if task not in self.tasks and task not in self.metapackages:
            return "# " + task + " is not available."
        else:
            packages = set(self.installable(task))
            if packages == set():
                return "# No packages for " + task + " available."
            else:
                return apt_command + " " + " ".join(sorted(packages))

    def report(self):
        """
        Print on task/metapackage installation statistics.
        """
        combined = set(self.installed_tasks) | set(self.installed_metapackages)
        skip = set()
        print(" task  |  meta   name packages (% overlap) unique/installed")
        print("       |  ")
        total_size = 0
        total_packages = 0
        for task in sorted(combined):
            if task not in skip:
                installed_size = 0
                installed_packages = 0
                if self._prefix + task in self.installed_metapackages:
                    metapackage = self._prefix + task
                    skip.update([metapackage])
                else:
                    metapackage = task
                if task in self.installed_tasks:
                    print((str(round(self.task_status(task)[1]-.05,1)) + "%").rjust(6), sep="", end="")
                    installed_size += self.size(set(self.tasks_db[task].installed))
                    installed_packages += len(set(self.tasks_db[task].installed))
                else:
                    print("   -  ", end="")
                if metapackage in self.installed_metapackages:
                    print(" | ", (str(round(self.metapackage_status(metapackage)[1]-.05,1)) + "%").rjust(6), sep="", end="")
                    installed_size += self.size(set(self.installed_metapackages_db[metapackage].installed))
                    installed_packages += len(set(self.installed_metapackages_db[metapackage].installed))
                else:
                    print(" |    -  ", sep="", end="")
                if task != metapackage:
                    print("  " + task + "/" + metapackage, end="")
                else:
                    print("  " + task, sep="", end="")
                print("", installed_packages, end="")
                overlaps = self.overlapping(task)
                overlapping_packages = 0
                biggest_overlap = ""
                for other_task in sorted(overlaps):
                    length = len(overlaps[other_task])
                    if length > overlapping_packages:
                        overlapping_packages = length
                        biggest_overlap = other_task
                if overlapping_packages > 0:
                    print(" (" + str(round(overlapping_packages / len(self.installed_packages(task)) * 100,
                                           1)) + "% in " + biggest_overlap + ")", end="")
                print(" " + human(self.size(self.removable(task)) * 1024) + "/" + human(installed_size * 1024))
                total_size += installed_size
                total_packages += installed_packages
        print("\n                 total:", total_packages, "packages", human(total_size * 1024))
        outsiders = apt.outside_packages()
        print("                 outside:", len(outsiders), "packages", human(self.size(outsiders) * 1024), "\n")


def human(num, suffix='B'):
    """
    Fred Cirera, 2007
    https://web.archive.org/web/20111010015624/http://blogmag.net/blog/read/38/Print_human_readable_file_size
    """
    for unit in ['','Ki','Mi','Gi','Ti','Pi','Ei','Zi']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)


def install(target=install_path):
    """
    Install to target path and set executable permission.
    """
    if os.path.isdir(target):
        try:
            subprocess.check_output(["cp", "apt-task.py", target + "/apt-task"]).decode("utf-8")
            subprocess.check_output(["chmod", "a+x", target + "/apt-task"]).decode("utf-8")
            print("Installed to " + target + " as apt-task.")
        except:
            print("Not installed.")
            if os.getuid() != 0:
                print("Is sudo required?")
            return False
    else:
        print(target, "is not a directory.")
        return False


def parse_command_line():
    description = "%(prog)s version " + version + ". " \
                  + "Safely remove and install Ubuntu Linux task and/or metapackage packages."
    parser = argparse.ArgumentParser(description=description, epilog="")
    if ".py" in sys.argv[0]:
        parser.add_argument("--setup", action="store_true", dest="setup",
                            help="install to Linux destination path (default: " + install_path + ")")
        parser.add_argument("path", nargs="?", action="store", type=str, default=install_path,
                            help="optional destination for --setup option (default: " + install_path + ")")
    parser.add_argument("-v", "--version", action="version", version="%(prog)s " + version,
                            help="display version and exit")
    parser.add_argument("-i", "--install", action="store_true", dest="install",
                        help="install/complete installation of task and/or metapackage packages")
    parser.add_argument("-r", "--remove", action="store_true", dest="remove",
                        help="safely remove task and/or metapackage packages")
    parser.add_argument("-l", "--list", action="store_true", dest="list",
                        help="list installed tasks and metapackages")
    parser.add_argument("--outsiders", action="store_true", dest="outsiders",
                        help="caution: remove packages not in metapackages or tasks")
    parser.add_argument("-s", "--show", action="store_true", dest="show",
                        help="show task and/or metapackage packages installed, available, and overlapping.")
    parser.add_argument("-a", "--available", action="store_true", dest="available",
                        help="list all available tasks and metapackages")
    parser.add_argument("-R", "--report", action="store_true", dest="report",
                        help="default: report on installed tasks and metapackages")
    parser.add_argument("task", nargs="?", action="store", type=str,
                        help="task or metapackage")
    args = parser.parse_args()
    return args


if __name__ == "__main__":
    args = parse_command_line()
    if ".py" in sys.argv[0]:
        if args.setup:
            install(args.path)
            exit(0)
    if (args.install or args.remove or args.show) and not args.task:
        print("\nMissing task parameter.\n")
        exit(2)
    print("\nParsing apt-cache ... ", end="")
    apt = Apt()
    print("\r                     \r", end="")
    if args.task and args.task not in apt.tasks and args.task not in apt.metapackages:
        print("Unknown task.\n")
        exit(1)
    if args.install:
        print(apt.install(args.task)+"\n")
    elif args.remove:
        print(apt.remove(args.task) + "\n")
    elif args.outsiders:
        print(apt.remove(None) + "\n")
    elif args.show:
        apt.show(args.task)
    elif args.list:
        print("tasks installed:", " ".join(apt.installed_tasks))
        print("metapackages installed:", " ".join(apt.installed_tasks), "\n")
    elif args.available:
        print("tasks available: ", " ".join(apt.tasks))
        print("metapackages available: ", " ".join(apt.metapackages), "\n")
    else:
        apt.report()
