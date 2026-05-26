import subprocess
from typing import List

from jinja2 import Template

from python_utils.io_utils.text_io import read_all_text_
from python_utils.path_utils.path_string_operations import add_ending_path_sep


def execute_cmd(target: str, command_line: str, template: str):
    if template:
        template = read_all_text_(template)
        cmd = Template(template).render(target=target, command_line=command_line)
        return subprocess.run(cmd, shell=True, capture_output=True, text=True)


def dir_size(target: str, dir_path: str, template: str):
    execution_result = execute_cmd(
        target=target,
        command_line=f'ls {add_ending_path_sep(dir_path)} | wc -l',
        template=template
    )
    if execution_result:
        return int(
            execution_result.stdout.strip()
        )


def listdir(target: str, dir_path: str, template: str) -> List[str]:
    """
    Executes a shell command to list the contents of a directory, ensuring that each item is listed on a new line.

    Args:
    target (str): The target system or environment where the command is to be executed.
    dir_path (str): The directory path whose contents are to be listed.
    template (str): The path to a template file that provides the shell command structure.

    Returns:
    list of str: A list containing the names of files and directories in the specified directory.
    """
    execution_result = execute_cmd(
        target=target,
        command_line=f'ls -1 {add_ending_path_sep(dir_path)}',
        template=template
    )
    if execution_result and execution_result.stdout:
        return execution_result.stdout.strip().split('\n')
    return []


def list_files(target: str, dir_path: str, template: str, full_path: bool = False) -> List[str]:
    """
    Executes a shell command to list only the files in a directory, ensuring that each item is listed on a new line.
    Optionally returns full paths instead of just file names.

    Args:
    target (str): The target system or environment where the command is to be executed.
    dir_path (str): The directory path whose files are to be listed.
    template (str): The path to a template file that provides the shell command structure.
    full_path (bool): If True, returns full paths of files; otherwise, returns just the names.

    Returns:
    list of str: A list containing the names or full paths of files in the specified directory, excluding directories.
    """
    if full_path:
        command = f"find {add_ending_path_sep(dir_path)} -maxdepth 1 -type f"
    else:
        command = f"find {add_ending_path_sep(dir_path)} -maxdepth 1 -type f -exec basename {{}} \\;"

    execution_result = execute_cmd(
        target=target,
        command_line=command,
        template=template
    )
    if execution_result and execution_result.stdout:
        # Split the output by new lines
        files = execution_result.stdout.strip().split('\n')
        return files
    return []


def list_subdirs(target: str, dir_path: str, template: str, full_path: bool = False) -> List[str]:
    """
    Executes a shell command to list only the directories in a directory, ensuring that each item is listed on a new line.
    Optionally returns full paths instead of just directory names.

    Args:
    target (str): The target system or environment where the command is to be executed.
    dir_path (str): The directory path whose directories are to be listed.
    template (str): The path to a template file that provides the shell command structure.
    full_path (bool): If True, returns full paths of directories; otherwise, returns just the names.

    Returns:
    list of str: A list containing the names or full paths of directories in the specified directory, excluding files.

    Examples:
        >>> from python_utils.cli_utils.eks_utils.constants import CLI_CMD_EXECUTION
        >>> list_subdirs(target='test-pod-hb4s4', dir_path='/data', template=CLI_CMD_EXECUTION, full_path=True)
        ['data/source_data_chunked', 'data/source_data']
    """
    if full_path:
        command = f"find {add_ending_path_sep(dir_path)} -mindepth 1 -maxdepth 1 -type d"
    else:
        command = f"find {add_ending_path_sep(dir_path)} -mindepth 1 -maxdepth 1 -type d -exec basename {{}} \\;"

    execution_result = execute_cmd(
        target=target,
        command_line=command,
        template=template
    )
    if execution_result and execution_result.stdout:
        # Split the output by new lines
        dirs = execution_result.stdout.strip().split('\n')
        return dirs
    return []





