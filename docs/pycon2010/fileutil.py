import glob
import os.path

for fullfilename in glob.glob('/home/cat/proj/cmd2/*.py'):
    (dirpath, fname) = os.path.split(fullfilename)
    stats = os.stat(fullfilename)
    binds['path'] = dirpath
    binds['name'] = fname
    binds['bytes'] = stats.st_size
    cmd("""INSERT INTO cat.files (path, name, bytes)
           VALUES (%(path)s, %(name)s, %(bytes)s)""")
quit()
