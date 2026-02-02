import subprocess

try:
    # Try to get version tags
    VERSION = (
        subprocess.Popen(
            'git describe --tags --exact-match',
            shell=True,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )
        .communicate()[0]
        .strip()
        .decode('utf-8')
    )
    if not VERSION:
        raise ValueError('Empty version')
except (OSError, IOError, ValueError, subprocess.CalledProcessError):
    try:
        VERSION = (
            subprocess.Popen(
                'git rev-parse --short HEAD',
                shell=True,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
            )
            .communicate()[0]
            .strip()
            .decode('utf-8')
        )
    except (OSError, IOError):
        VERSION = 'unknown'
