from confduino.liblist import libraries_dir
from confduino.util import tmpdir, download, clean_dir, ConfduinoError
from entrypoint2 import entrypoint
from path import Path as path
from pyunpack import Archive
import logging

log = logging.getLogger(__name__)


def noexample(x):
    while 1:
        f = x.next()
        if 'example' not in f.lower():
            yield f


def create_name(root):
    header_only = len(list(noexample(root.walkfiles('*.cpp')))) == 0
#    libname = None
    goodh = []
    for h in root.files('*.h'):
        cpp = h.stripext() + '.cpp'
        if header_only or cpp.exists():
            goodh += [h]
    assert len(goodh) > 0
    log.debug('candidate headers: %s', goodh)

    hchoosen = None
    if len(goodh) == 1:
        hchoosen = goodh[0]
    else:
        for h in goodh:
            n = h.namebase
            if n in str(root):
                hchoosen = h
        if not hchoosen:
            hchoosen = goodh[0]

    log.debug('choosing: %s', hchoosen)

#            assert not libname
    libname = hchoosen.namebase
    return libname


def rename_root(root):
    name = create_name(root)
    log.debug('lib has no own dir')
    root.rename(root.parent / name)
    root = root.parent / name
    return root


def fix_libdir(lib_dir):
    allh = lib_dir.files('*.h')
    if len(allh) == 1:
        x = lib_dir.parent / allh[0].namebase
        lib_dir.rename(x)
        lib_dir = x
    return lib_dir


def find_lib_dir(root):
    """search for lib dir under root."""
    root = path(root)
    log.debug('files in dir: %s', root)
    for x in root.walkfiles():
        log.debug('  %s', x)

    # only 1 dir in root? (example: github)
    if not len(root.files()) and len(root.dirs()) == 1:
        log.debug('go inside root')
        root = root.dirs()[0]

    if len(root.files('keywords.txt')):
        root = rename_root(root)
        return root, root

    keywords = list(root.walkfiles('keywords.txt'))
    if len(keywords):
        if len(keywords) > 1:
            log.warning('more keywords.txt found. Installing only one.  %s', keywords)  

        lib_dir = keywords[0].parent
        lib_dir = fix_libdir(lib_dir)
        return root, lib_dir

    header_only = len(list(noexample(root.walkfiles('*.cpp')))) == 0
    log.debug('header_only: %s', header_only)
    lib_dir = None

    headers = list(noexample(root.walkfiles('*.h')))

    for h in headers:
        cpp = h.stripext() + '.cpp'
        if (header_only or cpp.exists()) and h.parent.name.lower() == h.namebase.lower():
            assert not lib_dir
            lib_dir = h.parent
            log.debug('found lib: %s', lib_dir)

    if not lib_dir:
        if len(headers) == 1 and len(list(root.files('*.h'))) == 0:
            log.debug('only 1 header, not in root')
            lib_dir = headers[0].parent
            lib_dir = rename_root(lib_dir)

    if not lib_dir:
        # xxx.cpp and xxx.h in root? -> rename root dir
        root = rename_root(root)
        return root, root
#        for h in root.files('*.h'):
#            cpp = h.stripext() + '.cpp'
#            if  header_only or cpp.exists():
#                assert not lib_dir
#                root.rename(root.parent / h.namebase)
#                root = lib_dir = root.parent / h.namebase
    assert lib_dir
    return root, lib_dir

INO_PATTERNS = ['*.pde', '*.ino']
EXAMPLES = 'examples'


def files_multi_pattern(directory, patterns):
    ls = [list(directory.walkfiles(pattern)) for pattern in patterns]
    return set(reduce(list.__add__, ls))


def move_examples(root, lib_dir):
    """find examples not under lib dir, and move into ``examples``"""
    all_pde = files_multi_pattern(root, INO_PATTERNS)
    lib_pde = files_multi_pattern(lib_dir, INO_PATTERNS)
    stray_pde = all_pde.difference(lib_pde)
    if len(stray_pde) and not len(lib_pde):
        log.debug(
            'examples found outside lib dir, moving them: %s', stray_pde)
        examples = lib_dir / EXAMPLES
        examples.makedirs()
        for x in stray_pde:
            d = examples / x.namebase
            d.makedirs()
            x.move(d)


def _fix_dir(x):
    log.debug('fixing examples dir name: %s', x)
    log.debug('new dir name: %s', x.parent / EXAMPLES)
    x.rename(x.parent / EXAMPLES)


def fix_examples_dir(lib_dir):
    """rename examples dir to ``examples``"""
    for x in lib_dir.dirs():
        if x.name.lower() == EXAMPLES:
            return
    for x in lib_dir.dirs():
        if x.name.lower() == EXAMPLES:
            _fix_dir(x)
            return
    for x in lib_dir.dirs():
        if 'example' in x.name.lower():
            _fix_dir(x)
            return
    for x in lib_dir.dirs():
        if len(files_multi_pattern(x, INO_PATTERNS)):
            _fix_dir(x)
            return

WPROGRAM = '''
///////////////////////////////////////
// inserted by confduino
//
#if defined(ARDUINO) && ARDUINO >= 100
#include "Arduino.h"
#else
#include "WProgram.h"
#include "pins_arduino.h"
#endif
//
// end
///////////////////////////////////////

'''

OLD_INCLUDES = '''
pins_arduino
wprogram
wiring
'''.strip().split()


def fix_wprogram_in_file(filename):
    """"""
    filename = path(filename)
    change = False
    lines = filename.lines()

    def tester(line):
        line = line.lower()
        for i in OLD_INCLUDES:
            if '"%s.h"' % i in line:
                return True
            if '<%s.h>' % i in line:
                return True

    for i in range(len(lines)):
        if tester(lines[i]):
            change = True
            lines[i] = '// %s // disabled by confduino' % lines[i].strip()

    if change:
        filename.write_lines(lines)
    s = WPROGRAM + filename.text()
    filename.write_text(s)
#        print '\n'.join(lines)


def fix_wprogram_in_files(directory):
    """"""
    files = [x for x in directory.walk('*.h')]
    files += [x for x in directory.walk('*.cpp')]
    for f in files:
        if '"arduino.h"' not in f.text().lower():
            fix_wprogram_in_file(f)


@entrypoint
def install_lib(url, replace_existing=False, fix_wprogram=True):
    """install library from web or local files system.

    :param url: web address or file path
    :param replace_existing: bool
    :rtype: None

    """
    d = tmpdir(tmpdir())
    f = download(url)
    Archive(f).extractall(d)

    clean_dir(d)
    d, src_dlib = find_lib_dir(d)
    move_examples(d, src_dlib)
    fix_examples_dir(src_dlib)
    if fix_wprogram:
        fix_wprogram_in_files(src_dlib)

    targ_dlib = libraries_dir() / src_dlib.name
    if targ_dlib.exists():
        log.debug('library already exists: %s', targ_dlib)
        if replace_existing:
            log.debug('remove %s', targ_dlib)
            targ_dlib.rmtree()
        else:
            raise ConfduinoError('library already exists:' + targ_dlib)

    log.debug('move %s -> %s', src_dlib, targ_dlib)
    src_dlib.move(targ_dlib)

    libraries_dir().copymode(targ_dlib)
    for x in targ_dlib.walk():
        libraries_dir().copymode(x)
    return targ_dlib.name
