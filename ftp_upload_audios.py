#!/usr/bin/python

from configobj import ConfigObj
from base64 import b64decode
from ftplib import FTP
from os import listdir, rename
from os.path import join, isdir, basename, splitext, isfile
from subprocess import check_output, CalledProcessError
from logging import getLogger, FileHandler, Formatter, INFO
from datetime import date, datetime, timedelta
from sys import argv
from requests import head
from pysftp import Connection, CnOpts


class NoAudioFile(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


class WrongFilenameFormat(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


def is_day_and_file_format_ok(audio_dir, program, filename):
    """Validates file format YYYYMMDD-programname.mp3 and its date"""
    path_file = join(audio_dir, program, filename)
    broadcast_date = path_file.split("/")[-1].split("-")[0]
    if (broadcast_date >= past_date_start) and (broadcast_date <= past_date_end):
        # Let's check file name is the program name
        name, extension = splitext(filename)
        program_name = "-%s" % (program)
        if name.replace(broadcast_date, "", 1) == program_name:
            return True
    return False


def get_audio_type(path_file):
    "Returns either .mp3 or .ogg"
    file_type = check_output(["file", path_file]).split(": ")[1].strip()
    if any(tag in file_type for tag in config["audio_tags"]["mp3"]):
        return ".mp3"
    elif any(tag in file_type for tag in config["audio_tags"]["ogg"]):
        return ".ogg"
    raise NoAudioFile(path_file)


def if_audio_ensure_mp3(path_file):
    "If audio file makes sure is .mp3 file, if not it converts to it"
    # TODO: sndhdr not working
    # https://docs.python.org/2/library/sndhdr.html#module-sndhdr
    try:
        if get_audio_type(path_file) == ".ogg":
            path_file_ogg, extension_ogg = splitext(path_file)
            path_file_mp3 = path_file_ogg + ".mp3"
            # NEW: let's check if corresponding .mp3 file already exists
            if not isfile(path_file_mp3):
                try:
                    logger.info("Converting %s to MP3..." % (path_file))
                    # Requires package libav-tools
                    check_output(
                        [
                            "avconv",
                            "-y",
                            "-loglevel",
                            "quiet",
                            "-i",
                            path_file,
                            "-c:a",
                            "libmp3lame",
                            "-q:a",
                            "2",
                            path_file_mp3,
                        ]
                    )
                    logger.info("Converting %s to MP3 finished" % (path_file))
                except OSError as e:
                    logger.error("Missing required packages. Eception: %s" % (e))
                except CalledProcessError as e:
                    logger.error(
                        "Error converting from .ogg to .mp3 %s. Eception: %s"
                        % (path_file, e)
                    )
            else:
                logger.warning(
                    "%s already exists, skipping %s convert"
                    % (path_file_mp3, path_file)
                )
            return path_file_mp3
    except NoAudioFile:
        raise
    return path_file


def ftp_upload(dir_filename_list):
    "Uploads a list of (dir, filename)"
    # Required to fix pysftp bug
    cnopts = CnOpts()
    cnopts.hostkeys = None

    with Connection(
        host=b64decode(config["ftp"]["host"]).decode("utf-8"),
        username=b64decode(config["ftp"]["user"]).decode("utf-8"),
        password=b64decode(config["ftp"]["password"]).decode("utf-8"),
        port=int(b64decode(config["ftp"]["port"]).decode("utf-8")),
        cnopts=cnopts,
    ) as sftp:
        logger.info("SFTP connection OK")
        for dir_filename in dir_filename_list:
            file_path = join(dir_filename[0], dir_filename[1])
            logger.info("Uploading %s..." % (file_path))
            sftp.put(file_path, f"{config['dir']['remote']}/{dir_filename[1]}")
            logger.info("FTP uploaded successfully: %s" % (file_path))


def is_url(url):
    """ Checks if the URL exists """
    # https://stackoverflow.com/a/13641613
    try:
        if head(url).status_code == 200:
            return True
    except requests.ConnectionError as e:
        logger.warning("Error %s while connecting to %s" % (e, url))
    return False


config = ConfigObj("config")

handler = FileHandler(config["dir"]["log"])
logger = getLogger("audio_date_formatter")
formatter = Formatter("%(asctime)s - %(lineno)s: %(levelname)s %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(INFO)

logger.info("START %s" % (argv[0]))

past_date_start = (
    date.today() - timedelta(days=int(config["days_back_start"]))
).strftime(config["broadcast_date_format"])
past_date_end = (date.today() - timedelta(days=int(config["days_back_end"]))).strftime(
    config["broadcast_date_format"]
)

files_to_upload = []

for dir in listdir(config["dir"]["local"]):
    path_dir = join(config["dir"]["local"], dir)
    try:
        file_list = listdir(path_dir)
    except OSError as e:
        logger.warning("File instead of a directory: %s" % (e))
    if (
        isdir(path_dir)
        and (len(file_list) > 0)
        and not any(dir in ignored_dir for ignored_dir in config["dir"]["ignore"])
    ):
        program = dir
        logger.info('Checking "%s"' % (program))
        for file in file_list:
            path_file = join(config["dir"]["local"], dir, file)
            file = basename(path_file)
            # if is_day_and_file_format_ok(config['dir']['local'], dir, file):
            if True:
                try:
                    # path_file = if_audio_ensure_mp3(path_file)
                    pass
                except NoAudioFile:
                    if config["dir"] == "remove":
                        # TODO: implement
                        pass
                    logger.warning('No audio file. Ignoring "%s"' % (path_file))
                else:
                    if not (
                        is_url("%s%s" % (config["remote_url"], file))
                        and config["remote_file_exists_action"] == "ignore"
                    ):
                        files_to_upload.append(
                            (join(config["dir"]["local"], dir), file)
                        )
if files_to_upload:
    ftp_upload(files_to_upload)

logger.info("END %s" % (argv[0]))
