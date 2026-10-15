"""
Tokens:

OP_NO_OPERAND     = "NOP" | "HALT" | "RET" | "RETI"
OPR_ONE_OPERAND   = "JALA"
OPR_TWO_OPERAND   = "NOT" | "LBI" | "LWI" | "SBI" | "SWI"
OPR_THREE_OPERAND = "ADD" | "AND" | "DIV" | "LBS" | "MULT" | "OR" | "RBS" | "SUB" | "XOR"
OPI_THREE_OPERAND = "ADDI" | "ANDI" | "ORI" | "SUBI" | "XORI"
OPI_TWO_OPERAND   = "LB" | "LW" | "SB" | "SW"
OP_JUMP           = "BRN" | "BRP" | "BRZ" | "JAL" | "JMP" | "INTER"
CHAR              = a..z  | A..Z
DIGIT             = 0..9
HEX_DIGIT         = DIGIT | a..f | A..F
REGISTER          = (a, r, s, t, v) DIGIT {DIGIT}


Grammar:

Program          = Instruction_list
Instruction_list = (DIRECTIVE | LABEL | Instruction) {DIRECTIVE | LABEL | Instruction}
Instruction      = ROpcode | IOpcode | JOpcode | OP_NO_OPERAND
ROpocde          = OPR_ONE_OPERAND symbol | OPR_TWO_OPERAND symbol symbol | OPR_THREE_OPERAND symbol symbol symbol
IOpcode          = OPI_TWO_OPERAND symbol (HEX_NUM | DEC_NUM) | OPI_THREE_OPERAND symbol symbol (HEX_NUM | DEC_NUM)
JOpcode          = OP_JUMP (label | HEX_HUM | DEC_NUM)
dest             = symbol
src              = symbol
trgt             = symbol
imm16            = hex_num | dec_num
offset26         = hex_num | dec_num
directive        = .symbol
label            = symbol:
hex_num          = $HEX_DIGIT {HEX_DIGIT}
dec_num          = DIGIT {DIGIT}
symbol           = CHAR {CHAR | DIGIT}
"""
import struct
import sys
from dataclasses import dataclass
from enum import Enum, auto
from typing import NamedTuple, Optional
import traceback
import argparse

PARSER = argparse.ArgumentParser(description="Assembler for the LC32")
PARSER.add_argument("filename", help="Assembly file to assemble")
PARSER.add_argument("-d", "--debug", action="store_true", help="Print debugging output")
PARSER.add_argument("-x", "--hexdump", action="store_true", help="Show hex dump of executable")
PARSER.add_argument("-o", "--output", help="Path to outputfile")
ARGS = PARSER.parse_args()

"""AI CODE START"""


class TokenType(Enum):
    END_OF_FILE = auto()

    # Opcodes
    OP_NO_OPERAND = auto()
    OPR_ONE_OPERAND = auto()
    OPR_TWO_OPERAND = auto()
    OPR_THREE_OPERAND = auto()
    OPI_TWO_OPERAND = auto()
    OPI_THREE_OPERAND = auto()
    OP_JUMP = auto()

    # Other tokens
    HEX_NUM = auto()
    DEC_NUM = auto()
    SYMBOL = auto()
    LABEL = auto()
    DIRECTIVE = auto()


class Token(NamedTuple):
    lexeme: str
    type: TokenType
    line_no: int


# Reserved keywords, one list per instruction shape
OP_NO_OPERAND_KEYWORDS = ["NOP", "HALT", "RET", "RETI"]
OPR_ONE_OPERAND_KEYWORDS = ["JALA"]
OPR_TWO_OPERAND_KEYWORDS = ["NOT", "LBI", "LWI", "SBI", "SWI"]
OPR_THREE_OPERAND_KEYWORDS = ["ADD", "AND", "DIV", "LBS", "MULT", "OR", "RBS", "SUB", "XOR"]
OPI_TWO_OPERAND_KEYWORDS = ["LB", "LW", "SB", "SW"]
OPI_THREE_OPERAND_KEYWORDS = ["ADDI", "ANDI", "ORI", "SUBI", "XORI"]
OP_JUMP_KEYWORDS = ["BRN", "BRP", "BRZ", "JAL", "JMP", "INTER"]

KEYWORD_TABLE = {}
for words, type in [
    (OP_NO_OPERAND_KEYWORDS, TokenType.OP_NO_OPERAND),
    (OPR_ONE_OPERAND_KEYWORDS, TokenType.OPR_ONE_OPERAND),
    (OPR_TWO_OPERAND_KEYWORDS, TokenType.OPR_TWO_OPERAND),
    (OPR_THREE_OPERAND_KEYWORDS, TokenType.OPR_THREE_OPERAND),
    (OPI_TWO_OPERAND_KEYWORDS, TokenType.OPI_TWO_OPERAND),
    (OPI_THREE_OPERAND_KEYWORDS, TokenType.OPI_THREE_OPERAND),
    (OP_JUMP_KEYWORDS, TokenType.OP_JUMP),
]:
    for w in words:
        KEYWORD_TABLE[w] = type


def classify_symbol(lexeme: str) -> TokenType:
    """Return the opcode token type if lexeme is reserved, else SYMBOL."""
    return KEYWORD_TABLE.get(lexeme.upper(), TokenType.SYMBOL)


INSTRUCTION_FORMATS = {
    "NOP": "R",
    "ADD": "R",
    "ADDI": "I",
    "AND": "R",
    "ANDI": "I",
    "BRN": "J",
    "BRP": "J",
    "BRZ": "J",
    "DIV": "R",
    "JAL": "J",
    "JMP": "J",
    "JAlA": "R",
    "LB": "I",
    "LBI": "I",
    "LBS": "R",
    "LW": "I",
    "LWI": "I",
    "MULT": "R",
    "NOT": "R",
    "OR": "R",
    "ORI": "I",
    "RBS": "R",
    "RET": "J",
    "SB": "I",
    "SBI": "I",
    "SUB": "R",
    "SUBI": "I",
    "SW": "I",
    "SWI": "I",
    "INTER": "J",
    "XOR": "R",
    "XORI": "I",
    "HALT": "R",
    "RETI": "J",
}

REGISTERS = {
    "R0": 0,
    "R1": 1,
    "R2": 2,
    "R3": 3,
    "R4": 4,
    "R5": 5,
    "R6": 6,
    "R7": 7,
    "RA": 8,
    "A0": 9,
    "A1": 10,
    "A2": 11,
    "V0": 12,
    "V1": 13,
    "SP": 14,
    "SF": 15,
    "T0": 16,
    "T1": 17,
    "T2": 18,
    "T3": 19,
    "T4": 20,
    "T5": 21,
    "T6": 22,
    "T7": 23,
}

OPCODES = {
    'NOP': 0,
    'ADD': 1,
    'ADDI': 2,
    'AND': 3,
    'ANDI': 4,
    'BRN': 5,
    'BRP': 6,
    'BRZ': 7,
    'DIV': 8,
    'JAL': 9,
    'JMP': 10,
    'JALA': 11,
    'LB': 12,
    'LBI': 13,
    'LBS': 14,
    'LW': 15,
    'LWI': 16,
    'MULT': 17,
    'NOT': 18,
    'OR': 19,
    'ORI': 20,
    'RBS': 21,
    'RET': 22,
    'SB': 23,
    'SBI': 24,
    'SUB': 25,
    'SUBI': 26,
    'SW': 27,
    'SWI': 28,
    'INTER': 29,
    'XOR': 30,
    'XORI': 31,
    'HALT': 32,
    'RETI': 33,
}


def encode_rtype(opcode, dest, src, trgt, shamt):
    """
    R-type format:
    **OPCODE** [31-26: 6 bits] | **DEST** [25-21: 5 bits] | **SRC** [21-16: 5 bits] | **TRGT** [15-11: 5 bits] |**SHMAT** [10-6: 5 bits] | **Unused** [5-0: 6 bits]
    """
    if opcode == 14 or opcode == 21:
        instruction = (opcode << 26) | (dest << 21) | (src << 16) | (trgt << 11)
    else:
        trgt = 0
        instruction = (opcode << 26) | (dest << 21) | (src << 16) | (trgt << 11) | (shamt << 6)
    return instruction & 0xFFFFFFFF


def encode_itype(opcode, dest, src, imm16):
    """
    I-type format:
    **OPCODE** [31-26: 6 bits] | **DEST** [25-21: 5 bits] | **SRC** [20-16: 5 bits] | **IMM-17** [16-0: 17 bits]
    """
    instruction = (opcode << 26) | (dest << 21) | (src << 17) | (imm16 & 0x1FFFF)
    return instruction & 0xFFFFFFFF


def encode_jtype(opcode, offset26):
    """
    J-type format:
    [opcode:6][offset26:26]
    Bits: 31-26  25-0
    """
    instruction = (opcode << 26) | (offset26 & 0x3FFFFFF)
    return instruction & 0xFFFFFFFF


def write_uint32_to_buffer(buffer, offset, value):
    """
    Write a 32-bit unsigned integer to a byte buffer in little-endian format.

    Args:
        buffer: bytearray to write to
        offset: byte offset in the buffer
        value: 32-bit unsigned integer value
    """
    buffer[offset:offset + 4] = struct.pack('<I', value & 0xFFFFFFFF)


def print_word_hexdump(buffer, start_offset, end_offset):
    """
    Print a 4-byte-per-row hexdump of the buffer, reading each row as a
    little-endian uint32_t (matching memoryController::readWord's byte assembly), so the
    printed value is exactly what the CPU will decode -- no manual byte
    reversal needed to compare against expected instruction values.

    Equivalent to: hexdump -e '"%08_ax: " 1/4 "%08x" "\\n"' dummy_file.bin
    """
    for offset in range(start_offset, end_offset, 4):
        word = struct.unpack_from('<I', buffer, offset)[0]
        print(f"{offset:08x}: {word:08x}")


"""AI CODE END"""


class MissingErrorArgument(Exception):
    def __init__(self, msg):
        self.msg = msg
        super().__init__(self.msg)


class TooManyArguments(Exception):
    def __init__(self, msg):
        self.msg = msg
        super().__init__(self.msg)


def syntax_error(token, expected=None, msg=None):
    """
    For bad syntax in the input program
    """
    print("SYNTAX ERROR: ", end='')
    if expected is None and msg is not None:
        print(msg)
    elif msg is None and expected is not None:
        print(
            f"Syntax error on line {token.line_no}: '{token.lexeme}'\nExpected {expected}, but got {token.type} instead.")

    elif msg and expected:
        raise TooManyArguments("Cannot supply both a msg and an expected token")
    elif msg is None and expected is None:
        raise MissingErrorArgument("Must supply either a msg or an expected token")
    if ARGS.debug:
        traceback.print_stack()
    sys.exit(5)


def parser_error(line_no, msg):
    """
    For when parser itself fails
    """
    print(f"Parser error while parsing line {line_no}: {msg}")
    if ARGS.debug:
        traceback.print_stack()
    sys.exit(6)


def assembler_error(instruction, msg):
    """
    For when the assembling step breaks
    """
    print(f"Error while assembling {instruction.opcode} instruction: {msg}")
    if ARGS.debug:
        traceback.print_stack()
    sys.exit(7)


def lexical_analysis(lines: list):
    """
    1.) Split each line by space
    2.) loop through all lines
        a.) Loop through each token
        b.) If token starts with '.' -> DIRECTIVE
        c.) If token ends with ':' -> LABEL
        d.) If token starts with '$' -> HEX_NUM
        e.) If token numeric -> NUM
        d.) else SYMBOL
    """
    tokens = []
    symbol_table = {}
    line_no = 1
    for line in [line.split() for line in lines]:
        for lexeme in line:
            if lexeme[0] == '.':
                # Execute directive
                break
            elif lexeme[0] == ';':
                break
            elif lexeme[-1] == ':':
                label = lexeme.strip(':')
                if symbol_table.get(label):
                    syntax_error(line_no, msg=f"Label '{label}' is already defined on line {symbol_table.get(label)}")
                elif REGISTERS.get(label.upper()) or OPCODES.get(label.upper()):
                    syntax_error(line_no, msg=f"Label '{label}' is a reserved keyword")
                else:
                    symbol_table.update({label: line_no})

            elif lexeme[0] == '$':
                tokens.append(Token(lexeme.strip('$'), TokenType.HEX_NUM, line_no))
            elif lexeme.isnumeric():
                tokens.append(Token(lexeme, TokenType.DEC_NUM, line_no))
            else:
                token = Token(lexeme, classify_symbol(lexeme), line_no)
                tokens.append(token)
                if token.type in [TokenType.OP_JUMP, TokenType.OP_NO_OPERAND,
                                  TokenType.OPR_ONE_OPERAND, TokenType.OPR_TWO_OPERAND,
                                  TokenType.OPR_THREE_OPERAND, TokenType.OPI_TWO_OPERAND,
                                  TokenType.OPI_THREE_OPERAND]:
                    line_no += 1
    return tokens + [Token('', TokenType.END_OF_FILE, line_no)], symbol_table


"""
Parse functions

Parameters: token_list
Returns: linked list of Instruction objects
"""


@dataclass
class Instruction:
    opcode: int = 0
    dest: int = 0
    src: int = 0
    trgt: int = 0
    imm16: int = 0
    shamt: int = 0
    offset26: int = 0
    directive: int = 0
    next: Optional["Instruction"] = None

    def __str__(self):
        if INSTRUCTION_FORMATS[self.opcode.upper()] == "R":
            return f"{self.opcode} {self.dest=} {self.src=} {self.trgt=} {self.shamt=}"
        elif INSTRUCTION_FORMATS[self.opcode.upper()] == "I":
            return f"{self.opcode} {self.dest=} {self.src=} {self.imm16=}"
        elif INSTRUCTION_FORMATS[self.opcode.upper()] == "J":
            return f"{self.opcode} {self.offset26=}"
        else:
            return self.directive


class Parser:
    def __init__(self, tokens, symbol_table):
        self.tokens = tokens
        self.symbol_table = symbol_table
        self.line_no = 0

    def parse_program(self):
        return self._parse_instruction_list()

    def _peek(self, how_far):
        """
        Look ahead to tokens comming up
        """
        if len(self.tokens) == 0:
            return Token("", TokenType.END_OF_FILE, 0)
        if how_far > len(self.tokens) or how_far < 0:
            parser_error(self.line_no,
                         f"\nParser.peek({how_far}) requested to peek beyond size of tokens list ({len(self.tokens) - 1})")
        return self.tokens[how_far - 1]

    def _get_token(self):
        """
        Get token only
        """
        if len(self.tokens) == 0:
            return Token(0, "", TokenType.END_OF_FILE)
        return self.tokens.pop(0)

    def _expect(self, token_type):
        """
        Get token and check it against supplied token type
        """
        token = self._get_token()
        if token.type != token_type:
            syntax_error(token, expected=token_type)
        if isinstance(token_type, list):
            if token.type not in token_type:
                syntax_error(token, expected=token_type)
        return token

    @staticmethod
    def _first(token, token_set):
        """
        Check if a token starts with a member of the supplied token set
        """
        return token.type in token_set

    def _parse_instruction_list(self):
        next_token = self._peek(1)
        instruction_list = None
        current_instruction = None
        while next_token.type != TokenType.END_OF_FILE:
            if instruction_list is None:
                instruction_list = self._parse_Instruction()
                if instruction_list is None:
                    break
                current_instruction = instruction_list
            else:
                temp = current_instruction
                current_instruction = self._parse_Instruction()
                if instruction_list is None:
                    break
                temp.next = current_instruction
            next_token = self._peek(1)
            self.line_no += 1
        return instruction_list

    def _parse_Instruction(self):
        """
        Instruction_list = (DIRECTIVE | LABEL | Instruction) {DIRECTIVE | LABEL | Instruction}
        """
        token = self._peek(1)
        if token.type == TokenType.END_OF_FILE:
            return None
        opcode = token.lexeme.upper()
        instruction = None
        if opcode in OP_NO_OPERAND_KEYWORDS:
            instruction = self._parse_OP_NO_OPERAND()
        elif opcode in OPR_ONE_OPERAND_KEYWORDS:
            instruction = self._parse_OPR_ONE_OPERAND()
        elif opcode in OPR_TWO_OPERAND_KEYWORDS:
            instruction = self._parse_OPR_TWO_OPERAND()
        elif opcode in OPR_THREE_OPERAND_KEYWORDS:
            instruction = self._parse_OPR_THREE_OPERAND()
        elif opcode in OPI_TWO_OPERAND_KEYWORDS:
            instruction = self._parse_OPI_TWO_OPERAND()
        elif opcode in OPI_THREE_OPERAND_KEYWORDS:
            instruction = self._parse_OPI_THREE_OPERAND()
        elif opcode in OP_JUMP_KEYWORDS:
            instruction = self._parse_OP_JUMP()
        else:
            syntax_error(token, expected="an opcode")

        return instruction

    def _parse_OP_NO_OPERAND(self):
        """
        OP_NO_OPERAND     = "NOP" | "HALT" | "RET" | "RETI"
        """
        opcode = self._expect(TokenType.OP_NO_OPERAND)
        return Instruction(opcode=opcode.lexeme)

    def _parse_OPR_ONE_OPERAND(self):
        """
        OPR_ONE_OPERAND   = "JALA"
        """
        opcode = self._expect(TokenType.OPR_ONE_OPERAND)
        src = self._vet_register(self._expect(TokenType.SYMBOL))

        return Instruction(opcode=opcode.lexeme, src=src)

    def _parse_OPR_TWO_OPERAND(self):
        """
        OPR_TWO_OPERAND   = "NOT" | "LBI" | "LWI" | "SBI" | "SWI"
        """
        opcode = self._expect(TokenType.OPR_TWO_OPERAND)
        dest = self._vet_register(self._expect(TokenType.SYMBOL))
        src = self._vet_register(self._expect(TokenType.SYMBOL))
        return Instruction(opcode=opcode.lexeme, dest=dest, src=src)

    def _parse_OPR_THREE_OPERAND(self):
        """
        OPR_THREE_OPERAND = "ADD" | "AND" | "DIV" | "LBS" | "MULT" | "OR" | "RBS" | "SUB" | "XOR"
        """
        opcode = self._expect(TokenType.OPR_THREE_OPERAND)
        dest_tok = self._expect(TokenType.SYMBOL)
        src_tok = self._expect(TokenType.SYMBOL)
        dest = self._vet_register(dest_tok.lexeme)
        src = self._vet_register(src_tok.lexeme)
        if dest is None:
            syntax_error(dest_tok, "valid register")
        if src is None:
            syntax_error(src_tok, "valid register")
        shamt = 0
        trgt = 0
        if opcode.lexeme.upper() == "LBS" or opcode.lexeme.upper() == "RBS":
            shamt = self._parse_numerical_value()
        else:
            trgt_tok = self._expect(TokenType.SYMBOL)
            trgt = self._vet_register(trgt_tok.lexeme)
            if trgt is None:
                syntax_error(dest_tok, "valid register")
        return Instruction(opcode=opcode.lexeme, dest=dest, src=src, trgt=trgt, shamt=shamt)

    def _parse_OPI_THREE_OPERAND(self):
        """
        OPI_THREE_OPERAND = "ADDI" | "ANDI" | "ORI" | "SUBI" | "XORI"
        """
        opcode = self._expect(TokenType.OPI_THREE_OPERAND)
        dest_tok = self._expect(TokenType.SYMBOL)
        src_tok = self._expect(TokenType.SYMBOL)
        dest = self._vet_register(dest_tok.lexeme)
        src = self._vet_register(src_tok.lexeme)
        if dest is None:
            syntax_error(dest_tok, "valid register")
        if src is None:
            syntax_error(src_tok, "valid register")
        if not self._first(self._peek(1), [TokenType.HEX_NUM, TokenType.DEC_NUM]):
            syntax_error(self._peek(1), expected=[TokenType.HEX_NUM, TokenType.DEC_NUM])
        imm16 = self._parse_numerical_value()
        return Instruction(opcode=opcode.lexeme, dest=dest, src=src, imm16=imm16)

    def _parse_OPI_TWO_OPERAND(self):
        """
        OPI_TWO_OPERAND   = "LB" | "LW" | "SB" | "SW"
        """
        opcode = self._expect(TokenType.OPI_TWO_OPERAND)
        dest_tok = self._expect(TokenType.SYMBOL)
        dest = self._vet_register(dest_tok.lexeme)
        if dest is None:
            syntax_error(dest_tok, "valid register")
        imm16 = self._parse_numerical_value()
        return Instruction(opcode=opcode.lexeme, dest=dest, imm16=imm16)

    def _parse_OP_JUMP(self):
        """
        OP_JUMP           = "BRN" | "BRP" | "BRZ" | "JAL" | "JMP" | "INTER"
        """
        opcode = self._expect(TokenType.OP_JUMP)
        if self._first(self._peek(1), [TokenType.HEX_NUM, TokenType.DEC_NUM]):
            offset26 = self._parse_numerical_value()
        else:
            label = self._expect(TokenType.SYMBOL)
            # Calculate offset
            try:
                start = self.symbol_table[label.lexeme]
            except KeyError:
                syntax_error(label, msg=f"{label.lexeme} is not defined")
                return

            offset26 = ((self.line_no - start) + 2)
            offset26 *= -1

        return Instruction(opcode=opcode.lexeme, offset26=offset26)

    def _parse_numerical_value(self):
        if not self._first(self._peek(1), [TokenType.HEX_NUM, TokenType.DEC_NUM]):
            syntax_error(self._peek(1), expected=[TokenType.HEX_NUM, TokenType.DEC_NUM])
        value = self._get_token()
        num = self._vet_dec_num(value.lexeme)
        if num is None:
            num = self._vet_hex_num(value.lexeme)
        if num is None:
            syntax_error(value, expected=[TokenType.HEX_NUM, TokenType.DEC_NUM])
        return num

    @staticmethod
    def _vet_hex_num(value):
        try:
            return int.from_bytes(bytes.fromhex(value), "little")
        except ValueError:
            return

    @staticmethod
    def _vet_dec_num(value):
        try:
            return int(value)
        except ValueError:
            return

    @staticmethod
    def _vet_register(value):
        try:
            return REGISTERS[value.upper()]
        except KeyError:
            return


def assemble_executable(program_list):
    instructions = []
    curr = program_list
    offset = 0
    while curr is not None:
        opcode = curr.opcode.upper()
        try:
            instr_format = INSTRUCTION_FORMATS[opcode]
        except KeyError:
            assembler_error(curr, f"{opcode} has an unknown format")
            return
        try:
            opcode = OPCODES[opcode]
        except KeyError:
            assembler_error(curr, f"{opcode} is not a valid instruction")
            return

        if instr_format == "R":
            instructions.append(encode_rtype(opcode, curr.dest, curr.src, curr.trgt, curr.shamt))
        elif instr_format == "I":
            instructions.append(encode_itype(opcode, curr.dest, curr.src, curr.imm16))
        elif instr_format == "J":
            instructions.append(encode_jtype(opcode, curr.offset26))
        curr = curr.next

    buffer = bytearray(len(instructions) * 4)
    for instr in instructions:
        write_uint32_to_buffer(buffer, offset, instr)
        offset += 4
    if ARGS.hexdump:
        print_word_hexdump(buffer, 0, offset)
    return buffer


def main():
    try:
        with open(ARGS.filename, 'r') as file:
            input_program = file.readlines()
    except FileNotFoundError:
        print(f"Could not open {ARGS.filename} because it does not exist")
        sys.exit(2)
    except PermissionError:
        print(f"Could not open {ARGS.filename} because user does not have permission")
        sys.exit(3)
    except OSError:
        print(f"Could not open {ARGS.filename}")
        sys.exit(4)
    instruction_offset = 0
    data_offset = 0
    # Lexical analysis
    print("Analyzing file")
    tokens, symbol_table = lexical_analysis(input_program)
    # Parse
    print("Parsing file")
    parser = Parser(tokens, symbol_table)
    program_list = parser.parse_program()
    if ARGS.debug:
        curr = program_list
        while curr is not None:
            print(curr)
            curr = curr.next
        print("Symbols: ")
        print(parser.symbol_table)
    # Convert to LC32 machine code
    print("Assembling executable")
    executable = assemble_executable(program_list)

    if ARGS.output:
        outfile = ARGS.output
    else:
        outfile = "program.out"
    with open(outfile, "wb") as file:
        file.write(executable)
    print(f"Wrote {len(executable)} bytes to {outfile}")


if __name__ == '__main__':
    main()
