from __future__ import division
from confduino.boardinstall import install_board
from confduino.util import AutoBunch
from entrypoint2 import entrypoint

TEMPL_NAME = '{mcu}@{f_cpu} prog:{upload}'
TEMPL_ID = '{mcu}_{f_cpu}'


def format_freq(f):
    if f >= 1000000:
        f = f / 1000000.0
        suffix = 'MHz'
    elif f >= 1000:
        f = f / 1000.0
        suffix = 'kHz'
    else:
        suffix = 'Hz'
    f = ('%f' % f).rstrip('0').rstrip('.')
    return f + '' + suffix


@entrypoint
def main(
            upload='usbasp',
            core='arduino',
            replace_existing=True,
            ):
    'install custom boards'

    def install(mcu, f_cpu):
        board = AutoBunch()
        board.name = TEMPL_NAME.format(mcu=mcu,
                                       f_cpu=format_freq(f_cpu),
                                       upload=upload)
        board_id = TEMPL_ID.format(mcu=mcu,
                                       f_cpu=(f_cpu),
                                       upload=upload)

        board.upload.using = upload
        board.upload.maximum_size = 8 * 1024

        board.build.mcu = mcu
        board.build.f_cpu = str(f_cpu) + 'L'
        board.build.core = core

        install_board(board_id, board, replace_existing=replace_existing)

    install('atmega8', 1000000)
    install('atmega8', 12000000)
    install('atmega88', 1000000)
    install('atmega88', 12000000)
    install('atmega88', 20000000)