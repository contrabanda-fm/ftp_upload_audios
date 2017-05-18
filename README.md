ftp_upload_audios

Loops over dirs looking for audio files.
If an .ogg file is found, it converts it to .mp3 and adds it to the list to upload.
If an .mp3 file is found, it adds it to the list to upload.
Finally it uploads all the file by FTP

Requirements:

libav-tools
