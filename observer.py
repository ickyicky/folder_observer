import argparse
import collections
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
        self,
        extension_mapper,
        destination_folder,
        excluded,
        *args,
        recursive=False,
        delay=0,
        ln_duration=0,
        **kwargs,
    ):
        """
        Handler for observing file modifications.

        extension_mapper should be an object providing .get function, such as dict,
        default dict or special function, and it should return subfolder name for given
        destination folder. Also, destination folder can be specified as root folder
        and extension mapper can provide absolute paths.

        There's and option to preserve file for specified delay or to cresate temporary
        link to copied desitnation for diven time.

        exluded param should consist of regexes for excluded files

        """
        super().__init__(*args, **kwargs)
        self.extension_mapper = extension_mapper
        self.destination_folder = destination_folder
        self.excluded = excluded
        self.recursive = recursive
        self.delay = delay
        self.ln_duration = ln_duration

    def on_modified(self, event):
        if not os.path.isfile(event.src_path):
            return

        origin = event.src_path.split(os.path.sep)[-1]

        if any((re.match(pattern, origin) for pattern in self.excluded)):
            return

        if self.delay:
            time.sleep(self.delay)

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
            return

        if self.ln_duration:
            log.debug(f"creating symlink for {origin}")
            os.symlink(
                os.path.join(destination_folder, origin), event.src_path,
            )
            time.sleep(self.ln_duration)
            log.debug(f"removing symlink for {origin}")
            os.remove(event.src_path)


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
        extension = origin.split(".")[-1]

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
    parser.add_argument(
        "-r", "--recursive", help="Recursive", action="store_true", default=False
    )
    parser.add_argument(
        "--sort-old",
        help="At start of program, sort all old files",
        action="store_true",
        default=True,
    )
    parser.add_argument(
        "--delay",
        help="Delay for file move action in seconds",
        action="store",
        type=int,
        default=0,
    )
    parser.add_argument(
        "--ln-duration",
        help="Creates symbolic link to moved file and replaces original file with ot for given amount of seconds",
        action="store",
        type=int,
        default=0,
    )
    args = parser.parse_args()

    if args.recursive and (
        args.destination == "source" or args.source.startswith(args.destination)
    ):
        raise Exception(
            "When using --recursive option, destination folder cannot be the same (or subfolder of) as source one"
        )

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
    handler = NewFileHander(
        ext_mapper,
        args.destination,
        excluded,
        delay=args.delay,
        ln_duration=args.ln_duration,
    )
    observer = Observer()
    observer.schedule(handler, path=args.source, recursive=args.recursive)
    observer.start()

    if args.sort_old:
        if args.recursive:
            files_to_sort = [
                os.path.join(dp, f)
                for dp, dn, fn in os.walk(os.path.expanduser(args.source))
                for f in fn
            ]
        else:
            files_to_sort = [
                os.path.join(args.source, f)
                for f in os.listdir(os.path.expanduser(args.source))
            ]
            files_to_sort = [f for f in files_to_sort if os.path.isfile(f)]
        event_cls = collections.namedtuple("Event", ("src_path"))

        for f in files_to_sort:
            handler.on_modified(event_cls(f))

    try:
        while True:
            time.sleep(10)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
