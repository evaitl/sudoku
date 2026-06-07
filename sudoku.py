#!/usr/bin/env python3

known={}
possibles={}

known[1,1,1]=3
known[2,1,1]=1
known[3,1,1]=9
known[1,4,2]=4
known[1,6,2]=9
known[2,6,2]=8
known[3,5,2]=1
known[3,8,3]=2
known[4,4,5]=3
known[5,1,4]=2
known[5,2,4]=3
known[5,6,5]=1
known[5,8,6]=8
known[5,9,6]=5
known[6,3,4]=5
known[6,4,5]=9
known[8,2,7]=7
known[8,3,7]=9
known[8,7,9]=3
known[9,3,7]=8
known[9,6,8]=2
known[9,9,9]=6

for r,c,m in known.keys():
    assert m == ((r-1)//3)*3 + (c-1)//3 +1

for r in range(1,10):
    for c in range(1,10):
        m=((r-1)//3)*3 + (c-1)//3 +1
        if known.get((r,c,m)):
            possibles[r,c,m]=set()
        else:
            possibles[r,c,m]=set(range(1,10))-set(v for k,v in known.items() if k[0]==r or k[1]==c or k[2]==m)

print(f'{possibles[1,1,1]=} {possibles[1,2,1]=}')


def add_known(k,v):
    """Found one

    clear possible. Subtract value from r,c,m possible sets. Set known.
    """
    possibles[k]=set()
    known[k]=v
    r,c,m=k
    # Set in r
    for c1 in range(1,10):
        m1=(r-1)//3*3+(c1-1)//3+1
        possibles[r,c1,m1]-=set([v])
    # Set in c
    for r1 in range(1,10):
        m1=(r1-1)//3*3+(c-1)//3+1
        possibles[r1,c,m1]-=set([v])
    # Set in m
    for r1 in range(1,4):
        for c1 in range(1,4):
            possibles[r1+(m-1)//3*3, c1, m]-=set([v])

def find_singles():
    for k,v in possibles.items():
        if len(v)==1:
            add_known(k,v.pop())


def solved():
    return len(known)==81

def find_unaries():
    """Only one in a row, column, or m.

    This is the only find that 
    """
    find_unary_rows()
    find_unary_columns()
    find_unary_ms()

def find_exclusives():
    """For a given m,  all k are in a row, column or exclusive to the m. 
    """
    pass
def find_binaries():
    """
    Find binaries in rows, columns, and ms. 
    """
    pass
def find_trips():
    """
    Find trips in rows, columns, or ms. 
    """
    pass
def find_quads():
    """
    Find quads in rows, columns, or ms. 
    """
    pass

while not solved():
    find_singles()
    find_unaries()
    find_exclusives()
    find_binaries()
    find_trips()
    find_quads()
    
