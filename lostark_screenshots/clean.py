import os
import re

path = r'C:\Games\Smilegate\Games\LOSTARK\EFGame\Screenshots'
pattern = re.compile(r'^Selfie_\d{8}_.+_\d{3}\.jpg$')

for filename in os.listdir(path):
    if pattern.match(filename):
        file_path = os.path.join(path, filename)
        os.remove(file_path)