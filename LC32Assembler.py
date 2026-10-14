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
imm17            = hex_num | dec_num
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


instruction_formats = {
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
    "T1": 16,
    "T2": 17,
    "T3": 18,
    "T4": 19,
    "T5": 20,
    "T6": 21,
    "T7": 22,
    "T8": 23,
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


def encode_rtype(opcode, dest, src, trgt):
    """
    R-type format:
    **OPCODE** [31-26: 6 bits] | **DEST** [25-21: 5 bits] | **SRC** [21-16: 5 bits] | **TRGT** [15-11: 5 bits] |**SHMAT** [10-6: 5 bits] | **Unused** [5-0: 6 bits]
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
    buffer[offset:offset + 4] = struct.pack('<I', value & 0xFFFFFFFF)


"""AI CODE END"""

class MissingErrorArgument(Exception):
    def __init__(self, *args):
        super().__init__(*args)

class TooManyArguments(Exception):
    def __init__(self, *args):
        super().__init__(*args)

def syntax_error(token, expected=None, msg=None):
    """
    For bad syntax in the input program
    """
    if expected is None and msg is not None:
        print(f"Syntax error on line {token.line_no}: '{token.lexeme}'\nExpected {expected}, but got {token.type} instead.")
    elif msg is None and expected is not None:
        print(msg)
    elif msg and expected:
        raise TooManyArguments("Cannot supply both a msg and an expected token")
    else:
        raise MissingErrorArgument("Must supply either a msg or an expected token")


    if DEBUG:
        traceback.print_stack()
    sys.exit(5)


def parser_error(line_no, msg):
    """
    For when parser itself fails
    """
    print(f"Parser error while parsing line {line_no}: {msg}")
    if DEBUG:
        traceback.print_stack()
    sys.exit(6)


def assembler_error(instruction, msg):
    """
    For when the assembling step breaks
    """
    print(f"Error while assembling {instruction.opcode} instruction: {msg}")
    if DEBUG:
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
Returns: linked list of Instruction objects
"""


@dataclass
class Instruction:
    opcode: str = ""
    dest: str = ""
    src: str = ""
    trgt: str = ""
    imm17: str = ""
    shamt: str = ""
    offset26: str = ""
    directive: str = ""
    next: Optional["Instruction"] = None

    def __str__(self):
        if self.opcode != "":
            if self.trgt != "":
                return f"{self.opcode} {self.dest} {self.src} {self.trgt}"
            elif self.shamt != "":
                return f"{self.opcode} {self.dest} {self.shamt}"
            elif self.imm17 != "":
                return f"{self.opcode} {self.dest} {self.src} {self.imm17}"
            elif self.offset26 != "":
                return f"{self.opcode} {self.offset26}"
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
            syntax_error(token, token_type)
        if isinstance(token_type, list):
            if token.type not in token_type:
                syntax_error(token, token_type)
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
            syntax_error(token, "an opcode")

        return instruction

    def _parse_OP_NO_OPERAND(self):
        """
        OP_NO_OPERAND     = "NOP" | "HALT" | "RET" | "RETI"
        """
        token = self._expect(TokenType.OP_NO_OPERAND)
        return Instruction(opcode=token)

    def _parse_OPR_ONE_OPERAND(self):
        """
        OPR_ONE_OPERAND   = "JALA"
        """
        token = self._expect(TokenType.OPR_ONE_OPERAND)
        src = self._expect(TokenType.SYMBOL)

        return Instruction(opcode=token, src=src)

    def _parse_OPR_TWO_OPERAND(self):
        """
        OPR_TWO_OPERAND   = "NOT" | "LBI" | "LWI" | "SBI" | "SWI"
        """
        token = self._expect(TokenType.OPR_TWO_OPERAND)
        dest = self._expect(TokenType.SYMBOL)
        src = self._expect(TokenType.SYMBOL)
        return Instruction(opcode=token, dest=dest, src=src)

    def _parse_OPR_THREE_OPERAND(self):
        """
        OPR_THREE_OPERAND = "ADD" | "AND" | "DIV" | "LBS" | "MULT" | "OR" | "RBS" | "SUB" | "XOR"
        """
        token = self._expect(TokenType.OPR_THREE_OPERAND)
        dest = self._expect(TokenType.SYMBOL)
        src = self._expect(TokenType.SYMBOL)
        trgt = self._expect(TokenType.SYMBOL)
        return Instruction(opcode=token, dest=dest, src=src, trgt=trgt)

    def _parse_OPI_THREE_OPERAND(self):
        """
        OPI_THREE_OPERAND = "ADDI" | "ANDI" | "ORI" | "SUBI" | "XORI"
        """
        token = self._expect(TokenType.OPI_THREE_OPERAND)
        dest = self._expect(TokenType.SYMBOL)
        src = self._expect(TokenType.SYMBOL)
        if not self._first(self._peek(1), [TokenType.HEX_NUM, TokenType.DEC_NUM]):
            syntax_error(self._peek(1), [TokenType.HEX_NUM, TokenType.DEC_NUM])
        imm17 = self._get_token()
        return Instruction(opcode=token, dest=dest, src=src, imm17=imm17)

    def _parse_OPI_TWO_OPERAND(self):
        """
        OPI_TWO_OPERAND   = "LB" | "LW" | "SB" | "SW"
        """
        token = self._expect(TokenType.OPI_TWO_OPERAND)
        dest = self._expect(TokenType.SYMBOL)
        self._parse_register(dest)
        if not self._first(self._peek(1), [TokenType.HEX_NUM, TokenType.DEC_NUM]):
            syntax_error(self._peek(1), [TokenType.HEX_NUM, TokenType.DEC_NUM])
        imm17 = self._get_token()
        return Instruction(opcode=token, dest=dest, imm17=imm17)

    def _parse_OP_JUMP(self):
        """
        OP_JUMP           = "BRN" | "BRP" | "BRZ" | "JAL" | "JMP" | "INTER"
        """
        token = self._expect(TokenType.OP_JUMP)
        if not self._first(self._peek(1), [TokenType.HEX_NUM, TokenType.DEC_NUM, TokenType.SYMBOL]):
            syntax_error(self._peek(1), [TokenType.HEX_NUM, TokenType.DEC_NUM, TokenType.SYMBOL])

        offset26 = self._get_token()
        return Instruction(opcode=token, offset26=offset26)

    def _parse_imm17(self):
        pass

    def _parse_offset26(self):
        pass

    def _parse_hex_num(self):
        pass

    def _parse_dec_num(self):
        pass

    def _parse_symbol(self):
        pass

    def _parse_register(self):
        pass


def assemble_executable(program_list):
    out = bytearray()
    curr = program_list
    while curr is not None:
        try:
            instr_format = instruction_formats[curr.opcode]
        except KeyError:
            assembler_error(curr, f"{curr.opcode} has an unknown format")
            return

        try:
            opcode = OPCODES[curr.opcode]
        except KeyError:
            assembler_error(curr, f"{curr.opcode} is not a valid instruction")
            return

        if instr_format == "R":
            instruction = encode_rtype(opcode, curr.dest, curr.src, curr.trgt)
        elif instr_format == "I":
            instruction = encode_itype(opcode, curr.dest, curr.src, curr.imm17)
        elif instr_format == "J":
            instruction = encode_itype(opcode)

        curr = curr.next
    return


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
    # Parse
    parser = Parser(tokens, symbol_table)
    program_list = parser.parse_program()
    # curr = program_list
    # while curr is not None:
    #     print(curr)
    #     curr = curr.next
    # Convert to LC32 machine code
    executable = assemble_executable(program_list)


if __name__ == '__main__':
    main()
