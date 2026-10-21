init:
    xor r0 r0 r0
    xor r1 r1 r1
    xor r2 r2 r2
    xor r3 r3 r3
    xor r4 r4 r4
    xor r5 r5 r5
    xor r6 r6 r6
    xor r7 r7 r7
    xor ra ra ra
    xor a0 a0 a0
    xor a1 a1 a1
    xor a2 a2 a2
    xor v0 v0 v0
    xor v1 v1 v1
    xor sp sp sp
    xor sf sf sf
    xor t0 t0 t0
    xor t1 t1 t1
    xor t2 t2 t2
    xor t3 t3 t3
    xor t4 t4 t4
    xor t5 t5 t5
    xor t6 t6 t6
    xor t7 t7 t7
    addi t0 t0 $6000
    lbs t0 t0 2         ; $6000 << 2 = $18000
    jala t0             ; jmp to general memory
putc:                   ; void putc(char out_char)
    xor t0 t0 t0
    xor t1 t1 t1
    xor t2 t2 t2
    xor t3 t3 t3
    addi t2 t2 1        ; int ready = 1
    addi t0 t0 $4000    ; char* char_reg = $4000
    addi t1 t1 $4001    ; int* ready_reg = $4001
    sbi t0 a0           ; char_reg = out_char
    sbi t1 t2           ; ready_reg = 1
 wait:
    ; bool is_ready = 1
    ; while (ready_reg == 1){
    ;   is_ready = *ready_reg;
    ;   is_ready = is_ready | is_ready
    ; }
    lbi t3 t1
    or t3 t3 t3
    brz exit
    jmp wait
exit:
    reti
getc:
    reti
