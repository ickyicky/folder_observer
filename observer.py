import os
import sys
import time
import re
import requests

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


class NewFileHander(FileSystemEventHandler):
    def __init__(
        self, extension_mapper, destination_folder, excluded, *args, **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.extension_mapper = extension_mapper
        self.destination_folder = destination_folder
        self.excluded = excluded

    def on_modified(self, event):
        if not os.path.isfile(event.src_path):
            return

        origin = event.src_path.split("/")[-1]

        if any((re.match(pattern, origin) for pattern in self.excluded)):
            return

        print(f"processing {origin}")

        destination_folder = os.path.join(
            self.destination_folder, self.extension_mapper.get(origin)
        )

        try:
            os.rename(
                event.src_path,
                os.path.join(destination_folder, origin),
            )
        except FileNotFoundError:
            os.mkdir(destination_folder)
            os.rename(
                event.src_path,
                os.path.join(destination_folder, origin),
            )


class ExtensionMapper:
    def __init__(self, known_types={}, default="other", api_url="", name_regex=""):
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
    source_folder = destination_folder = sys.argv[1]
    excluded = (r".*\.crdownload$",)
    api_url = "https://fileinfo.com/extension/"
    name_regex = r"""<td>Category</td><td><a href="/filetypes/.+?">(.*?)</a></td>"""
    known_types = {}

    ext_mapper = ExtensionMapper(known_types, "other", api_url, name_regex)
    handler = NewFileHander(ext_mapper, destination_folder, excluded)
    observer = Observer()
    observer.schedule(handler, path=source_folder, recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(10)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
