import sys

import board

# CircuitPython throws SyntaxError for multiline f-strings - either use single line or concatenation
print(f"\nRunning on {board.board_id} ({sys.platform}), {sys.implementation.name} " +
      f"{sys.version}/{'.'.join(map(str, sys.implementation.version))}, mpy {sys.implementation.mpy}")
