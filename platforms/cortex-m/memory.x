/* NUCLEO-F401RE: 512 KiB Flash, 96 KiB RAM. Reserve 16 KiB stack. */
MEMORY {
 FLASH : ORIGIN = 0x08000000, LENGTH = 512K
 RAM : ORIGIN = 0x20000000, LENGTH = 96K
}
_stack_start = ORIGIN(RAM) + LENGTH(RAM);
_stack_end = _stack_start - 16K;
ASSERT(__euninit <= _stack_end, "Static RAM overlaps reserved stack");
