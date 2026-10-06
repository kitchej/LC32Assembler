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
HEX_NUM           = $HEX_DIGIT {HEX_DIGIT}
DEC_NUM           = DIGIT {DIGIT}
SYMBOL            = CHAR {CHAR | DIGIT}
LABEL             = SYMBOL:
DIRECTIVE         = .SYMBOL

Grammar:
Program          = Instruction_list
Instruction_list = (DIRECTIVE | LABEL | Instruction) {DIRECTIVE | LABEL | Instruction}
Instruction      = ROpcode | IOpcode | JOpcode | OP_NO_OPERAND
ROpocde          = OPR_ONE_OPERAND SYMBOL | OPR_TWO_OPERAND SYMBOL SYMBOL | OPR_THREE_OPERAND SYMBOL SYMBOL SYMBOL
IOpcode          = OPI_TWO_OPERAND SYMBOL (HEX_NUM | DEC_NUM) | OPI_THREE_OPERAND SYMBOL SYMBOL (HEX_NUM | DEC_NUM)
JOpcode          = OP_JUMP (SYMBOL | HEX_HUM | DEC_NUM)
"""
import struct
import sys
from dataclasses import dataclass
from enum import Enum, auto
from typing import NamedTuple, Optional
import traceback

USAGE = "LC32Assembler.py (filepath)"
MAX_UINT_32 = 0xFFFFFFFF
DEBUG = True

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

# Opcode definitions (matching the CPU's Opcode enum)
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


def encode_rtype(opcode, dest, src, trgt):
    """
    R-type format:
    **OPCODE** [31-26: 6 bits] | **DEST** [25-21: 5 bits] | **SRC** [21-16: 5 bits] | **TRGT** [15-11: 5 bits] | **Unused** [10-0: 11 bits]
    """
    instruction = (opcode << 26) | (dest << 21) | (src << 16) | (trgt << 11)
    return instruction & 0xFFFFFFFF

def encode_itype(opcode, dest, src, imm17):
    """
    I-type format:
    **OPCODE** [31-26: 6 bits] | **DEST** [25-21: 5 bits] | **SRC** [20-16: 5 bits] | **IMM-17** [16-0: 17 bits]
    """
    instruction = (opcode << 26) | (dest << 21) | (src << 17) | (imm17 & 0x1FFFF)
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
    buffer[offset:offset+4] = struct.pack('<I', value & 0xFFFFFFFF)

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

def syntax_error(token, expected):
    print(f"Syntax error on line {token.line_no}: '{token.lexeme}'\nExpected {expected}, but got {token.type} instead.")
    sys.exit(5)

def parser_error(line_no, msg):
    print(f"Parser error while parsing line {line_no}: {msg}")
    if DEBUG:
        traceback.print_stack()
    sys.exit(6)

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
            elif lexeme[-1] == ':':
                label = lexeme.strip(':')
                if not symbol_table.get(label):
                    symbol_table.update({label: line_no})
                else:
                    parser_error(line_no, f"{label} is already defined on line {symbol_table.get(label)}")
                continue
            elif lexeme[0] == '$':
                tokens.append(Token(lexeme.strip('$'), TokenType.HEX_NUM, line_no))
            elif lexeme.isnumeric():
                tokens.append(Token(lexeme, TokenType.DEC_NUM, line_no))
            else:
                tokens.append(Token(lexeme, classify_symbol(lexeme), line_no))
        line_no += 1
    return tokens + [Token('', TokenType.END_OF_FILE, line_no)], symbol_table

"""
Parse functions

Parameters: token_list
Returns: linked list of Instructions
"""

@dataclass
class Instruction:
    opcode: str = ""
    dest: str = ""
    src: str = ""
    trgt: str = ""
    imm16: str = ""
    shamt: str = ""
    offset26: str = ""
    directive: str = ""
    next: Optional["Instruction"] = None

    def __repr__(self):
        parts = []
        for f in self.fields():
            if f.name == "next":
                continue
            value = getattr(self, f.name)
            if value:
                parts.append(f"{f.name}={value!r}")
        return f"Instruction({', '.join(parts)})"


class Parser:
    def __init__(self, tokens, symbol_table):
        self.tokens = tokens
        self.symbol_table = symbol_table
        self.line_no = 0

    def parse_program(self):
        return self._parse_Instruction_list()

    def _peek(self, how_far):
        if len(self.tokens) == 0:
            return Token("", TokenType.END_OF_FILE, 0)
        if how_far >= len(self.tokens) or how_far <= 0:
            parser_error(self.line_no, f"\nParser.peek({how_far}) requested to peek beyond size of tokens list ({len(self.tokens) - 1})")
        return self.tokens[how_far - 1]

    def _get_token(self):
        if len(self.tokens) == 0:
            return Token("", TokenType.END_OF_FILE)
        return self.tokens.pop(0)

    def _expect(self, token_type):
        token = self._get_token()
        if token.type != token_type:
            syntax_error(token, token_type)
        if isinstance(token_type, list):
            if token.type not in token_type:
                syntax_error(token, token_type)
        return token

    @staticmethod
    def _first(token, token_set):
        return token.type in token_set

    def _parse_Instruction_list(self):
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

    def _parse_Instruction(self):
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
            syntax_error(token, "an opcode")

        return instruction

    def _parse_OP_NO_OPERAND(self):
        token = self._expect(TokenType.OP_NO_OPERAND)
        return Instruction(opcode=token.lexeme)

    def _parse_OPR_ONE_OPERAND(self):
        token = self._expect(TokenType.OPR_ONE_OPERAND)
        src = self._expect(TokenType.SYMBOL)
        return Instruction(opcode=token.lexeme, src=src)

    def _parse_OPR_TWO_OPERAND(self):
        token = self._expect(TokenType.OPR_TWO_OPERAND)
        dest = self._expect(TokenType.SYMBOL)
        src = self._expect(TokenType.SYMBOL)
        return Instruction(opcode=token.lexeme, dest=dest, src=src)

    def _parse_OPR_THREE_OPERAND(self):
        token = self._expect(TokenType.OPR_THREE_OPERAND)
        dest = self._expect(TokenType.SYMBOL)
        src = self._expect(TokenType.SYMBOL)
        trgt = self._expect(TokenType.SYMBOL)
        return Instruction(opcode=token.lexeme, dest=dest, src=src, trgt=trgt)

    def _parse_OPI_THREE_OPERAND(self):
        token = self._expect(TokenType.OPI_THREE_OPERAND)
        dest = self._expect(TokenType.SYMBOL)
        src = self._expect(TokenType.SYMBOL)
        if not self._first(self._peek(1), [TokenType.HEX_NUM, TokenType.DEC_NUM]):
            syntax_error(self._peek(1), [TokenType.HEX_NUM, TokenType.DEC_NUM])
        imm16 = self._get_token()
        return Instruction(opcode=token.lexeme, dest=dest, src=src, imm16=imm16)

    def _parse_OPI_TWO_OPERAND(self):
        token = self._expect(TokenType.OPI_TWO_OPERAND)
        dest = self._expect(TokenType.SYMBOL)
        if not self._first(self._peek(1), [TokenType.HEX_NUM, TokenType.DEC_NUM]):
            syntax_error(self._peek(1), [TokenType.HEX_NUM, TokenType.DEC_NUM])
        imm16 = self._get_token()
        return Instruction(opcode=token.lexeme, dest=dest, imm16=imm16)

    def _parse_OP_JUMP(self):
        token = self._expect(TokenType.OP_JUMP)
        if not self._first(self.peek(1), [TokenType.HEX_NUM, TokenType.DEC_NUM, TokenType.SYMBOL]):
            syntax_error(self._peek(1), [TokenType.HEX_NUM, TokenType.DEC_NUM, TokenType.SYMBOL])

        offset26 = self._get_token()
        return Instruction(opcode=token.lexeme, offset26=offset26)

def main():
    if len(sys.argv) != 2:
        print(USAGE)
        sys.exit(1)

    filepath = sys.argv[1]

    try:
        with open(filepath, 'r') as file:
            program_text = file.readlines()
    except FileNotFoundError:
        sys.exit(2)
    except PermissionError:
        sys.exit(3)
    except OSError:
        sys.exit(4)
    instruction_offset = 0
    data_offset = 0
    # Lexical analysis
    tokens, symbol_table = lexical_analysis(program_text)
    print(tokens)
    # Parse
    parser = Parser(tokens, symbol_table)
    program_list = parser.parse_program()
    curr = program_list
    while program_list != None:
        print(curr.__repr__())
        curr = curr.next
    # Convert to LC32 machine code

if __name__ == '__main__':
    main()