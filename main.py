import io
import os
import random
import string
import warnings
import subprocess
from typing import List
from os.path import abspath, join, dirname

import paramiko
from paramiko import SSHClient


def get_random_string(length: int = 128) -> str:
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))


def execute(c: SSHClient, cmd: str, path: str = None) -> str:
    if path is not None:
        cmd = 'cd {}; {}'.format(path, cmd)
    stdin, stdout, stderr = c.exec_command(cmd)
    output = stdout.read().decode('utf-8').strip()
    error = stderr.read().decode('utf-8')

    if len(error) is not 0:
        print('ERROR: {}'.format(error))

    return output


def main():
    host = os.environ.get('PLUGIN_HOST')
    port = os.environ.get('PLUGIN_PORT', 22)
    user = os.environ.get('PLUGIN_USER')

    password = os.environ.get('PLUGIN_PASSWORD')
    key = os.environ.get('PLUGIN_KEY')

    def clean_array(s: str) -> List[str]:
        return list(filter(None, s.split(',')))

    commands = clean_array(os.environ.get('PLUGIN_COMMANDS', ''))
    sources = clean_array(os.environ.get('PLUGIN_SOURCES', ''))
    deletes = clean_array(os.environ.get('PLUGIN_DELETE', ''))
    target = os.environ.get('PLUGIN_TARGET')

    for env in [host, port, user]:
        if env is None:
            raise Exception('Missing ENV variable')

    if len(list(filter(lambda x: x is not None, [password, key]))) is 0:
        raise Exception('No authentication method provided')

    if len(sources) is not 0 and target is None:
        raise Exception('Target not set')

    ssh: SSHClient = paramiko.SSHClient()
    try:
        k = paramiko.RSAKey.from_private_key(io.StringIO(key))
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(hostname=host, username=user, pkey=k, port=port, password=password)

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
            if len(sources) is not 0:
                archive = get_random_string(100) + '.tar.gz'  # Keep the max file name length under 128 chars
                archive_local = abspath(archive)
                archive_remote = join(target, archive)

                # sources = list(map(lambda x: join(dirname(archive_local), x), sources))
                # print(sources)

                # Compress
                cmd = ['tar', '-czf', archive, '-C', dirname(archive_local), *sources]
                run = subprocess.run(cmd, capture_output=True)
                if run.returncode is not 0:
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
            output = execute(ssh, command, target)
            print(output)

    finally:
        ssh.close()


with warnings.catch_warnings():
    warnings.simplefilter('ignore')
    main()
