#!/usr/bin/env python

from src.eagle import Eagle
import eel
import os
import threading


@eel.expose
def connect(host):
    try:
        if not eagle.running:
            eagle.open(host)
    except Exception as e:
        return {
            "success": False,
            "message": str(e)
        }
    return {
        "success": True
    }


def send_log_to_user(log):
    eel.push(log)


def watcher():
    while True:
        if eagle.running:
            eagle.watch()
        eel.sleep(1)


def main():
    print('Welcome to Eagle!')
    global eagle
    eagle = Eagle('eagle.conf', send_log_to_user)
    eagle.watch()

    eel.init('src/web')
    t = threading.Thread(target=watcher)
    t.start()

    try:
      eel.start('index.html', size=(1000, 800))
    except (SystemExit, MemoryError, KeyboardInterrupt):
      eagle.close()

if __name__ == "__main__":
    main()
