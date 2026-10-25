
from dataclasses import dataclass
from typing import Any, Callable
from enum import Enum
from abc import abstractmethod, ABCMeta
import os
import sys

LINEBREAKS = "\n\r"
WHITESPACE = " \t"
LINE_ESCAPE = "\\"
WHITESPACE_AND_LINEBREAKS = WHITESPACE + LINEBREAKS
COMMON_ESCAPES = {
	"0": "\0",
	"a": "\a",
	"b": "\b",
	"t": "\t",
	"n": "\n",
	"v": "\v",
	"f": "\f",
	"r": "\r",
}

# variant type
class Vtyp(Enum):
	GenericNumber = -2
	Nothing = -1
	Int = 0
	Float = 1
	String = 2
	Symbol = 3

class Lexer:
	def __init__(self, src: str, file: str) -> None:
		self.src = src
		self.file = file
		self.tokens: list[str] = []
		self.line_numbers: list[tuple[str, int]] = []

	def parse(self):
		is_in_string = False
		is_in_comment = False
		
		current = ""
		line_number = 1
		
		just_changed_line_number = False

		def next(p):
			if 0 <= p + 1 < len(self.src):
				return self.src[p + 1], p + 1
			return "", p
		
		i = 0
		while i < len(self.src):
			char = self.src[i]
			just_changed_line_number = False

			if char in LINEBREAKS:
				line_number += 1
				just_changed_line_number = True
				is_in_comment = False

			if (not is_in_string and not is_in_comment and char in WHITESPACE_AND_LINEBREAKS):
				if "\"" not in current:
					current = current.lower()

				if just_changed_line_number:
					line_number -= 1
				
				if is_in_comment:
					i += 1
					continue
				
				if len(current) > 0 and current not in LINE_ESCAPE:
					self.tokens.append(current)
					self.line_numbers.append((self.file, line_number))
					current = ""

				if just_changed_line_number:
					line_number += 1

				i += 1
				continue

			if char == "\\":
				flag, i = next(i)
				
				if flag in COMMON_ESCAPES:
					char = COMMON_ESCAPES[flag]

				elif flag == "x":
					x0, i = next(i)
					x1, i = next(i)

					try:
						char = chr(int(x0 + x1, base=16))
					except Exception:
						char = "x" + x0 + x1

				elif flag == "u":
					u0, i = next(i)
					u1, i = next(i)
					u2, i = next(i)
					u3, i = next(i)

					try:
						char = chr(int(u0 + u1 + u2 + u3, base=16))
					except Exception:
						char = "u" + u0 + u1 + u2 + u3

				elif flag == "U":
					u0, i = next(i)
					u1, i = next(i)
					u2, i = next(i)
					u3, i = next(i)
					u4, i = next(i)
					u5, i = next(i)
					u6, i = next(i)
					u7, i = next(i)

					try:
						char = chr(int(u0 + u1 + u2 + u3 + u4 + u5 + u6 + u7, base=16))
					except Exception:
						char = "U" + u0 + u1 + u2 + u3 + u4 + u5 + u6 + u7

				else:
					char = flag

			else:
				if char == "\"" and not is_in_comment:
					is_in_string = not is_in_string

				if char == "#" and not is_in_string:
					is_in_comment = True

			if not is_in_comment:
				current += char

			i += 1

		if len(current) > 0:
			self.tokens.append(current)
			self.line_numbers.append((self.file, line_number))


@dataclass
class Variant:
	typ: Vtyp
	val: Any = None


class LangExtension(metaclass=ABCMeta):
	@abstractmethod
	def register(self) -> dict[str, Callable]:
		"""
		all functions can call using `call` command<br>
		each `Callable` must `def name(lng: Lang) -> None`
		"""
		...


class Lang:
	def __init__(self, src: str, file: str) -> None:
		self.lexer = Lexer(src, file)

		self.stack: list[Variant] = []
		self.call_stack: list[int] = []
		self.mem: dict[int, Variant] = {}
		self.flags: dict[str, int] = {}
		self.constants: dict[str, Variant] = {}

		self.ptr = 0
		self.flag_register_phase = False
		self.terminate_run = False
		self.used_includes = []

		self.extensions: list[LangExtension] = []
		self.extension_calls: dict[str, Callable] = {}

		self.src = src
		self.file = file

	def error(self, message: str):
		clamped = max(0, min(self.ptr, len(self.lexer.line_numbers) - 1))
		
		if self.flag_register_phase:
			sys.stderr.write(f"[error] [registering flags] {message}.\n")
		else:
			sys.stderr.write(f"[error] {message}.\n")

		# calculate line number for stacktrace
		for i in range(len(self.call_stack) -1, -1, -1):
			if i == len(self.call_stack) - 1:
				line_token = clamped
			else:
				line_token = self.call_stack[i + 1]

			line_number = self.lexer.line_numbers[line_token]
			sys.stderr.write(f"  at '{line_number[0]}' line {line_number[1]} in function '{self.lexer.tokens[self.call_stack[i]]}'.\n")

		if len(self.call_stack) > 0:
			line_token = self.call_stack[0]
		else:
			line_token = clamped

		line_number = self.lexer.line_numbers[line_token]
		sys.stderr.write(f"  at '{line_number[0]}' line {line_number[1]}.")

		sys.stderr.flush()
		sys.exit(1)


	def get_mem_at(self, idx: int) -> Variant:
		return self.mem.get(idx, Variant(Vtyp.Nothing))

	def set_mem_at(self, idx: int, val: Variant):
		self.mem[idx] = val

	def push_to_stack(self, val: Variant):
		self.stack.append(val)

	def push_number_to_stack(self, val: Any):
		if isinstance(val, int):
			self.push_to_stack(Variant(Vtyp.Int, val))
		elif isinstance(val, float):
			self.push_to_stack(Variant(Vtyp.Float, val))
		else:
			self.error(f"'{val}' is not a valid number")

	def push_string_to_stack(self, val: Any):
		if isinstance(val, str):
			self.push_to_stack(Variant(Vtyp.String, val))
		else:
			self.error(f"'{val}' is not a valid string")

	def push_symbol_to_stack(self, val: Any):
		if isinstance(val, str):
			self.push_to_stack(Variant(Vtyp.Symbol, val))
		else:
			self.error(f"'{val}' is not a valid symbol")

	def pop_from_stack(self) -> Variant:
		if len(self.stack) <= 0:
			self.error("stack is empty")
		return self.stack.pop()

	def get_flag_position(self, name: str) -> int:
		if name not in self.flags:
			self.error(f"no flag named '{name}'")
		return self.flags[name]


	def strcmp(self, a: str, b: str):
		min_len = min(len(a), len(b))
		for i in range(min_len):
			if a[i] != b[i]:
				return ord(a[i]) - ord(b[i])
		return len(a) - len(b)


	def next_value(self) -> Variant:
		self.ptr += 1
		if self.ptr >= len(self.lexer.tokens):
			self.error("unexpected EOF")

		tok = self.lexer.tokens[self.ptr]

		if tok == "mem":
			addr = self.expect_next_type(Vtyp.Int)
			return self.get_mem_at(addr.val)

		if tok == "stack":
			return self.pop_from_stack()
		
		elif tok == "int":
			return self.expect_next_type(Vtyp.Int)
		
		elif tok == "float":
			return self.expect_next_type(Vtyp.Float)

		elif tok == "hex":
			raw = self.next_raw_value()
			try:
				return Variant(Vtyp.Int, int(raw, base=16))
			except Exception:
				return Variant(Vtyp.Symbol, tok)

		if tok in self.constants:
			return self.constants[tok]

		if tok[0] == "\"":
			return Variant(Vtyp.String, tok[1:-1])

		elif "." in tok:
			try:
				return Variant(Vtyp.Float, float(tok))
			except Exception:
				return Variant(Vtyp.Symbol, tok)

		else:
			try:
				return Variant(Vtyp.Int, int(tok))
			except Exception:
				return Variant(Vtyp.Symbol, tok)

	def expect_next_type(self, typ: Vtyp) -> Variant:
		val = self.next_value()

		if typ == Vtyp.GenericNumber:
			if val.typ == Vtyp.Int or val.typ == Vtyp.Float:
				return val

		if val.typ != typ:
			self.error(f"expected {typ}, got {val.typ} intead")

		return val

	def expect_next_symbol_to_be(self, txt: str):
		val = self.expect_next_type(Vtyp.Symbol)
		if val.val != txt:
			self.error(f"expected '{txt}', got '{val.val}' instead")
		
		return val

	def expect_type_from_stack(self, typ: Vtyp) -> Variant:
		val = self.pop_from_stack()

		if typ == Vtyp.GenericNumber:
			if val.typ == Vtyp.Int or val.typ == Vtyp.Float:
				return val

		if val.typ != typ:
			self.error(f"expected {typ} from stack top, got {val.typ} intead")

		return val

	def next_raw_value(self):
		self.ptr += 1
		if self.ptr >= len(self.lexer.tokens):
			self.error("unexpected EOF")
		
		return self.lexer.tokens[self.ptr]


	def execute_command(self, command: str):
		match command:
			case "move":
				val = self.next_value()
				self.expect_next_symbol_to_be("to")

				# solve for address
				addr0 = self.next_raw_value()

				if addr0 == "mem":
					addr1 = self.expect_next_type(Vtyp.Int)
					self.set_mem_at(addr1.val, val)

				elif addr0 == "stack":
					self.push_to_stack(val)

				else:
					self.error(f"'{addr0}' is not a valid address")


			case "call":
				fn_name = self.next_raw_value()

				# safety
				if len(self.call_stack) > 1000:
					self.error("stack overflow")
				
				# kernel functions
				if fn_name == "_println":
					val = self.pop_from_stack()
					print(val.val if val.val is not None else "")

				elif fn_name == "_print":
					val = self.pop_from_stack()
					print(val.val if val.val is not None else "", end="")

				elif fn_name == "_printerr":
					val = self.pop_from_stack()
					sys.stderr.write(val.val if val.val is not None else "")

				elif fn_name == "_input":
					val = input()
					self.push_string_to_stack(val)

				elif fn_name == "_getchar":
					val = sys.stdin.read(1)
					self.push_string_to_stack(val)

				elif fn_name == "_typeof":
					val = self.pop_from_stack()
					self.push_symbol_to_stack(str(val.typ))

				elif fn_name in self.extension_calls:
					self.extension_calls[fn_name](self)

				else:
					target_position = self.get_flag_position(fn_name)
					
					self.call_stack.append(self.ptr)
					self.ptr = target_position


			case "flag":
				self.next_raw_value()


			case "jump" | "test":
				jump_condition_type = self.expect_next_type(Vtyp.Symbol).val
				flag_name = self.next_raw_value()
				target_position = self.get_flag_position(flag_name)

				condition = 0
				if jump_condition_type != "to":
					condition = self.expect_type_from_stack(Vtyp.GenericNumber).val
					if command == "test":
						self.push_number_to_stack(condition)

				if jump_condition_type == "to":
					self.ptr = target_position

				elif jump_condition_type == "negative":
					if condition < 0:
						self.ptr = target_position

				elif jump_condition_type == "positive":
					if condition > 0:
						self.ptr = target_position

				elif jump_condition_type == "zero":
					if condition == 0:
						self.ptr = target_position

				elif jump_condition_type == "nonzero":
					if condition != 0:
						self.ptr = target_position

				else:
					self.error("jump condition must be 'negetive', 'positive', 'zero'. or 'to' for unconditional jumps")


			case "return":
				if len(self.call_stack) <= 0:
					self.error("cannot return on top level codes")

				self.ptr = self.call_stack.pop()


			case "halt":
				self.terminate_run = True


			case "perform":
				operation = self.expect_next_type(Vtyp.Symbol).val
				b = self.expect_type_from_stack(Vtyp.GenericNumber).val

				a = 0
				if operation != "bitnot":
					a = self.expect_type_from_stack(Vtyp.GenericNumber).val

				if operation == "addition":
					self.push_number_to_stack(a + b)

				elif operation == "subtraction":
					self.push_number_to_stack(a - b)

				elif operation == "multiplication":
					self.push_number_to_stack(a * b)

				elif operation == "floordivision":
					if b == 0:
						self.error("cannot divide by 0")
					self.push_number_to_stack(a // b)

				elif operation == "truedivision":
					if b == 0:
						self.error("cannot divide by 0")
					self.push_number_to_stack(a / b)

				elif operation == "modulo":
					if b == 0:
						self.error("cannot divide by 0")
					self.push_number_to_stack(a % b)

				elif operation == "bitand":
					self.push_number_to_stack(a & b)

				elif operation == "bitor":
					self.push_number_to_stack(a | b)

				elif operation == "bitnot":
					self.push_number_to_stack(~b)

				elif operation == "bitxor":
					self.push_number_to_stack(a ^ b)

				elif operation == "bitlshift":
					self.push_number_to_stack(a << b)

				elif operation == "bitrshift":
					self.push_number_to_stack(a >> b)

				else:
					self.error(f"unknow operation '{operation}'")


			case "strop":
				operation = self.expect_next_type(Vtyp.Symbol).val

				s = ""
				if operation != "tochar":
					s = self.expect_type_from_stack(Vtyp.String).val

				if operation == "compare":
					other = self.expect_type_from_stack(Vtyp.String)
					self.push_number_to_stack(self.strcmp(s, other.val))

				elif operation == "slice":
					index = self.expect_type_from_stack(Vtyp.Int).val
					if index < 0 or index >= len(s):
						self.error(f"slice index {index} out of range [0, {len(s)})")
					self.push_string_to_stack(s[index])

				elif operation == "tocode":
					if len(s) != 1:
						self.error(f"expected length 1 string for converting, got length {len(s)} instead")
					self.push_number_to_stack(ord(s))

				elif operation == "tochar":
					c = self.expect_type_from_stack(Vtyp.Int)
					try:
						self.push_string_to_stack(chr(c.val))
					except Exception:
						self.error(f"{c} is not a valid unicode code point value")

				elif operation == "concat":
					other = self.expect_type_from_stack(Vtyp.String)
					self.push_string_to_stack(other.val + s)

				elif operation == "length":
					self.push_number_to_stack(len(s))

				else:
					self.error(f"unknow string operation '{operation}'")


			case "convert":
				self.expect_next_symbol_to_be("to")
				operation = self.expect_next_type(Vtyp.Symbol).val

				if operation == "integer":
					val = self.pop_from_stack().val
					try:
						self.push_number_to_stack(int(val))
					except Exception:
						self.error(f"'{val}' is not a valid int")

				elif operation == "floating":
					val = self.pop_from_stack().val
					try:
						self.push_number_to_stack(float(val))
					except Exception:
						self.error(f"'{val}' is not a valid float")

				elif operation == "string":
					val = self.pop_from_stack().val
					try:
						self.push_string_to_stack(str(val))
					except Exception:
						self.error(f"'{val}' is not a valid string")

				elif operation == "symbol":
					val = self.pop_from_stack().val
					try:
						self.push_symbol_to_stack(str(val))
					except Exception:
						self.error(f"'{val}' is not a valid symbol")

				else:
					self.error(f"unknow convert operation '{operation}'")


			case "stackop":
				operation = self.expect_next_type(Vtyp.Symbol).val

				if operation == "duplicate":
					val = self.pop_from_stack()
					self.push_to_stack(val)
					self.push_to_stack(val)

				elif operation == "swap":
					first = self.pop_from_stack()
					second = self.pop_from_stack()

					self.push_to_stack(first)
					self.push_to_stack(second)

				elif operation == "drop":
					self.pop_from_stack()

				elif operation == "nontopduplicate":
					first = self.pop_from_stack()
					second = self.pop_from_stack()

					self.push_to_stack(second)
					self.push_to_stack(first)
					self.push_to_stack(second)

				else:
					self.error(f"unknow stack operation '{operation}'")


			case "constant":
				self.next_raw_value()
				self.next_raw_value()
				self.next_value()


			case "debug":
				operation = self.expect_next_type(Vtyp.Symbol).val

				if operation == "callstack":
					print(f"[callstack] {self.call_stack}")

				elif operation == "datastack":
					print(f"[stack] {self.stack}")

				elif operation == "constants":
					print(f"[constants] {self.constants}")

				elif operation == "tokens":
					print(f"[tokens] {self.lexer.tokens}")

				else:
					self.error(f"unknow debug operation '{operation}'")


			case "exit":
				code = self.expect_type_from_stack(Vtyp.Int)
				sys.exit(code.val)


			case _:
				self.error(f"unknow command '{command}'")


	def register_flag(self, command: str):
		if command == "flag":
			id = self.next_raw_value()
			self.flags[id] = self.ptr

		elif command == "constant":
			name = self.next_raw_value()
			
			between = self.next_raw_value()
			if between != "is":
				self.error(f"expected 'is', got '{between}' instead")

			value = self.next_value()
			self.constants[name] = value

	def register_function(self, command: str):
		if command == "function":
			self.lexer.tokens[self.ptr] = "jump"
			line_number = self.lexer.line_numbers[self.ptr]

			name = self.next_raw_value()
			self.lexer.tokens.insert(self.ptr, "flag")
			self.lexer.tokens.insert(self.ptr, f"{name} END")
			self.lexer.tokens.insert(self.ptr, "to")

			self.lexer.line_numbers.insert(self.ptr, line_number)
			self.lexer.line_numbers.insert(self.ptr, line_number)
			self.lexer.line_numbers.insert(self.ptr, line_number)

		elif command == "endfunction":
			self.lexer.tokens[self.ptr] = "return"
			line_number = self.lexer.line_numbers[self.ptr]

			name = self.next_raw_value()
			self.lexer.tokens[self.ptr] = f"{name} END"
			self.lexer.tokens.insert(self.ptr, "flag")

			self.lexer.line_numbers.insert(self.ptr, line_number)

	def register_include(self, command: str):
		if command == "include":
			path = self.expect_next_type(Vtyp.String).val
			path = os.path.abspath(path)
			
			if path in self.used_includes:
				self.lexer.tokens[self.ptr - 1 : self.ptr + 1] = []
				self.lexer.line_numbers[self.ptr - 1 : self.ptr + 1] = []

				self.ptr = -1  # make sure catch all includes
				return

			self.used_includes.append(path)

			try:
				with open(path, encoding="utf-8") as file:
					ctx = file.read()
			except Exception as e:
				self.error(f"cannot open include file {path}: {e}")

			sub_lexer = Lexer(ctx, path)
			sub_lexer.parse()

			try:
				self.lexer.tokens[self.ptr - 1 : self.ptr + 1] = sub_lexer.tokens
				self.lexer.line_numbers[self.ptr - 1 : self.ptr + 1] = sub_lexer.line_numbers

				self.ptr = -1  # make sure catch all includes
			except Exception:
				self.error("error while solving include")


	def parse_and_run(self):
		self.lexer.tokens = []
		self.lexer.line_numbers = []
		self.lexer.parse()

		def go_through(callback_fn):	
			while True:
				callback_fn(self.lexer.tokens[self.ptr])

				if self.terminate_run:
					return

				self.ptr += 1
				if self.ptr >= len(self.lexer.tokens):
					return

		for ext in self.extensions:
			methods = ext.register()
			self.extension_calls.update(methods)

		self.constants = {}
		self.flags = {}
		self.mem = {}
		self.stack = []
		self.call_stack = []

		self.flag_register_phase = True

		self.used_includes = []
		self.ptr = 0
		go_through(self.register_include)

		self.ptr = 0
		go_through(self.register_function)
		
		self.ptr = 0
		go_through(self.register_flag)
		
		self.flag_register_phase = False
		
		self.ptr = 0
		go_through(self.execute_command)


	def add_extension(self, extension: LangExtension):
		self.extensions.append(extension)
