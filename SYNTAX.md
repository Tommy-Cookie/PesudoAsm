
- `move`:
  - `move <value> to <addr>`
  - addressing: `mem` and `stack`, can nest
  - value: `mem`, `stack`, `int`, `float` and `hex`

- `call`:
  - `call <name>`
  - jump to flag `name` and start execute
  - push to call stack

- `flag`:
  - `flag <name>`
  - defines a flag
  - **runs at parsing state**

- `jump` / `test`:
  - `jump|test <type> <target>`
  - braching
  - jump to `target` if `type` evaluated true
  - `test` wont pop the top of stack

- `return`:
  - return from a "function" (call stack)

- `halt`:
  - stops the program

- `perform`:
  - `perform <operation>`
  - operations: `addition`, `subtraction`, `multiplication`, `floordivision` `truedivision`, `modulo`, `bitand`, `bitor`, `bitnot`, `bitxor`, `bitlshift`, `bitrshift`
  - pops from stack
  - result push into stack

- `strop`:
  - `strop <operation>`
  - operations: `compare`, `slice`, `tocode`, `tochar`, `concat`, `length`

- `convert`:
  - `convert to <target>`
  - convert type to `target`
  - pop from stack and push to stack

- `stackop`:
  - `stackop <operation>`
  - operations: `duplicate`, `swap`, `drop`, `nontopduplicate`

- `constant`:
  - `constant <name> is <value>`
  - defines a constant value
  - **runs at parsing state**

- `debug`:
  - `debug <operation>`
  - operations: `callstack`, `datastack`, `constants`, `tokens`
  - each prints the value

- `exit`:
  - `exit <code>`
  - stops the program with an exit code

- `function` / `endfunction`
  - `function|endfunction <name>`
  - defines a "function"
  - runs at parsing state
  - expand to `jump to <name END> flag <name> {body} return flag <name END>`

here is a working "hello world" example
```
move "hello world" to stack
call _println
```

here is another example computes 1 + 2 and prints it
```
move 1 to stack
move 2 to stack
perform addition
call _println
```
