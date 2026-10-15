start:
; Comment 1
; This is a comment block just to
; see if multiline comments will
; be ignored
xor r0 r0 r0
xor r1 r1 r1
xor r2 r2
middle: addi r1 r1 -2 ; Comment 2
addi r2 r2 $1A ;Comment 3
sub r0 r3 r1
lbs t0 r0 2
end:
brz middle