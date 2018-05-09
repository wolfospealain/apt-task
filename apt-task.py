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
    Stores package data: tasks, metapackages, depends, installation, size.
    """

    def __init__(self, name, sections=[], tasks=[], installed=False, metapackage=False, size=0):
        self.name = name
        self.sections = set(sections)
        self.tasks = set(tasks)
        self.installed = installed
        self.metapackage = metapackage
        self.size = size
        self.depends = set()

    def in_task(self, search):
        for task in self.tasks:
            if search in task:
                return True
        return False


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
            elif line[:15] == "Installed-Size:":
                db[package].size = int(line[16:])
            elif line[:5] == "Task:":
                db[package].tasks.update(line[6:].split(", "))
            elif line[:8] == "Section:" and "metapackage" in line:
                db[package].metapackage = True
            elif line[:8] == "Depends:":
                for depend in line[9:].split(", "):
                    name = depend.split(" (")[0]
                    db[package].depends.update([name])
            elif line[:9] == "Suggests:":
                db[package].depends.update(line[10:].split(", "))
            elif line[:11] == "Recommends:":
                db[package].depends.update(line[12:].split(", "))
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
        if metapackage in self.metapackages:
            task_contents = set(self.tasks_db[task].installed)
            metapackage_contents = set(self.metapackage_packages(metapackage, installed_only=True))
            return [task_installed, percentage, metapackage_contents - task_contents]
        else:
            return [task_installed, percentage]

    def metapackage_status(self, metapackage):
        """
        Return install status, percentage of packages installed, and list of any extra packages from equivalent task.
        """
        depends = self.metapackage_packages(metapackage)
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
                    set(self.tasks_db[task].installed) - set(self.metapackage_packages(metapackage, installed_only=True))]
        else:
            return [self.packages_db[metapackage].installed, percentage]

    def _metapackages(self, installed_only=False):
        """
        List metapackages, all available or installed only.
        """
        metapackages = set()
        for item in self.packages_db:
            if (not installed_only or self.packages_db[item].installed) and self.packages_db[item].metapackage:
                metapackages.update([item])
        return sorted(metapackages)

    def metapackage_packages(self, metapackage, installed_only=False):
        """
        List metapackage packages, all available or installed only.
        """
        if installed_only:
            installed = set()
            for package in self.packages_db[metapackage].depends:
                if package in self.packages_db:
                    if self.packages_db[package].installed:
                        installed.update([package])
            return sorted(installed)
        else:
            return sorted(self.packages_db[metapackage].depends)

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
        task_label = ("task orphans installed" if task not in self.installed_tasks else "task installed")
        metapackage_label = ("metapackage orphans installed" if metapackage not in self.installed_metapackages else "metapackages installed")
        label = ("orphans installed" if task not in self.installed_tasks and metapackage not in self.installed_metapackages else "installed")
        if metapackage in self.metapackages and task in self.tasks:
            common_packages = set(installed_packages)
            task_packages = self.metapackage_status(metapackage)[2]
            print(task, task_label + ":\n" + " ".join(task_packages), "\n")
            common_packages.difference_update(task_packages)
            metapackage_packages = self.task_status(task)[2]
            print(metapackage, metapackage_label + ":\n" + " ".join(metapackage_packages), "\n")
            common_packages.difference_update(metapackage_packages)
            print(task, "task/metapackage " + label + ":\n" + " ".join(common_packages), "\n")
        else:
            print(task, label + ":\n" + " ".join(installed_packages), "\n")
        print("removable:\n" + " ".join(self.removable(task)), "\n")
        print("available:\n" + " ".join(self.installable(task)), "\n")
        overlaps = self.overlapping(task)
        for other_task in sorted(overlaps):
            overlapping = sorted(overlaps[other_task])
            if overlapping:
                print("overlapping", other_task + ":\n" + " ".join(overlapping) + "\n")

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
                overlaps[other_metapackage].update(set(self.metapackage_packages(other_metapackage, installed_only=True)) & packages)
        return overlaps

    def installed_packages(self, task=None):
        """
        List of all installed packages or for task and/or metapackage.
        """
        installed = set()
        if task:
            if task in self.tasks:
                installed.update(set(self.tasks_db[task].installed))
            metapackage = self.equivalent_metapackage(task)
            if metapackage in self.metapackages:
                installed.update(set(self.metapackage_packages(metapackage, installed_only=True)))
                if metapackage in self.installed_metapackages:
                    installed.update([metapackage])
        else:
            for package in self.packages_db:
                if self.packages_db[package].installed:
                    installed.update([package])
        return sorted(installed)

    def installed_child_packages(self):
        """
        List installed child packages or installed tasks and/or metapackages.
        """
        children = set()
        for metapackage in self.installed_metapackages:
            children.update(self.metapackage_packages(metapackage, installed_only=True))
        for task in self.installed_tasks:
            children.update(self.tasks_db[task].installed)
        return sorted(children)

    def installed_orphan_packages(self):
        """
        List installed packages not in an installed task or metapackage.
        """
        children = set()
        for metapackage in self.metapackages:
            children.update(self.metapackage_packages(metapackage, installed_only=True))
        for task in self.tasks:
            children.update(self.tasks_db[task].installed)
        children.difference_update(self.installed_child_packages())
        return sorted(children)

    def installed_independent_packages(self):
        """
        List installed packages not in any task or metapackage.
        """
        packages = (set(self.installed_packages()) - set(self.installed_child_packages())) - set(self.installed_orphan_packages())
        return sorted(packages)

    def removable(self, task):
        """
        Return packages safely removable from task and/or metapackage without disturbing other tasks and metapackages.
        """
        if not task:
            return sorted(set(self.installed_independent_packages()))
        else:
            packages = set(self.installed_packages(task))
            overlaps = self.overlapping(task)
            for other_task in overlaps:
                packages -= overlaps[other_task]
            return sorted(packages)

    def remove(self, task):
        """
        Return apt remove command text.
        """
        apt_command = "sudo apt remove"
        comment = ""
        if task and task not in self.installed_tasks and task not in self.installed_metapackages:
            comment = "# Note: " + task + " is not installed."
        if task and task not in self.tasks and task not in self.metapackages:
            return "# " + task + " is not available."
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
            packages.update(self.tasks_db[task].packages)
        if self._prefix+task in self.metapackages:
            task = self._prefix+task
        if task in self.metapackages:
            packages.update(self.metapackage_packages(task, installed_only=True))
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

    def report(self, orphans=False):
        """
        Print on task/metapackage installation statistics.
        """
        installed = set(self.installed_tasks) | set(self.installed_metapackages)
        if orphans:
            combined = (set(self.tasks) | set(self.metapackages)) - installed
        else:
            combined = installed
        skip = set()
        print(" task | meta  name packages (% overlap) removable/installed")
        print("      |  ")
        for task in sorted(combined):
            if task not in skip:
                removable = self.size(self.removable(task))
                if (removable > 0 and orphans and task not in installed) or (not orphans and task in installed):
                    packages = set()
                    if self._prefix + task in self.installed_metapackages:
                        metapackage = self._prefix + task
                        skip.update([metapackage])
                    else:
                        metapackage = task
                    if task in self.tasks:
                        percentage = self.task_status(task)[1]
                        symbol = ("<" if percentage < 100 and percentage >= 99.5 else " ")
                        print((symbol + str(round(percentage)) + "%").rjust(5), sep="", end="")
                        packages.update(self.tasks_db[task].installed)
                    else:
                        print("   - ", end="")
                    if metapackage in self.metapackages:
                        percentage = self.metapackage_status(metapackage)[1]
                        symbol = ("<" if percentage < 100 and percentage >= 99.5 else " ")
                        print(" |", (symbol + str(round(percentage)) + "%").rjust(5), sep="", end="")
                        packages.update(self.metapackage_packages(metapackage, installed_only=True))
                    else:
                        print(" |   - ", sep="", end="")
                    if task != metapackage:
                        print("  " + task + "/" + metapackage, end="")
                    else:
                        print("  " + task, sep="", end="")
                    print("", len(packages), end="")
                    overlaps = self.overlapping(task)
                    overlapping_packages = 0
                    biggest_overlap = ""
                    for other_task in sorted(overlaps):
                        length = len(overlaps[other_task])
                        if length > overlapping_packages:
                            overlapping_packages = length
                            biggest_overlap = other_task
                    if overlapping_packages > 0:
                        print(" (" + str(round(overlapping_packages / len(self.installed_packages(task)) * 100)) + "% in " + biggest_overlap + ")", end="")
                    print(" " + human(removable * 1024) + "/" + human(self.size(packages) * 1024))

        installed = apt.installed_packages()
        children = apt.installed_child_packages()
        orphans = apt.installed_orphan_packages()
        independent = apt.installed_independent_packages()
        print()
        print("              installed packages:", len(installed), "packages", human(self.size(installed) * 1024))
        print()
        print("              child packages:", len(children), "packages", human(self.size(children) * 1024))
        print("              orphan packages:", len(orphans), "packages", human(self.size(orphans) * 1024))
        print("              independent packages:", len(independent), "packages", human(self.size(independent) * 1024))
        print()


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
    parser.add_argument("-v", "--version", action="version", version="%(prog)s " + version,
                            help="display version and exit")
    parser.add_argument("-i", "--install", action="store_true", dest="install",
                        help="install/complete installation of task and/or metapackage packages")
    parser.add_argument("-r", "--remove", action="store_true", dest="remove",
                        help="safely remove task and/or metapackage packages")
    parser.add_argument("-l", "--list", action="store_true", dest="list",
                        help="list installed tasks and metapackages")
    parser.add_argument("--remove-independent", action="store_true", dest="independent",
                        help="caution: remove packages not in metapackages or tasks")
    parser.add_argument("-s", "--show", action="store_true", dest="show",
                        help="show task and/or metapackage packages installed, available, and overlapping.")
    parser.add_argument("-a", "--available", action="store_true", dest="available",
                        help="list all available tasks and metapackages")
    parser.add_argument("-R", "--report", action="store_true", dest="report",
                        help="default: report on installed tasks and metapackages")
    parser.add_argument("-o", "--report-orphans", action="store_true", dest="orphans",
                        help="report on orphan packages from not installed tasks or metapackages")
    parser.add_argument("task", nargs="?", action="store", type=str,
                        help="task or metapackage")
    if ".py" in sys.argv[0]:
        parser.add_argument("--setup", action="store_true", dest="setup",
                            help="install to Linux destination path (default: " + install_path + ")")
    args = parser.parse_args()
    return args


if __name__ == "__main__":
    args = parse_command_line()
    if ".py" in sys.argv[0]:
        if args.setup:
            install(args.task)
            exit(0)
    if (args.install or args.remove or args.show) and not args.task:
        print(args.__dict__)
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
    elif args.independent:
        print(apt.remove(None) + "\n")
    elif args.show:
        apt.show(args.task)
    elif args.list:
        print("tasks installed:\n"+" ".join(apt.installed_tasks), "\n")
        print("metapackages installed:\n"+" ".join(apt.installed_tasks), "\n")
    elif args.available:
        print("tasks available:\n"+" ".join(apt.tasks), "\n")
        print("metapackages available:\n"+" ".join(apt.metapackages), "\n")
    elif args.orphans:
        print("tasks/metapackages orphans:\n")
        apt.report(orphans=True)
    else:
        print("installed tasks/metapackages:\n")
        apt.report()
