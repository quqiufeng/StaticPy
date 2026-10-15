"""Backend-independent intermediate representation for StaticPy.

This layer sits between the Python AST + typechecker and the backend
 generators (Chez Scheme first, LLVM/WASM later).  All backends consume
IRModule/IRFunc/IRStmt/IRExpr, never the Python AST directly.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple
from static_common import Type, type_to_str

# ---------- IR types ----------

@dataclass
class IRVar:
    """A typed local variable or parameter."""
    name: str
    ty: Optional[Type] = None

# ---------- IR expressions ----------

@dataclass
class IRExpr:
    ty: Optional[Type] = None

@dataclass
class EConst(IRExpr):
    value: Any = None

@dataclass
class EVar(IRExpr):
    name: str = ""

@dataclass
class EBinop(IRExpr):
    op: str = ""  # + - * / // % == != < > <= >= and or
    left: IRExpr = field(default_factory=IRExpr)
    right: IRExpr = field(default_factory=IRExpr)

@dataclass
class EUnary(IRExpr):
    op: str = ""  # not, -
    operand: IRExpr = field(default_factory=IRExpr)

@dataclass
class ECall(IRExpr):
    func: IRExpr = field(default_factory=IRExpr)
    args: List[IRExpr] = field(default_factory=list)

@dataclass
class ESubscript(IRExpr):
    target: IRExpr = field(default_factory=IRExpr)
    index: IRExpr = field(default_factory=IRExpr)

@dataclass
class ESlice(IRExpr):
    target: IRExpr = field(default_factory=IRExpr)
    start: Optional[IRExpr] = None
    stop: Optional[IRExpr] = None

@dataclass
class EAttr(IRExpr):
    target: IRExpr = field(default_factory=IRExpr)
    field: str = ""

@dataclass
class ETuple(IRExpr):
    items: List[IRExpr] = field(default_factory=list)

@dataclass
class EList(IRExpr):
    items: List[IRExpr] = field(default_factory=list)

@dataclass
class EDict(IRExpr):
    items: List[Tuple[IRExpr, IRExpr]] = field(default_factory=list)

@dataclass
class EMakeRecord(IRExpr):
    """Construct a user-defined dataclass record."""
    name: str = ""
    fields: List[Tuple[str, IRExpr]] = field(default_factory=list)

@dataclass
class EVariant(IRExpr):
    """Construct a variant tag, e.g. Ok(v) or Some(v)."""
    tag: str = ""
    arg: Optional[IRExpr] = None

@dataclass
class ELambda(IRExpr):
    params: List[IRVar] = field(default_factory=list)
    body: List["IRStmt"] = field(default_factory=list)

# ---------- IR statements ----------

@dataclass
class IRStmt:
    pass

@dataclass
class SAssign(IRStmt):
    name: str = ""
    value: IRExpr = field(default_factory=IRExpr)

@dataclass
class SAssignSubscript(IRStmt):
    target: IRExpr = field(default_factory=IRExpr)
    index: IRExpr = field(default_factory=IRExpr)
    value: IRExpr = field(default_factory=IRExpr)

@dataclass
class SAssignAttr(IRStmt):
    target: IRExpr = field(default_factory=IRExpr)
    field: str = ""
    value: IRExpr = field(default_factory=IRExpr)

@dataclass
class SMultiAssign(IRStmt):
    """Tuple unpacking: a, b = expr"""
    names: List[str] = field(default_factory=list)
    value: IRExpr = field(default_factory=IRExpr)

@dataclass
class SReturn(IRStmt):
    value: Optional[IRExpr] = None

@dataclass
class SExpr(IRStmt):
    value: IRExpr = field(default_factory=IRExpr)

@dataclass
class SIf(IRStmt):
    cond: IRExpr = field(default_factory=IRExpr)
    then_body: List[IRStmt] = field(default_factory=list)
    else_body: List[IRStmt] = field(default_factory=list)

@dataclass
class SWhile(IRStmt):
    cond: IRExpr = field(default_factory=IRExpr)
    body: List[IRStmt] = field(default_factory=list)

@dataclass
class SForRange(IRStmt):
    var: str = ""
    start: Optional[IRExpr] = None
    stop: IRExpr = field(default_factory=IRExpr)
    step: Optional[IRExpr] = None
    body: List[IRStmt] = field(default_factory=list)

@dataclass
class SBreak(IRStmt):
    pass

@dataclass
class SContinue(IRStmt):
    pass

# ---------- IR function ----------

@dataclass
class IRFunc:
    name: str = ""
    params: List[IRVar] = field(default_factory=list)
    return_type: Optional[Type] = None
    body: List[IRStmt] = field(default_factory=list)
    source_file: str = ""
    source_line: int = 0

# ---------- IR dataclass / enum / extern ----------

@dataclass
class IRRecord:
    name: str = ""
    fields: List[IRVar] = field(default_factory=list)

@dataclass
class IREnum:
    name: str = ""
    members: List[Tuple[str, int]] = field(default_factory=list)

@dataclass
class IRExtern:
    name: str = ""
    params: List[IRVar] = field(default_factory=list)
    return_type: Optional[Type] = None
    lib: str = ""
    cname: str = ""

# ---------- IR module ----------

@dataclass
class IRModule:
    source_file: str = ""
    records: List[IRRecord] = field(default_factory=list)
    enums: List[IREnum] = field(default_factory=list)
    externs: List[IRExtern] = field(default_factory=list)
    imports: List[Tuple[str, Optional[str]]] = field(default_factory=list)
    funcs: List[IRFunc] = field(default_factory=list)

# ---------- helpers ----------

def ir_var(name: str, ty: Optional[Type] = None) -> IRVar:
    return IRVar(name=name, ty=ty)

def ir_const(value: Any, ty: Optional[Type] = None) -> EConst:
    return EConst(value=value, ty=ty)

def ir_var_expr(name: str, ty: Optional[Type] = None) -> EVar:
    return EVar(name=name, ty=ty)
