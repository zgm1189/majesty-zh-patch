// libs3e_android.so 的 DT_INIT 桩：把 frida-gadget 拉进进程。
// STR_ADDR / GOT_DLOPEN 由链接器 --defsym 提供；
// 链接地址必须等于实际放置的 vaddr（0x3702C），adrp 的页差才对。

    .text
    .global _start
    .type _start, %function
_start:
    stp     x29, x30, [sp, #-16]!
    mov     x29, sp
    adrp    x0, STR_ADDR
    add     x0, x0, :lo12:STR_ADDR
    mov     w1, #1               // RTLD_LAZY
    adrp    x16, GOT_DLOPEN
    ldr     x17, [x16, :lo12:GOT_DLOPEN]
    blr     x17
    ldp     x29, x30, [sp], #16
    ret
    .size _start, .-_start
