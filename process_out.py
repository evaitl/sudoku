#!/usr/bin/env python3


with open("out.txt") as f:
    for line in f:
        line=line.strip()
        if not line.startswith('o='):
            continue
        if not '.' in line:
            continue
        print(f'{line.strip()[2:]}')
