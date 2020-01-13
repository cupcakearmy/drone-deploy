import io
import os
import random
import string
import subprocess
import warnings
from os.path import abspath, join, dirname
from typing import List

import paramiko
from paramiko import SSHClient

VERSION = '1.0.3'


def get_random_string(length: int = 128) -> str:
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))


def execute(c: SSHClient, cmd: str, path: str = None, env: dict = None) -> str:
    if path is not None:
        cmd = 'cd {}; {}'.format(path, cmd)
    stdin, stdout, stderr = c.exec_command(cmd, environment=env)
    return stdout.read().decode('utf-8').strip()


def main():
    print(f'> Version: {VERSION}')
    print('> Deployment started 🚀')
    host = os.environ.get('PLUGIN_HOST')
    port = os.environ.get('PLUGIN_PORT', 22)
    user = os.environ.get('PLUGIN_USER')

    password = os.environ.get('PLUGIN_PASSWORD')
    key = os.environ.get('PLUGIN_KEY')

    # Takes a string, splits it at the comma and removes empty elements
    def clean_array(s: str) -> List[str]:
        return list(filter(None, s.split(',')))

    commands = clean_array(os.environ.get('PLUGIN_COMMANDS', ''))
    sources = clean_array(os.environ.get('PLUGIN_SOURCES', ''))
    deletes = clean_array(os.environ.get('PLUGIN_DELETE', ''))
    target = os.environ.get('PLUGIN_TARGET')

    # Check for host, port and user
    for env in [host, port, user]:
        if env is None:
            raise Exception('Missing host, port or user env variable')

    # Check if there is a possible authentication method
    if len(list(filter(lambda x: x is not None, [password, key]))) == 0:
        raise Exception('No authentication method provided')

    # Check if target is set
    if len(sources) != 0 and target is None:
        raise Exception('Target not set')

    # Remote Envs
    envs_raw = os.environ.get('PLUGIN_ENVS')
    envs = None
    if envs_raw is not None:
        prefix = 'PLUGIN_'
        # Take only the envs that start with PLUGIN_ and remove the prefix
        envs = {k[len(prefix):]: v for k, v in os.environ.items() if k.startswith(prefix)}

        if 'all' != envs_raw or ',' in envs_raw:
            # Make them uppercase
            selected = [x.upper() for x in clean_array(envs_raw)]
            # Select only the envs that where specified inside of envs
            envs = {k: v for k, v in envs.items() if k in selected}

    ssh: SSHClient = paramiko.SSHClient()
    try:
        k = paramiko.RSAKey.from_private_key(io.StringIO(key))
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        print(host, user, port)
        ssh.connect(hostname=host, username=user, pkey=k, port=port, password=password, timeout=3)

        # If a target is set, make sure the directory is created and writable
        if target is not None:
            try:
                execute(ssh, 'mkdir -p {}'.format(target))
                tmp_file = get_random_string()
                execute(ssh, 'touch {}; rm {}'.format(tmp_file, tmp_file), target)
            except Exception:
                raise Exception('Could not create directory')

        sftp = ssh.open_sftp()
        try:
            # DELETE
            for delete in deletes:
                sftp.remove(join(target, delete))

            # COPY
            if len(sources) != 0:
                archive = get_random_string(64) + '.tar.gz'  # Keep the max file name length under 128 chars
                archive_local = abspath(archive)
                archive_remote = join(target, archive)

                # Compress
                cmd = ['tar', '-czf', archive, '-C', dirname(archive_local), *sources]
                run = subprocess.run(cmd, capture_output=True)
                if run.returncode != 0:
                    raise Exception('Error while compressing locally. {}'.format(run.stderr.decode('utf-8').strip()))

                # Upload
                sftp.put(archive_local, archive_remote)
                # Extract
                execute(ssh, 'tar -xzf {}'.format(archive), target)

                # Delete Archives
                sftp.remove(archive_remote)
                subprocess.run(['rm', archive_local], capture_output=True)
        finally:
            sftp.close()

        for command in commands:
            output = execute(ssh, command, target, envs)
            print(command)
            print(output)

    finally:
        ssh.close()


with warnings.catch_warnings():
    warnings.simplefilter('ignore')
    main()
