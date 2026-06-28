"""Completion functions for lshell"""

import os
import re
from lshell import sec


def completedefault(*ignored):
    """Method called to complete an input line when no command-specific
    complete_*() method is available.

    By default, it returns an empty list.

    """
    return []


def _prefix_matches(candidates, prefix):
    """Return prefix matches, with a case-insensitive fallback when needed."""
    matches = [candidate for candidate in candidates if candidate.startswith(prefix)]
    if matches or not prefix:
        return matches

    prefix_lower = prefix.lower()
    return [
        candidate for candidate in candidates if candidate.lower().startswith(prefix_lower)
    ]


def completenames(conf, text, line, *ignored):
    """This method is meant to override the original completenames method
    to overload it's output with the command available in the 'allowed'
    variable. This is useful when typing 'tab-tab' in the command prompt
    """
    commands = conf["allowed"]

    # Handle local relative commands explicitly allowed as "./foo".
    # readline tokenization may provide either "foo" or "./foo" as text,
    # depending on completer delimiters/platform.
    if line.startswith("./") or text.startswith("./"):
        prefix = text[2:] if text.startswith("./") else text
        relative_commands = [cmd for cmd in commands if cmd.startswith("./")]
        matches = _prefix_matches(relative_commands, f"./{prefix}")
        if text.startswith("./"):
            return matches
        return [cmd[2:] for cmd in matches]

    return _prefix_matches(commands, text)


SUDO_ARGUMENT_COMPLETIONS = {
    "apt": [
        "autoclean",
        "autoremove",
        "clean",
        "dist-upgrade",
        "edit-sources",
        "full-upgrade",
        "install",
        "list",
        "policy",
        "purge",
        "reinstall",
        "remove",
        "satisfy",
        "search",
        "show",
        "update",
        "upgrade",
    ],
    "apt-cache": [
        "depends",
        "dump",
        "dumpavail",
        "madison",
        "pkgnames",
        "policy",
        "rdepends",
        "search",
        "show",
        "showpkg",
        "stats",
        "unmet",
    ],
    "apt-get": [
        "autoclean",
        "autoremove",
        "build-dep",
        "check",
        "changelog",
        "clean",
        "dist-upgrade",
        "download",
        "install",
        "purge",
        "reinstall",
        "remove",
        "source",
        "update",
        "upgrade",
    ],
    "dpkg": [
        "--audit",
        "--configure",
        "--contents",
        "--get-selections",
        "--info",
        "--install",
        "--list",
        "--purge",
        "--remove",
        "--search",
        "--status",
        "--verify",
    ],
    "journalctl": [
        "--boot",
        "--catalog",
        "--disk-usage",
        "--follow",
        "--kernel",
        "--lines",
        "--no-pager",
        "--reverse",
        "--since",
        "--unit",
        "--until",
        "-b",
        "-e",
        "-f",
        "-k",
        "-n",
        "-r",
        "-u",
    ],
    "systemctl": [
        "cat",
        "daemon-reload",
        "disable",
        "edit",
        "enable",
        "is-active",
        "is-enabled",
        "list-unit-files",
        "list-units",
        "mask",
        "reload",
        "reload-or-restart",
        "reset-failed",
        "restart",
        "show",
        "start",
        "status",
        "stop",
        "try-restart",
        "unmask",
    ],
}


def complete_sudo(conf, text, line, begidx, endidx):
    """Complete sudo command names, known subcommands, and path arguments."""
    line_before_cursor = line[:endidx] if 0 <= endidx <= len(line) else line
    parts = line_before_cursor.split()
    if line_before_cursor and line_before_cursor[-1].isspace():
        parts.append("")

    sudo_commands = conf["sudo_commands"]
    if len(parts) <= 2:
        return _prefix_matches(sudo_commands, text)

    sudo_command = parts[1]
    if sudo_command not in sudo_commands:
        return []

    argument_position = len(parts) - 3
    if argument_position == 0:
        subcommands = SUDO_ARGUMENT_COMPLETIONS.get(sudo_command, [])
        if subcommands:
            return _prefix_matches(subcommands, text)

    return complete_list_dir(conf, text, line, begidx, endidx)


def _completion_path_allowed(candidate_path, conf):
    """Return whether a completion candidate is visible under path ACLs."""
    ret_check_path, _conf = sec.check_path(candidate_path, conf, completion=1)
    return ret_check_path == 0


def complete_change_dir(conf, text, line, begidx, endidx):
    """complete directories"""
    dirs_to_return = []
    tocomplete = line.split(" ")[1]
    # replace "~" with home path
    tocomplete = re.sub("^~", conf["home_path"], tocomplete)

    # Detect relative vs absolute paths
    if not tocomplete.startswith("/"):
        # Resolve relative paths based on current working directory
        base_path = os.getcwd()
        tocomplete = os.path.normpath(os.path.join(base_path, tocomplete))
    try:
        directory = os.path.realpath(tocomplete)
    except OSError:
        directory = os.getcwd()

    # if directory doesn't exist, take the parent directory
    if not os.path.isdir(directory):
        directory = directory.rsplit("/", 1)[0]
        if directory == "":
            directory = "/"

    directory = os.path.normpath(directory)

    # check path security
    ret_check_path, conf = sec.check_path(directory, conf, completion=1)

    # if path is secure, list subdirectories and files
    if ret_check_path == 0:
        for instance in os.listdir(directory):
            candidate_path = os.path.join(directory, instance)
            if (
                os.path.isdir(candidate_path)
                and instance.startswith(text)
                and _completion_path_allowed(candidate_path, conf)
            ):
                dirs_to_return.append(f"{instance}/")

    # if path is not secure, add completion based on allowed path
    else:
        allowed_paths = conf["path"][0].split("|")
        for instance in allowed_paths:
            # Check if the directory matches or is a parent of the allowed path
            if instance.startswith(directory) and instance.startswith(tocomplete):
                # Extract the next unmatched segment of the allowed path
                remaining_path = instance[len(directory) :].lstrip("/")
                # Nothing left to suggest for this allowed path.
                if not remaining_path:
                    continue
                if "/" in remaining_path:
                    next_segment = remaining_path.split("/", 1)[0] + "/"
                else:
                    next_segment = remaining_path + "/"

                # Add unique suggestions
                if next_segment and next_segment not in dirs_to_return:
                    dirs_to_return.append(next_segment)

    return dirs_to_return


def complete_list_dir(conf, text, line, begidx, endidx):
    """complete with files and directories"""
    results = []
    # Resolve the full token before cursor from the current line. This is
    # required because readline uses "/" as a delimiter, so `text` may only
    # contain the basename fragment after the last slash.
    line_before_cursor = line[:endidx] if 0 <= endidx <= len(line) else line
    if line_before_cursor and line_before_cursor[-1].isspace():
        tocomplete = ""
    else:
        parts = line_before_cursor.split()
        tocomplete = parts[-1] if parts else ""

    # Fallback to readline-provided token when available.
    if not tocomplete and text:
        tocomplete = text
    # replace "~" with home path
    tocomplete = re.sub("^~", conf["home_path"], tocomplete)
    directory = os.path.dirname(tocomplete) if os.path.dirname(tocomplete) else "."
    prefix = os.path.basename(tocomplete)
    if tocomplete.endswith("/"):
        directory = tocomplete
        prefix = ""

    try:
        directory = os.path.realpath(directory)
    except OSError:
        return []

    if not os.path.isdir(directory):
        return []

    ret_check_path, conf = sec.check_path(directory, conf, completion=1)
    if ret_check_path == 0:
        # if path is secure, list subdirectories and files
        list_dir = os.listdir(directory)
        for instance in list_dir:
            if not instance.startswith(prefix):
                continue
            candidate_path = os.path.join(directory, instance)
            if not _completion_path_allowed(candidate_path, conf):
                continue
            if os.path.isdir(candidate_path):
                instance = instance + "/"
            else:
                instance = instance + " "
            results.append(instance)
        return results

    # if path is not secure, return nothing
    return []
