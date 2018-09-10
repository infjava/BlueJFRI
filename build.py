#!/usr/bin/python3

import os
import os.path
import shutil
import glob

def copy_bluej_file(path):
    shutil.copyfile(path, 'dst' + path[3:])

def copy_bluej_tree(path):
    shutil.copytree(path, 'dst' + path[3:])

if not os.path.exists('src/bluej/BlueJ.exe'):
    print('ERROR: unpack bluej to the src/bluej directory')

if os.path.exists('dst/bluej'):
    print('=== removing old bluej destination directory')
    shutil.rmtree('dst/bluej')

print('=== creating new bluej destination directory')
os.mkdir('dst/bluej')
os.mkdir('dst/bluej/lib')

print('=== copying icons')
copy_bluej_tree('src/bluej/icons')

print('=== copying fonts')
copy_bluej_tree('src/bluej/lib/fonts')

print('=== copying images')
copy_bluej_tree('src/bluej/lib/images')

print('=== copying stylesheets')
copy_bluej_tree('src/bluej/lib/stylesheets')

print('=== copying userlib README')
os.mkdir('dst/bluej/lib/userlib')
copy_bluej_file('src/bluej/lib/userlib/README.TXT')

print('=== copying english translations')
os.mkdir('dst/bluej/lib/english')
for file in glob.glob('src/bluej/lib/english/*'):
    if not os.path.isdir(file):
        copy_bluej_file(file)

print('=== copying modified templates')
shutil.copytree('data/templates', 'dst/bluej/lib/english/templates')

print('=== copying original template READMEs')
copy_bluej_file('src/bluej/lib/english/templates/README')
copy_bluej_file('src/bluej/lib/english/templates/newclass/README')

print('=== copy libraries')
for file in glob.glob('src/bluej/lib/*'):
    if not os.path.isdir(file):
        copy_bluej_file(file)

print('=== copy project README and licences')
copy_bluej_file('src/bluej/README.TXT')
copy_bluej_file('src/bluej/LICENSE.txt')
copy_bluej_file('src/bluej/THIRDPARTYLICENSE.txt')

print('=== copy BlueJ.exe')
copy_bluej_file('src/bluej/BlueJ.exe')
