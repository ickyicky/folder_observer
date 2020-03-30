import argparse
import os
import sys
import time
import pathlib
import re
import requests
import logging

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

log = logging.getLogger()


class NewFileHander(FileSystemEventHandler):
    def __init__(
        self, extension_mapper, destination_folder, excluded, *args, **kwargs,
    ):
        """
        Handler for observing file modifications.

        extension_mapper should be an object providing .get function, such as dict,
        default dict or special function, and it should return subfolder name for given
        destination folder. Also, destination folder can be specified as root folder 
        and extension mapper can provide absolute paths.

        exluded param should consist of regexes for excluded files
        """
        super().__init__(*args, **kwargs)
        self.extension_mapper = extension_mapper
        self.destination_folder = destination_folder
        self.excluded = excluded

    def on_modified(self, event):
        if not os.path.isfile(event.src_path):
            return

        origin = event.src_path.split(os.path.sep)[-1]

        if any((re.match(pattern, origin) for pattern in self.excluded)):
            return

        log.debug(f"processing {origin}")

        destination_folder = os.path.join(
            self.destination_folder, self.extension_mapper.get(origin)
        )

        log.debug(f"Destination folder: {destination_folder}")

        pathlib.Path(destination_folder).mkdir(parents=True, exist_ok=True)

        try:
            os.rename(
                event.src_path, os.path.join(destination_folder, origin),
            )
        except Exception as e:
            log.error(f"processing {origin} failed due to error:", e)


class ExtensionMapper:
    def __init__(self, known_types={}, default="other", api_url="", name_regex=""):
        """
        Basic extension mapper, which relays on external website.
        """
        self.known_types = known_types
        self.default = default
        self.api_url = api_url
        self.name_regex = name_regex

    def download_info(self, extension):
        try:
            resp = requests.get(os.path.join(self.api_url, extension))
            content = resp.content.decode()
            result = re.findall(self.name_regex, content)[0]
        except:
            result = self.default
        result = result.replace(" ", "").replace(".", "")
        self.known_types[extension] = result
        return result

    def get(self, origin):
        origin = origin.lower()
        extension = ".".join(origin.split(".")[1:])

        try:
            return self.known_types[extension]
        except KeyError:
            return self.download_info(extension)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source", help="Source folder")
    parser.add_argument(
        "-d", "--destination", help="Destination folder", default="source"
    )
    parser.add_argument("-l", "--logfile", help="Log file")
    parser.add_argument("-v", "--debug", help="Run in debug mode", action="store_true")
    args = parser.parse_args()

    if args.destination == "source":
        args.destination = args.source

    if args.logfile:
        from logging.handlers import TimedRotatingFileHandler
        handler = TimedRotatingFileHandler(args.logfile, when="D", backupCount=7)
    else:
        handler = logging.StreamHandler(sys.stdout)

    if args.debug:
        handler.setLevel(logging.DEBUG)
        log.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)
    log.addHandler(handler)

    excluded = (r".*\.crdownload$", r".*\.temp$", r".*\.part.*")
    api_url = "https://fileinfo.com/extension/"
    name_regex = r"""<td>Category</td><td><a href="/filetypes/.+?">(.*?)</a></td>"""
    known_types = {"pdf": "PDF", "skp": "SketchUp"}
    for ext in ("dwg", "dxf"):
        known_types[ext] = "AutoCAD"

    ext_mapper = ExtensionMapper(known_types, "other", api_url, name_regex)
    handler = NewFileHander(ext_mapper, args.destination, excluded)
    observer = Observer()
    observer.schedule(handler, path=args.source, recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(10)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
