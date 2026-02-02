import subprocess


class TerminalCMDError(Exception): ...


def run_terminal_cmd(cmd: str, timeout: int | None = None):
    rsyncproc = subprocess.Popen(
        cmd,
        shell=True,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
    )
    while True:
        next_line = rsyncproc.stdout.readline().decode('utf-8').rstrip()
        if not next_line:
            break
        print(next_line)

    try:
        exitcode = rsyncproc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        exitcode = None

    if exitcode is None:
        print(f'WARNING: never received exit code where timeout: {timeout}')

    elif exitcode != 0:
        print('WARNING: An error occurred!')
        raise TerminalCMDError('Error Occurred while executing cmd!')
