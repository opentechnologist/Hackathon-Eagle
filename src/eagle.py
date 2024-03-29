from configparser import ConfigParser
from random import Random
from json import JSONEncoder
import paramiko
import os
import time
import eel
import json

class Eagle(object):

    def __init__(self, config_filename, send_fn):
        self.running = False
        self.ssh = None
        self.sftp = None
        self.logs = {}
        # retrieve configuration from external config file
        self.config = ConfigParser()
        self.config.read(os.sep.join([os.getcwd(), config_filename]))
        self.username = self.get_config('username')
        self.domain = self.get_config('flndevdomain')
        self.maxlines = int(self.get_config('maxlines'))
        self.gaflogsdir = self.get_config('gaflogsdir')
        self.thriftlogsdir = self.get_config('thriftlogsdir')
        self.remotetmp = self.get_config('remotetmpdir')
        self.tempfile = os.sep.join([self.remotetmp, 'log'+str(int(Random().random()*1e12))])
        self.localdir = os.sep.join([os.getcwd(), 'logs'])
        self.send_log_to_user = send_fn


    def __del__(self):
        self.close()


    def get_config(self, option):
        if self.config:
            return self.config.get('eagle', option)


    def get_files_info(self, path):
        files_info = {}
        if self.sftp:
            for filename in self.sftp.listdir(path):
                if filename.split('.')[-1] in ['json', 'log', 'error']:
                    fullpath = os.sep.join([path, filename])
                    filestat = self.sftp.stat(fullpath)
                    self.log('stat', path, filestat.st_mtime, filestat.st_size, filestat.st_mode & 0x4, fullpath)
                    files_info[filename] = dict(
                        name=filename,
                        longname=fullpath,
                        date=filestat.st_mtime,
                        size=filestat.st_size,
                        mode=filestat.st_mode & 0x4,
                        start=1,
                    )
        return files_info


    def get_logs_info(self):
        logs_info = {}
        logs_info.update(self.get_files_info(self.gaflogsdir))
        logs_info.update(self.get_files_info(self.thriftlogsdir))
        return logs_info

    def get_logs(self, log_info):
        print(log_info)
        stdin, stdout, stderr = self.ssh.exec_command(
            'tail -n +%d -q %s | tail -n %d -q' % (
                log_info['start'], log_info['longname'], self.maxlines
            )
        )

        message = str(stdout.read(), 'utf-8');
        message = message.replace("}\n", "},");
        message = "[" + message + "]";

        try:
            message = json.dumps(message)
        except:
            message = message[1:len(message)-1]

        return message

    def send(self, log_info):

        log_name = log_info['name']
        contents = self.get_logs(log_info)
        json = JSONEncoder()
        log_name = log_name.replace('program_', '').upper()
        log_name = log_name.replace('-', '_').replace('.', '_')
        self.send_log_to_user(json.encode(dict(name=log_name, value=contents)))


    def watch(self):
        try:
            # initially send the all log files
            self.logs = self.get_logs_info()
            for log_name in self.logs:
                self.send(self.logs[log_name])

            # sleep and watch for log changes
            while self.running:
                time.sleep(1)
                logs_info = self.get_logs_info()
                for log_key in logs_info:
                    if (
                        self.running and
                        logs_info[log_key]['size'] != 0 and
                        logs_info[log_key]['mode'] == 0x4 and (
                            log_key not in self.logs
                            or
                            logs_info[log_key]['size'] != self.logs[log_key]['size']
                            or
                            logs_info[log_key]['date'] != self.logs[log_key]['date']
                        )
                    ):
                        # the remote file has changed, send the log
                        self.send(logs_info[log_key])
                        # update the cached log info
                        self.logs[log_key] = logs_info[log_key]
        except Exception as e:
            self.log('ssh error', e)
            pass
        finally:
            # watch was stopped, wait for 5 seconds before exiting
            self.running = False
            # self.sleep(3)
            self.close()

    def open(self, hostname):
        if hostname:
            self.ssh = paramiko.SSHClient()
            self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh.load_system_host_keys()
            self.ssh.connect(
                hostname='.'.join([hostname, self.domain]), username=self.username
            )
            self.sftp = self.ssh.open_sftp()
            self.sftp.chdir(self.gaflogsdir)
            self.sftp.getcwd()
            self.running = True
            self.hostname = hostname


    def close(self):
        self.running = False
        if self.sftp:
            self.sftp.close()
            self.sftp = None
        if self.ssh:
            self.ssh.close()
            self.ssh = None
        # self.sleep(3)


    def log(self, *args):
        # print(args)
        pass


    def sleep(self, seconds):
        time.sleep(seconds)
