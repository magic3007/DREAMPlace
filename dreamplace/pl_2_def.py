import os
import sys
import subprocess

if len(sys.argv) != 3:
    print(f"Usage: python {os.path.basename(sys.argv[0])} <output_pl> <input_def>")
    sys.exit(1)

output_pl = sys.argv[1]
input_def = sys.argv[2]
output_def = output_pl.replace('.pl', '.def')

command = f"sed -r 's/MYRBKT/]/g; s/MYLBKT/[/g' {output_pl} > {output_pl}.org"
subprocess.run(command, shell=True, check=True)

cell_2_write = {}
with open(f'{output_pl}.org', 'r') as r:
    while 1:
        line = r.readline()
        if not line: break
        line = line.strip().split()
        if len(line) == 5:
            cellName = line[0]
            cell_2_write[cellName] = " + PLACED ( {} {} ) {}\n".format(line[1], line[2], line[-1])

w = open(output_def, 'w')

with open(input_def, 'r') as r:
    read_cell = False
    while 1:
        line = r.readline()
        if not line: break
        if line.startswith('COMPONENTS'):
            read_cell = True
        elif read_cell and line.startswith('-'):
            if not '+ FIXED' in line:
                line = line.strip()
                if '+ PLACED' in line:
                    line = line.split('+ PLACED')[0]
                cellName = line.split()[1].replace('\\', '')
                cellName.strip()
                assert cellName in cell_2_write, f"cannot find: {cellName}"
                line += cell_2_write[cellName]
        elif line.startswith('END COMPONENTS'):
            read_cell = False
        w.write(line)
w.close()