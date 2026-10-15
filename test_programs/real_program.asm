; Sample test program for LC32 assembler
xor r0 r0 r0 ; Loop Counter
xor r1 r1 r1 ; Loop Guard
xor r2 r2 r2 ; Value to increment
xor t0 t0 t0 ; Temporary for holding result of guard - counter
addi r1 r1 3
addi r2 r2 $01
loop:
addi r2 r2 1  ; increment r2 by 1
addi r0 r0 1  ; First, increment loop counter by 1
sub t0 r1 r0 ; Second, subtract loop counter from loop guard
brz continue
jmp loop
continue:
halt
