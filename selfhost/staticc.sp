# staticc.sp — StaticPy subset compiler written in .sp syntax.
#
# ========== tokenizer ==========

def str-ref (s : str i : int) -> str
  return (call substring s i (+ i 1))
end

# ---------- 字符类 ----------
# 词法约定（写 .sp 时必须遵守，写错了编译器会报错而不是产出废码）：
#   标识符  = [A-Za-z_][A-Za-z0-9_?]*( '-' 后接字母 … )   ; '-' 只在后面紧跟字母时属于标识符
#   数字    = '-'? digits [ '.' digits ] [ (e|E) [+-]? digits ]
#   二元减法必须留空格：(- a b) / (n - 1)
#   因此：a-1 → a , - , 1（减法）；emit-plus → 一个标识符；-7 → 一个字面量

def is-digit (c : str) -> bool
  return (and (>= c "0") (<= c "9"))
end

def is-alpha (c : str) -> bool
  return (or (and (>= c "a") (<= c "z")) (and (>= c "A") (<= c "Z")))
end

def is-ident-char (c : str) -> bool
  return (or (or (call is-alpha c) (call is-digit c)) (or (= c "_") (= c "?")))
end

# ========== 字符串构造（string port，避免 O(n^2)） ==========

def sb-new () -> any
  return (call open-output-string)
end

def sb-write (sb : any s : str) -> int
  (call display s sb)
  return 0
end

def sb-string (sb : any) -> str
  return (call get-output-string sb)
end

def scan-ident (src : str i : int n : int) -> int
  while (< i n)
    let c str (call str-ref src i)
    if (call is-ident-char c)
      set i (+ i 1)
    else
      if (and (= c "-") (and (< (+ i 1) n) (call is-alpha (call str-ref src (+ i 1)))))
        set i (+ i 1)
      else
        return i
      end
    end
  end
  return i
end

def exp-start? (src : str i : int n : int) -> bool
  if (>= i n) return False
  end
  let c str (call str-ref src i)
  if (call is-digit c) return True
  end
  if (and (or (= c "+") (= c "-")) (and (< (+ i 1) n) (call is-digit (call str-ref src (+ i 1)))))
    return True
  end
  return False
end

def scan-exp (src : str i : int n : int) -> int
  if (< i n)
    let c str (call str-ref src i)
    if (or (= c "+") (= c "-")) set i (+ i 1) end
  end
  while (and (< i n) (call is-digit (call str-ref src i)))
    set i (+ i 1)
  end
  return i
end

def scan-number (src : str i : int n : int) -> int
  while (< i n)
    let c str (call str-ref src i)
    if (call is-digit c)
      set i (+ i 1)
    else
      if (and (= c ".") (and (< (+ i 1) n) (call is-digit (call str-ref src (+ i 1)))))
        set i (+ i 1)
      else
        if (and (or (= c "e") (= c "E")) (call exp-start? src (+ i 1) n))
          set i (call scan-exp src (+ i 1) n)
        else
          return i
        end
      end
    end
  end
  return i
end

def tokenize (src : str) -> str
  let sb any (call sb-new)
  let i int 0
  let n int (call list_length src)
  let line int 1
  while (< i n)
    let c str (call str-ref src i)
    if (or (or (or (= c " ") (= c "\t")) (= c "\n")) (= c "\r"))
      if (= c "\n")
        set line (+ line 1)
      end
      set i (+ i 1)
    else
      if (= c "#")
        set i (+ i 1)
        while (and (< i n) (not (= (call str-ref src i) "\n")))
          set i (+ i 1)
        end
      else
        if (= c "\"")
          let start int i
          set i (+ i 1)
          while (and (< i n) (not (= (call str-ref src i) "\"")))
            if (= (call str-ref src i) "\\")
              set i (+ i 2)
            else
              if (= (call str-ref src i) "\n")
                set line (+ line 1)
              end
              set i (+ i 1)
            end
          end
          if (>= i n)
            (call parse-fail-at "unterminated string literal" (call count-lines src))
          end
          set i (+ i 1)
          (call emit-tok sb line (call substring src start i))
        else
          let tmp tuple (call tokenize-symbol src i n)
          (call emit-tok sb line (call vector-ref tmp 0))
          set i (call vector-ref tmp 1)
        end
      end
    end
  end
  # 末尾哨兵：EOF 时的 next-token 也能报出「最后一行」
  (call emit-tok sb line "")
  return (call sb-string sb)
end

# token 流格式：每个 token 写成 "<行号> <文本> "。行号由 tokenize 在一次扫描中累加，
# 因而是绝对行号；next-token 只做 O(1) 读取，不再靠数换行（旧实现每 token 从 1 起算，
# 报错位置是「相对上一次 token」的偏移，带空行/注释的文件会报错行）。
def emit-tok (sb : any line : int text : str) -> int
  (call sb-write sb (call num-str line))
  (call sb-write sb " ")
  (call sb-write sb text)
  (call sb-write sb " ")
  return 0
end

def digit-val (c : str) -> int
  let k int 0
  while (< k 10)
    if (= c (call substring "0123456789" k (+ k 1)))
      return k
    end
    set k (+ k 1)
  end
  return 0
end

def str-int (s : str) -> int
  let n int (call list_length s)
  let i int 0
  let v int 0
  if (and (> n 0) (= (call str-ref s 0) "-"))
    set i 1
  end
  while (< i n)
    set v (+ (* v 10) (call digit-val (call str-ref s i)))
    set i (+ i 1)
  end
  if (and (> n 0) (= (call str-ref s 0) "-"))
    return (- 0 v)
  end
  return v
end

def tokenize-symbol (src : str i : int n : int) -> tuple
  let c str (call str-ref src i)
  if (or (= c "(") (= c ")"))
    return (call vector (call string-append c " ") (+ i 1))
  end
  if (or (call is-alpha c) (= c "_"))
    let start int i
    set i (call scan-ident src i n)
    return (call vector (call string-append (call substring src start i) " ") i)
  end
  if (call is-digit c)
    let start int i
    set i (call scan-number src i n)
    return (call vector (call string-append (call substring src start i) " ") i)
  end
  if (and (= c "-") (and (< (+ i 1) n) (not (= (call str-ref src (+ i 1)) ">"))))
    if (call is-digit (call str-ref src (+ i 1)))
      let start int i
      set i (call scan-number src (+ i 1) n)
      return (call vector (call string-append (call substring src start i) " ") i)
    end
  end
  return (call tokenize-op src i n)
end

def tokenize-op (src : str i : int n : int) -> tuple
  let out str ""
  let c str (call substring src i (+ i 1))
  if (and (= c "-") (and (< (+ i 1) n) (= (call str-ref src (+ i 1)) ">")))
    set out "-> "
    set i (+ i 2)
  else
    if (and (= c ">") (and (< (+ i 1) n) (= (call str-ref src (+ i 1)) "=")))
      set out ">= "
      set i (+ i 2)
    else
      if (and (= c "<") (and (< (+ i 1) n) (= (call str-ref src (+ i 1)) "=")))
        set out "<= "
        set i (+ i 2)
      else
        if (and (= c "=") (and (< (+ i 1) n) (= (call str-ref src (+ i 1)) "=")))
          set out "== "
          set i (+ i 2)
        else
          if (and (= c "!") (and (< (+ i 1) n) (= (call str-ref src (+ i 1)) "=")))
            set out "!= "
            set i (+ i 2)
          else
            set out (call string-append c " ")
            set i (+ i 1)
          end
        end
      end
    end
  end
  return (call vector out i)
end

# 返回 (token, 新位置, 行号)。行号 = token 流里 "\n" 标记的个数 + 1，
# tokenize 已经把源码换行原样写进 token 流，所以行号与源码一一对应。
def next-token (tokens : str pos : int) -> tuple
  let n int (call list_length tokens)
  while (and (< pos n) (= (call str-ref tokens pos) " "))
    set pos (+ pos 1)
  end
  if (>= pos n)
    return (call vector "" pos 0)
  end
  let lstart int pos
  while (and (< pos n) (not (= (call str-ref tokens pos) " ")))
    set pos (+ pos 1)
  end
  let line int (call str-int (call substring tokens lstart pos))
  while (and (< pos n) (= (call str-ref tokens pos) " "))
    set pos (+ pos 1)
  end
  if (>= pos n)
    return (call vector "" pos line)
  end
  let start int pos
  if (= (call str-ref tokens pos) "\"")
    set pos (+ pos 1)
    while (and (< pos n) (not (= (call str-ref tokens pos) "\"")))
      if (= (call str-ref tokens pos) "\\")
        set pos (+ pos 2)
      else
        set pos (+ pos 1)
      end
    end
    set pos (+ pos 1)
  else
    while (and (< pos n) (not (= (call str-ref tokens pos) " ")))
      set pos (+ pos 1)
    end
  end
  return (call vector (call substring tokens start pos) pos line)
end

# ========== IR constructors ==========

def EConst (value) -> tuple
  return (call vector "EConst" value)
end

def EVar (name) -> tuple
  return (call vector "EVar" name)
end

def EBinop (op left right) -> tuple
  return (call vector "EBinop" op left right)
end

def EUnary (op operand) -> tuple
  return (call vector "EUnary" op operand)
end

def ECall (func args) -> tuple
  return (call vector "ECall" func args)
end

def ELambda (params body) -> tuple
  return (call vector "ELambda" params body)
end

def SLet (name ty value) -> tuple
  return (call vector "SLet" name ty value)
end

def SSet (name value) -> tuple
  return (call vector "SSet" name value)
end

def SReturn (value) -> tuple
  return (call vector "SReturn" value)
end

def SExpr (value) -> tuple
  return (call vector "SExpr" value)
end

def SIf (cond-expr then-body else-body) -> tuple
  return (call vector "SIf" cond-expr then-body else-body)
end

def SWhile (cond-expr body) -> tuple
  return (call vector "SWhile" cond-expr body)
end

def SFor (var stop body) -> tuple
  return (call vector "SFor" var stop body)
end

def IRFunc (name params param-types ret body) -> tuple
  return (call vector "IRFunc" name params param-types ret body)
end

# ========== list helpers ==========

def list-ref (lst i) -> any
  return (call list_ref lst i)
end

def list-length (lst) -> int
  return (call list_length lst)
end

def list-append (lst val) -> any
  return (call obj-list-append lst val)
end

def list-append-all (target source) -> any
  let i int 0
  let n int (call list-length source)
  while (< i n)
    set target (call list-append target (call list-ref source i))
    set i (+ i 1)
  end
  return target
end

def list-ref-range (lst start stop) -> any
  let result any (call py-list)
  let i int start
  while (< i stop)
    set result (call list-append result (call list-ref lst i))
    set i (+ i 1)
  end
  return result
end

def str-join (parts sep-str) -> str
  let sb any (call sb-new)
  let i int 0
  let n int (call list-length parts)
  while (< i n)
    if (> i 0)
      (call sb-write sb sep-str)
    end
    (call sb-write sb (call list-ref parts i))
    set i (+ i 1)
  end
  return (call sb-string sb)
end

def func-params-to-str (params) -> str
  let result str ""
  let i int 0
  let n int (call list-length params)
  while (< i n)
    if (= i 0) set result (call list-ref params i)
    else set result (call string-append (call string-append result " ") (call list-ref params i))
    end
    set i (+ i 1)
  end
  return result
end

# ========== parser ==========

def parse-expr (tokens : str pos : int) -> tuple
  let tmp tuple (call next-token tokens pos)
  let tok str (call vector-ref tmp 0)
  let new-pos int (call vector-ref tmp 1)
  return (call parse-expr-at tokens new-pos tok (call vector-ref tmp 2))
end

def parse-expr-at (tokens : str pos : int tok : str line : int) -> tuple
  if (= tok "(")
    return (call parse-paren tokens pos)
  else
    let result any ""
    if (= tok "")
      (call parse-fail-at "unexpected end of input: expression expected" line)
    end
    if (call is-reserved tok)
      (call parse-fail-at (call string-append (call string-append "expression expected, found keyword '") (call string-append tok "'")) line)
    end
    let first str (call substring tok 0 1)
    if (= first "\"")
      set result (call EConst tok)
    else
      if (or (or (call is-digit first) (= first "-")) (= first "."))
        set result (call EConst tok)
      else
        set result (call EVar tok)
      end
    end
    return (call vector result pos)
  end
end

def parse-paren (tokens : str pos : int) -> tuple
  let result any ""
  let tmp tuple (call next-token tokens pos)
  let op str (call vector-ref tmp 0)
  set pos (call vector-ref tmp 1)
  if (= op "call")
    let tmp tuple (call next-token tokens pos)
    let name str (call vector-ref tmp 0)
    set pos (call vector-ref tmp 1)
    let args any (call py-list)
    let tmp tuple (call next-token tokens pos)
    let nxt str (call vector-ref tmp 0)
    let pos2 int (call vector-ref tmp 1)
    while (not (= nxt ")"))
      let tmp tuple (call parse-expr tokens pos)
      let arg any (call vector-ref tmp 0)
      set pos (call vector-ref tmp 1)
      set args (call list-append args arg)
      set tmp (call next-token tokens pos)
      set nxt (call vector-ref tmp 0)
      set pos2 (call vector-ref tmp 1)
    end
    set pos pos2
    set result (call ECall name args)
    return (call vector result pos)
  else
    if (= op "not")
      return (call parse-not tokens pos op)
    else
      if (= op "lambda")
        return (call parse-lambda tokens pos)
      else
        return (call parse-binop tokens pos op)
      end
    end
  end
end

# (lambda (a b) stmt ...) —— 表达式位置的一等函数；body 是语句序列，末句为返回值
def parse-lambda (tokens : str pos : int) -> tuple
  let tmp tuple (call next-token tokens pos)
  let lparen str (call vector-ref tmp 0)
  let lparen-line int (call vector-ref tmp 2)
  let pos2 int (call vector-ref tmp 1)
  if (not (= lparen "("))
    (call parse-fail-at (call string-append (call string-append "expected '(' to open lambda parameter list, found '" (call string-append lparen "'"))) lparen-line)
  end
  let tmp2 tuple (call parse-lambda-params tokens pos2 (call py-list))
  let params any (call vector-ref tmp2 0)
  let pos3 int (call vector-ref tmp2 1)
  let tmp3 tuple (call parse-lambda-body tokens pos3 (call py-list))
  let body any (call vector-ref tmp3 0)
  let pos4 int (call vector-ref tmp3 1)
  return (call vector (call ELambda params body) pos4)
end

def parse-lambda-params (tokens : str pos : int acc : any) -> tuple
  let tmp tuple (call next-token tokens pos)
  let tok str (call vector-ref tmp 0)
  let pos2 int (call vector-ref tmp 1)
  if (= tok ")")
    return (call vector acc pos2)
  end
  if (= tok "")
    (call parse-fail-at "unexpected end of input in lambda parameter list" (call vector-ref tmp 2))
  end
  if (or (call known-type? tok) (call is-reserved tok))
    (call parse-fail-at (call string-append (call string-append "lambda parameter expected, found '") (call string-append tok "'")) (call vector-ref tmp 2))
  end
  return (call parse-lambda-params tokens pos2 (call list-append acc tok))
end

def parse-lambda-body (tokens : str pos : int acc : any) -> tuple
  let tmp tuple (call next-token tokens pos)
  let tok str (call vector-ref tmp 0)
  if (= tok ")")
    return (call vector acc (call vector-ref tmp 1))
  end
  if (= tok "")
    (call parse-fail-at "unexpected end of input: missing ')' to close lambda" (call vector-ref tmp 2))
  end
  let tmp2 tuple (call parse-stmt tokens pos)
  let stmt any (call vector-ref tmp2 0)
  if (call ir-tag? stmt "SReturn")
    (call parse-fail-at "return is not allowed inside lambda (its body is an expression)" (call vector-ref tmp 2))
  end
  return (call parse-lambda-body tokens (call vector-ref tmp2 1) (call list-append acc stmt))
end

def parse-not (tokens : str pos : int op : str) -> tuple
  let result any ""
  let tmp tuple (call parse-expr tokens pos)
  let operand any (call vector-ref tmp 0)
  set pos (call vector-ref tmp 1)
  let tmp tuple (call next-token tokens pos)
  let rparen str (call vector-ref tmp 0)
  set pos (call vector-ref tmp 1)
  if (not (= rparen ")"))
    (call parse-fail-at (call string-append "expected ')' to close 'not', found '" (call string-append rparen "'")) (call vector-ref tmp 2))
  end
  set result (call EUnary op operand)
  return (call vector result pos)
end

def parse-binop (tokens : str pos : int op : str) -> tuple
  let result any ""
  let tmp tuple (call parse-expr tokens pos)
  let left any (call vector-ref tmp 0)
  set pos (call vector-ref tmp 1)
  let tmp tuple (call parse-expr tokens pos)
  let right any (call vector-ref tmp 0)
  set pos (call vector-ref tmp 1)
  let tmp tuple (call next-token tokens pos)
  let rparen str (call vector-ref tmp 0)
  set pos (call vector-ref tmp 1)
  if (not (= rparen ")"))
    (call parse-fail-at (call string-append (call string-append "expected ')' to close '" (call string-append op "'")) (call string-append ", found '" (call string-append rparen "'"))) (call vector-ref tmp 2))
  end
  set result (call EBinop op left right)
  return (call vector result pos)
end

def count-lines (s : str) -> int
  let i int 0
  let n int (call list_length s)
  let lines int 1
  while (< i n)
    if (= (call str-ref s i) "\n")
      set lines (+ lines 1)
    end
    set i (+ i 1)
  end
  return lines
end

def num-str (n : int) -> str
  let sb any (call sb-new)
  (call display n sb)
  return (call sb-string sb)
end

def parse-fail-at (msg : str line : int) -> int
  let head str "staticc: error: "
  if (> line 0)
    set head (call string-append (call string-append "staticc: error: line " (call num-str line)) ": ")
  end
  (call display (call string-append head msg) (call current-error-port))
  (call newline (call current-error-port))
  (call flush-output-port (call current-error-port))
  (call exit 1)
  return 0
end

def parse-fail (msg : str) -> int
  return (call parse-fail-at msg 0)
end

def known-type? (ty : str) -> bool
  if (or (or (= ty "int") (or (= ty "float") (= ty "str"))) (or (or (= ty "bool") (= ty "any")) (or (= ty "tuple") (= ty "ptr"))))
    return True
  end
  return False
end

def check-type (ty : str what : str line : int) -> int
  if (not (call known-type? ty))
    (call parse-fail-at (call string-append (call string-append what ": unknown type '") (call string-append ty "'")) line)
  end
  return 0
end

def is-reserved (tok : str) -> bool
  if (or (or (or (= tok "end") (= tok "else")) (or (= tok "def") (= tok "let"))) (or (or (= tok "set") (= tok "return")) (or (or (= tok "if") (= tok "while")) (= tok "for"))))
    return True
  end
  return False
end

def parse-stmts (tokens : str pos : int) -> tuple
  let stmts any (call py-list)
  let tmp tuple (call next-token tokens pos)
  let tok str (call vector-ref tmp 0)
  let pos2 int (call vector-ref tmp 1)
  while (and (not (= tok "end")) (not (= tok "else")))
    if (= tok "")
      (call parse-fail-at "unexpected end of input: missing 'end'" (call vector-ref tmp 2))
    end
    let tmp tuple (call parse-stmt tokens pos)
    let stmt any (call vector-ref tmp 0)
    set pos (call vector-ref tmp 1)
    set stmts (call list-append stmts stmt)
    set tmp (call next-token tokens pos)
    set tok (call vector-ref tmp 0)
    set pos2 (call vector-ref tmp 1)
  end
  return (call vector stmts pos)
end

def parse-stmt (tokens : str pos : int) -> tuple
  let tmp tuple (call next-token tokens pos)
  let tok str (call vector-ref tmp 0)
  let tok-line int (call vector-ref tmp 2)
  set pos (call vector-ref tmp 1)
  if (= tok "let")
    return (call parse-stmt-let tokens pos)
  else
    if (= tok "set")
      let tmp tuple (call next-token tokens pos)
      let name str (call vector-ref tmp 0)
      set pos (call vector-ref tmp 1)
      let tmp tuple (call parse-expr tokens pos)
      let value any (call vector-ref tmp 0)
      set pos (call vector-ref tmp 1)
      return (call vector (call SSet name value) pos)
    else
      if (= tok "return")
        let tmp tuple (call parse-expr tokens pos)
        let value any (call vector-ref tmp 0)
        set pos (call vector-ref tmp 1)
        return (call vector (call SReturn value) pos)
      else
        return (call parse-stmt-ctrl tokens pos tok tok-line)
      end
    end
  end
end

def parse-stmt-let (tokens : str pos : int) -> tuple
  let tmp tuple (call next-token tokens pos)
  let name str (call vector-ref tmp 0)
  set pos (call vector-ref tmp 1)
  let tmp tuple (call next-token tokens pos)
  let ty str (call vector-ref tmp 0)
  let ty-line int (call vector-ref tmp 2)
  set pos (call vector-ref tmp 1)
  (call check-type ty (call string-append "let " name) ty-line)
  let tmp tuple (call parse-expr tokens pos)
  let value any (call vector-ref tmp 0)
  set pos (call vector-ref tmp 1)
  return (call vector (call SLet name ty value) pos)
end

def parse-stmt-ctrl (tokens : str pos : int tok : str line : int) -> tuple
  if (= tok "if")
    let tmp tuple (call parse-expr tokens pos)
    let cond-expr any (call vector-ref tmp 0)
    set pos (call vector-ref tmp 1)
    let tmp tuple (call parse-stmts tokens pos)
    let then-body any (call vector-ref tmp 0)
    set pos (call vector-ref tmp 1)
    let else-body any (call py-list)
    let tmp tuple (call next-token tokens pos)
    let nxt str (call vector-ref tmp 0)
    let pos2 int (call vector-ref tmp 1)
    if (= nxt "else")
      set pos pos2
      set tmp (call parse-stmts tokens pos)
      set else-body (call vector-ref tmp 0)
      set pos (call vector-ref tmp 1)
    end
    let tmp tuple (call next-token tokens pos)
    let end-tok str (call vector-ref tmp 0)
    set pos (call vector-ref tmp 1)
    if (not (= end-tok "end"))
      (call parse-fail-at (call string-append (call string-append "expected 'end' to close 'if', found '") (call string-append end-tok "'")) (call vector-ref tmp 2))
    end
    return (call vector (call SIf cond-expr then-body else-body) pos)
  else
    return (call parse-stmt-loop tokens pos tok line)
  end
end

def parse-stmt-loop (tokens : str pos : int tok : str line : int) -> tuple
  let result any ""
  if (= tok "while")
    let tmp tuple (call parse-expr tokens pos)
    let cond-expr any (call vector-ref tmp 0)
    set pos (call vector-ref tmp 1)
    let tmp tuple (call parse-stmts tokens pos)
    let body any (call vector-ref tmp 0)
    set pos (call vector-ref tmp 1)
    let tmp tuple (call next-token tokens pos)
    let end-tok str (call vector-ref tmp 0)
    set pos (call vector-ref tmp 1)
    if (not (= end-tok "end"))
      (call parse-fail-at (call string-append (call string-append "expected 'end' to close 'while', found '") (call string-append end-tok "'")) (call vector-ref tmp 2))
    end
    set result (call SWhile cond-expr body)
    return (call vector result pos)
  else
    return (call parse-stmt-for tokens pos tok line)
  end
end

def parse-stmt-for (tokens : str pos : int tok : str line : int) -> tuple
  let result any ""
  if (= tok "for")
    let tmp tuple (call next-token tokens pos)
    let var str (call vector-ref tmp 0)
    set pos (call vector-ref tmp 1)
    let tmp tuple (call parse-expr tokens pos)
    let stop any (call vector-ref tmp 0)
    set pos (call vector-ref tmp 1)
    let tmp tuple (call parse-stmts tokens pos)
    let body any (call vector-ref tmp 0)
    set pos (call vector-ref tmp 1)
    let tmp tuple (call next-token tokens pos)
    let end-tok str (call vector-ref tmp 0)
    set pos (call vector-ref tmp 1)
    if (not (= end-tok "end"))
      (call parse-fail-at (call string-append (call string-append "expected 'end' to close 'for', found '") (call string-append end-tok "'")) (call vector-ref tmp 2))
    end
    set result (call SFor var stop body)
  else
    let tmp tuple (call parse-expr-at tokens pos tok line)
    let value any (call vector-ref tmp 0)
    set pos (call vector-ref tmp 1)
    set result (call SExpr value)
  end
  return (call vector result pos)
end

def parse-params (tokens : str pos : int) -> tuple
  let tmp tuple (call next-token tokens pos)
  let nxt str (call vector-ref tmp 0)
  let pos2 int (call vector-ref tmp 1)
  if (= nxt "")
    (call parse-fail-at "unexpected end of input in parameter list" (call vector-ref tmp 2))
  end
  if (= nxt ")")
    return (call vector (call py-list) (call py-list) pos2)
  end
  if (call known-type? nxt)
    (call parse-fail-at (call string-append (call string-append "parameter name missing before type '") (call string-append nxt "'")) (call vector-ref tmp 2))
  end
  return (call parse-param-rest tokens nxt pos2)
end

def parse-param-rest (tokens : str name : str pos : int) -> tuple
  let ty str ""
  let tmp tuple (call next-token tokens pos)
  let nxt str (call vector-ref tmp 0)
  let pos2 int (call vector-ref tmp 1)
  if (= nxt ":")
    set tmp (call next-token tokens pos2)
    set ty (call vector-ref tmp 0)
    set pos (call vector-ref tmp 1)
    set tmp (call next-token tokens pos)
    set nxt (call vector-ref tmp 0)
    set pos2 (call vector-ref tmp 1)
  end
  if (= nxt ",")
    set pos pos2
  end
  set tmp (call parse-params tokens pos)
  let rest-names any (call vector-ref tmp 0)
  let rest-types any (call vector-ref tmp 1)
  set pos (call vector-ref tmp 2)
  let names any (call py-list)
  set names (call list-append names name)
  set names (call list-append-all names rest-names)
  let types any (call py-list)
  set types (call list-append types ty)
  set types (call list-append-all types rest-types)
  return (call vector names types pos)
end

def parse-func (tokens : str pos : int) -> tuple
  let tmp tuple (call parse-func-sig tokens pos)
  let name str (call vector-ref tmp 0)
  let params any (call vector-ref tmp 1)
  let param-types any (call vector-ref tmp 2)
  let ret str (call vector-ref tmp 3)
  set pos (call vector-ref tmp 4)
  set tmp (call parse-stmts tokens pos)
  let body any (call vector-ref tmp 0)
  set pos (call vector-ref tmp 1)
  set tmp (call next-token tokens pos)
  let end-tok str (call vector-ref tmp 0)
  set pos (call vector-ref tmp 1)
  return (call vector (call IRFunc name params param-types ret body) pos)
end

def parse-func-sig (tokens : str pos : int) -> tuple
  let tmp tuple (call next-token tokens pos)
  let def-tok str (call vector-ref tmp 0)
  set pos (call vector-ref tmp 1)
  if (not (= def-tok "def"))
    (call parse-fail-at (call string-append (call string-append "expected 'def', found '") (call string-append def-tok "'")) (call vector-ref tmp 2))
  end
  set tmp (call next-token tokens pos)
  let name str (call vector-ref tmp 0)
  let name-line int (call vector-ref tmp 2)
  set pos (call vector-ref tmp 1)
  if (or (= name "") (call is-reserved name))
    (call parse-fail-at "function name expected after 'def'" name-line)
  end
  set tmp (call next-token tokens pos)
  let lparen str (call vector-ref tmp 0)
  let lparen-line int (call vector-ref tmp 2)
  set pos (call vector-ref tmp 1)
  if (not (= lparen "("))
    (call parse-fail-at (call string-append (call string-append (call string-append "expected '(' after function name " name) ", found '") (call string-append lparen "'")) lparen-line)
  end
  set tmp (call parse-params tokens pos)
  let params any (call vector-ref tmp 0)
  let param-types any (call vector-ref tmp 1)
  set pos (call vector-ref tmp 2)
  set tmp (call next-token tokens pos)
  let arrow str (call vector-ref tmp 0)
  let arrow-line int (call vector-ref tmp 2)
  set pos (call vector-ref tmp 1)
  if (not (= arrow "->"))
    (call parse-fail-at (call string-append (call string-append (call string-append "expected '->' after parameter list of " name) ", found '") (call string-append arrow "'")) arrow-line)
  end
  set tmp (call next-token tokens pos)
  let ret str (call vector-ref tmp 0)
  let ret-line int (call vector-ref tmp 2)
  set pos (call vector-ref tmp 1)
  (call check-type ret (call string-append "return type of " name) ret-line)
  return (call vector name params param-types ret pos)
end

def parse-funcs (tokens : str pos : int) -> tuple
  let tmp tuple (call next-token tokens pos)
  let tok str (call vector-ref tmp 0)
  let pos2 int (call vector-ref tmp 1)
  let result any (call py-list)
  if (not (= tok ""))
    set tmp (call parse-func tokens pos)
    let func any (call vector-ref tmp 0)
    set pos (call vector-ref tmp 1)
    set tmp (call parse-funcs tokens pos)
    let rest any (call vector-ref tmp 0)
    set pos (call vector-ref tmp 1)
    set result (call list-append result func)
    set result (call list-append-all result rest)
  end
  return (call vector result pos)
end

def parse-program (tokens : str) -> any
  let tmp any (call parse-funcs tokens 0)
  let funcs any (call vector-ref tmp 0)
  if (= (call list-length funcs) 0)
    (call parse-fail "empty program: no function definitions")
  end
  let tmp2 tuple (call next-token tokens (call vector-ref tmp 1))
  let tok2 str (call vector-ref tmp2 0)
  if (not (= tok2 ""))
    (call parse-fail-at (call string-append "unexpected trailing token after last function: " tok2) (call vector-ref tmp2 2))
  end
  return funcs
end

# ========== type environment ==========

def const-is-float (v : str) -> bool
  let i int 0
  let n int (call list-length v)
  while (< i n)
    let c str (call substring v i (+ i 1))
    if (or (= c ".") (or (= c "e") (= c "E")))
      return True
    end
    set i (+ i 1)
  end
  return False
end

def expr-type (expr env) -> str
  let result str "Any"
  if (call ir-tag? expr "EConst")
    let v str (call ir-field expr "value")
    if (= v "") set result "str"
    else
      let first str (call substring v 0 1)
      if (= first "\"") set result "str"
      else
        if (or (or (call is-digit first) (= first "-")) (= first "."))
          if (call const-is-float v) set result "float"
          else set result "int"
          end
        end
      end
    end
  else
    if (call ir-tag? expr "EVar")
      let t str (call dict_get_or_empty env (call ir-field expr "name"))
      if (not (= t "")) set result t
      else set result "Any"
      end
    else
      return (call expr-type-binop expr env)
    end
  end
  return result
end

def expr-type-binop (expr env) -> str
  let result str "Any"
  if (call ir-tag? expr "EBinop")
    let lt str (call expr-type (call ir-field expr "left") env)
    let rt str (call expr-type (call ir-field expr "right") env)
    let op str (call ir-field expr "op")
    if (or (or (or (= op "+") (= op "-")) (= op "*")) (= op "/"))
      if (or (= lt "float") (= rt "float")) set result "float"
      else
        if (and (= lt "int") (= rt "int")) set result "int"
        else
          if (= op "+")
            if (or (= lt "str") (= rt "str")) set result "str"
            end
          end
        end
      end
    else set result "bool"
    end
  else
    if (call ir-tag? expr "EUnary")
      if (= (call ir-field expr "op") "not") set result "bool"
      else set result (call expr-type (call ir-field expr "operand") env)
      end
    end
  end
  return result
end

def collect-func-env (func) -> any
  let env any (call make_dict)
  let i int 0
  let n int (call list-length (call ir-field func "params"))
  while (< i n)
    let ty str (call list-ref (call ir-field func "param-types") i)
    if (= ty "") set ty "Any"
    end
    (call dict_set env (call list-ref (call ir-field func "params") i) ty)
    set i (+ i 1)
  end
  return env
end

def add-env-binding (env name ty) -> any
  if (= ty "") set ty "Any"
  end
  (call dict_set env name ty)
  return env
end

# ========== codegen helpers ==========

def build2 (a b) -> str
  let tmp str (call string-append a b)
  return tmp
end

def build3 (a b c) -> str
  let tmp str (call string-append a b)
  return (call string-append tmp c)
end

def build4 (a b c d) -> str
  let tmp str (call string-append a b)
  set tmp (call string-append tmp c)
  return (call string-append tmp d)
end

def build5 (a b c d e) -> str
  let tmp str (call string-append a b)
  set tmp (call string-append tmp c)
  set tmp (call string-append tmp d)
  return (call string-append tmp e)
end

def build6 (a b c d e f) -> str
  let tmp str (call string-append a b)
  set tmp (call string-append tmp c)
  set tmp (call string-append tmp d)
  set tmp (call string-append tmp e)
  return (call string-append tmp f)
end

def build7 (a b c d e f g) -> str
  let tmp str (call string-append a b)
  set tmp (call string-append tmp c)
  set tmp (call string-append tmp d)
  set tmp (call string-append tmp e)
  set tmp (call string-append tmp f)
  return (call string-append tmp g)
end

def build8 (a b c d e f g h) -> str
  let tmp str (call string-append a b)
  set tmp (call string-append tmp c)
  set tmp (call string-append tmp d)
  set tmp (call string-append tmp e)
  set tmp (call string-append tmp f)
  set tmp (call string-append tmp g)
  return (call string-append tmp h)
end

def build9 (a b c d e f g h i) -> str
  let tmp str (call string-append a b)
  set tmp (call string-append tmp c)
  set tmp (call string-append tmp d)
  set tmp (call string-append tmp e)
  set tmp (call string-append tmp f)
  set tmp (call string-append tmp g)
  set tmp (call string-append tmp h)
  return (call string-append tmp i)
end

def build10 (a b c d e f g h i j) -> str
  let tmp str (call string-append a b)
  set tmp (call string-append tmp c)
  set tmp (call string-append tmp d)
  set tmp (call string-append tmp e)
  set tmp (call string-append tmp f)
  set tmp (call string-append tmp g)
  set tmp (call string-append tmp h)
  set tmp (call string-append tmp i)
  return (call string-append tmp j)
end

def build11 (a b c d e f g h i j k) -> str
  let tmp str (call string-append a b)
  set tmp (call string-append tmp c)
  set tmp (call string-append tmp d)
  set tmp (call string-append tmp e)
  set tmp (call string-append tmp f)
  set tmp (call string-append tmp g)
  set tmp (call string-append tmp h)
  set tmp (call string-append tmp i)
  set tmp (call string-append tmp j)
  return (call string-append tmp k)
end

def build12 (a b c d e f g h i j k l) -> str
  let tmp str (call string-append a b)
  set tmp (call string-append tmp c)
  set tmp (call string-append tmp d)
  set tmp (call string-append tmp e)
  set tmp (call string-append tmp f)
  set tmp (call string-append tmp g)
  set tmp (call string-append tmp h)
  set tmp (call string-append tmp i)
  set tmp (call string-append tmp j)
  set tmp (call string-append tmp k)
  return (call string-append tmp l)
end

def build13 (a b c d e f g h i j k l m) -> str
  let tmp str (call string-append a b)
  set tmp (call string-append tmp c)
  set tmp (call string-append tmp d)
  set tmp (call string-append tmp e)
  set tmp (call string-append tmp f)
  set tmp (call string-append tmp g)
  set tmp (call string-append tmp h)
  set tmp (call string-append tmp i)
  set tmp (call string-append tmp j)
  set tmp (call string-append tmp k)
  set tmp (call string-append tmp l)
  return (call string-append tmp m)
end

def build14 (a b c d e f g h i j k l m n) -> str
  let tmp str (call string-append a b)
  set tmp (call string-append tmp c)
  set tmp (call string-append tmp d)
  set tmp (call string-append tmp e)
  set tmp (call string-append tmp f)
  set tmp (call string-append tmp g)
  set tmp (call string-append tmp h)
  set tmp (call string-append tmp i)
  set tmp (call string-append tmp j)
  set tmp (call string-append tmp k)
  set tmp (call string-append tmp l)
  set tmp (call string-append tmp m)
  return (call string-append tmp n)
end


def emit-plus (left right lt rt) -> str
  if (or (= lt "str") (= rt "str"))
    return (call make-binop-str "string-append" left right)
  else
    if (or (= lt "float") (= rt "float"))
      return (call make-binop-str "fl+" left right)
    else
      if (and (= lt "int") (= rt "int"))
        return (call make-binop-str "fx+" left right)
      else
        return (call make-binop-str "+" left right)
      end
    end
  end
end

def emit-eq (left right lt rt) -> str
  if (and (= lt "str") (= rt "str"))
    return (call make-binop-str "string=?" left right)
  else
    if (or (= lt "float") (= rt "float"))
      return (call make-binop-str "fl=" left right)
    else
      if (and (= lt "int") (= rt "int"))
        return (call make-binop-str "fx=" left right)
      else
        return (call make-binop-str "equal?" left right)
      end
    end
  end
end

def emit-lt (left right lt rt) -> str
  if (and (= lt "str") (= rt "str"))
    return (call make-binop-str "string<?" left right)
  else
    if (or (= lt "float") (= rt "float"))
      return (call make-binop-str "fl<" left right)
    else
      if (and (= lt "int") (= rt "int"))
        return (call make-binop-str "fx<" left right)
      else
        return (call make-binop-str "<" left right)
      end
    end
  end
end

def emit-gt (left right lt rt) -> str
  if (and (= lt "str") (= rt "str"))
    return (call make-binop-str "string>?" left right)
  else
    if (or (= lt "float") (= rt "float"))
      return (call make-binop-str "fl>" left right)
    else
      if (and (= lt "int") (= rt "int"))
        return (call make-binop-str "fx>" left right)
      else
        return (call make-binop-str ">" left right)
      end
    end
  end
end

def emit-minus (left right lt rt) -> str
  if (or (= lt "float") (= rt "float"))
    return (call make-binop-str "fl-" left right)
  else
    if (and (= lt "int") (= rt "int"))
      return (call make-binop-str "fx-" left right)
    else
      return (call make-binop-str "-" left right)
    end
  end
end

def emit-mult (left right lt rt) -> str
  if (or (= lt "float") (= rt "float"))
    return (call make-binop-str "fl*" left right)
  else
    if (and (= lt "int") (= rt "int"))
      return (call make-binop-str "fx*" left right)
    else
      return (call make-binop-str "*" left right)
    end
  end
end

def emit-div (left right lt rt) -> str
  if (or (= lt "float") (= rt "float"))
    return (call make-binop-str "fl/" left right)
  else
    if (and (= lt "int") (= rt "int"))
      return (call make-binop-str "fx/" left right)
    else
      return (call make-binop-str "/" left right)
    end
  end
end

def emit-le (left right lt rt) -> str
  if (and (= lt "str") (= rt "str"))
    return (call make-binop-str "string<=?" left right)
  else
    if (or (= lt "float") (= rt "float"))
      return (call make-binop-str "fl<=" left right)
    else
      if (and (= lt "int") (= rt "int"))
        return (call make-binop-str "fx<=?" left right)
      else
        return (call make-binop-str "<=" left right)
      end
    end
  end
end

def emit-ge (left right lt rt) -> str
  if (and (= lt "str") (= rt "str"))
    return (call make-binop-str "string>=?" left right)
  else
    if (or (= lt "float") (= rt "float"))
      return (call make-binop-str "fl>=" left right)
    else
      if (and (= lt "int") (= rt "int"))
        return (call make-binop-str "fx>=?" left right)
      else
        return (call make-binop-str ">=" left right)
      end
    end
  end
end

def make-binop-str (op-str left right) -> str
  let tmp str (call string-append op-str " ")
  set tmp (call string-append tmp left)
  set tmp (call string-append tmp " ")
  set tmp (call string-append tmp right)
  return (call build3 "(" tmp ")")
end

# ========== codegen ==========

def emit-expr (expr env) -> str
  if (call ir-tag? expr "EConst")
    let v str (call ir-field expr "value")
    if (= v "") return "\"\""
    else
      let first str (call substring v 0 1)
      if (= first "\"") return v
      else return v
      end
    end
  else
    if (call ir-tag? expr "EVar")
      return (call ir-field expr "name")
    else
      if (call ir-tag? expr "EBinop")
        let left str (call emit-expr (call ir-field expr "left") env)
        let right str (call emit-expr (call ir-field expr "right") env)
        return (call emit-binary (call ir-field expr "op") left right (call ir-field expr "left") (call ir-field expr "right") env)
      else
        if (call ir-tag? expr "EUnary")
          return (call emit-unary expr env)
        else
          if (call ir-tag? expr "ECall")
            return (call emit-expr-call expr env)
          else
            if (call ir-tag? expr "ELambda")
              return (call emit-lambda expr env)
            else
              (call parse-fail "internal: unknown expression node")
              return "0"
            end
          end
        end
      end
    end
  end
end

def emit-unary (expr env) -> str
  let op str (call ir-field expr "op")
  let operand str (call emit-expr (call ir-field expr "operand") env)
  if (= op "not")
    return (call string-append (call string-append "(not " operand) ")")
  else
    return (call string-append (call string-append "(" op) (call string-append " " operand) ")")
  end
end

def emit-lambda (expr env) -> str
  let params any (call ir-field expr "params")
  let i int 0
  let n int (call list-length params)
  while (< i n)
    (call add-env-binding env (call list-ref params i) "Any")
    set i (+ i 1)
  end
  let body-expr str (call emit-block (call ir-field expr "body") env "  ")
  return (call build5 "(lambda (" (call func-params-to-str params) ") " body-expr ")")
end

def emit-expr-call (expr env) -> str
  let result str (call string-append "(" (call ir-field expr "func"))
  let args any (call ir-field expr "args")
  let i int 0
  let n int (call list-length args)
  while (< i n)
    set result (call string-append (call string-append result " ") (call emit-expr (call list-ref args i) env))
    set i (+ i 1)
  end
  return (call string-append result ")")
end

def emit-binary (op left right ln rn env) -> str
  let lt str (call expr-type ln env)
  let rt str (call expr-type rn env)
  if (= op "+") return (call emit-plus left right lt rt)
  else
    if (= op "-") return (call emit-minus left right lt rt)
    else
      if (= op "*") return (call emit-mult left right lt rt)
      else
        if (= op "/") return (call emit-div left right lt rt)
        else
          if (or (= op "==") (= op "=")) return (call emit-eq left right lt rt)
          else
            if (= op "!=")
              let inner str (call emit-binary "==" left right ln rn env)
              return (call string-append (call string-append "(not " inner) ")")
            else
              return (call emit-binary-cmp op left right lt rt)
            end
          end
        end
      end
    end
  end
end

def emit-binary-cmp (op left right lt rt) -> str
  if (= op "<") return (call emit-lt left right lt rt)
  else
    if (= op ">") return (call emit-gt left right lt rt)
    else
      if (= op "<=") return (call emit-le left right lt rt)
      else
        if (= op ">=") return (call emit-ge left right lt rt)
        else
          if (= op "and") return (call make-binop-str "and" left right)
          else
            if (= op "or") return (call make-binop-str "or" left right)
            else
              (call parse-fail (call string-append (call string-append "unsupported binary operator '" op) "'"))
              return "0"
            end
          end
        end
      end
    end
  end
end

def emit-block (stmts env indent) -> str
  let n int (call list-length stmts)
  if (= n 0) return "(void)"
  end
  let first any (call list-ref stmts 0)
  if (call ir-tag? first "SLet")
    let binding str (call build5 "(" (call ir-field first "name") " " (call emit-expr (call ir-field first "value") env) ")")
    (call add-env-binding env (call ir-field first "name") (call ir-field first "ty"))
    let rest any (call list-ref-range stmts 1 n)
    let rest-expr str (call emit-block rest env (call string-append indent "  "))
    let r0 str (call string-append "(let (" binding ")\n")
  set r0 (call string-append r0 indent)
  set r0 (call string-append r0 "  ")
  set r0 (call string-append r0 rest-expr)
  set r0 (call string-append r0 ")")
  return r0
  end
  return (call emit-raw-block stmts env indent)
end

def emit-raw-block (stmts env indent) -> str
  let n int (call list-length stmts)
  if (= n 0) return "(void)"
  end
  let parts any (call py-list)
  let i int 0
  while (< i n)
    let stmt any (call list-ref stmts i)
    if (call ir-tag? stmt "SLet")
      return (call emit-block-let stmts env indent parts i n)
    else
      set parts (call list-append parts (call emit-stmt stmt env (call string-append indent "  ")))
      set i (+ i 1)
    end
  end
  if (= (call list-length parts) 1) return (call list-ref parts 0)
  end
  let joiner str (call string-append (call string-append "\n" indent) "  ")
  let joined str (call str-join parts joiner)
  let result str (call string-append "(begin\n" indent "  " joined)
  set result (call string-append result "\n" indent ")")
  return result
end

def emit-block-let (stmts env indent parts i n) -> str
  let prefix str ""
  if (= (call list-length parts) 1) set prefix (call list-ref parts 0)
  else
    if (> (call list-length parts) 1)
      let joiner str (call string-append (call string-append "\n" indent) "  ")
      let joined str (call str-join parts joiner)
      let p str (call string-append "(begin\n" indent)
      set p (call string-append p "  ")
      set p (call string-append p joined)
      set p (call string-append p "\n")
      set p (call string-append p indent)
      set p (call string-append p ")")
      set prefix p
    end
  end
  let rest any (call list-ref-range stmts i n)
  let rest-expr str (call emit-block rest env indent)
  if (= prefix "") return rest-expr
  end
  let tmp-r str (call string-append "(begin\n" indent "  " prefix)
  set tmp-r (call string-append tmp-r "\n" indent "  ")
  set tmp-r (call string-append tmp-r rest-expr)
  set tmp-r (call string-append tmp-r "\n" indent ")")
  return tmp-r
end

def emit-stmt (stmt env indent) -> str
  if (call ir-tag? stmt "SLet")
    let name str (call ir-field stmt "name")
    let val str (call emit-expr (call ir-field stmt "value") env)
    return (call build5 "(let ((" name " " val ")) (void))")
  else
    if (call ir-tag? stmt "SSet")
      let name str (call ir-field stmt "name")
      let val str (call emit-expr (call ir-field stmt "value") env)
      return (call build5 "(set! " name " " val ")")
    else
      if (call ir-tag? stmt "SReturn")
        let val str (call emit-expr (call ir-field stmt "value") env)
        return (call string-append "(__return__ " val ")")
      else
        if (call ir-tag? stmt "SExpr")
          return (call emit-expr (call ir-field stmt "value") env)
        else
          return (call emit-stmt-ctrl stmt env indent)
        end
      end
    end
  end
end

def emit-stmt-ctrl (stmt env indent) -> str
  if (call ir-tag? stmt "SIf")
    let c str (call emit-expr (call ir-field stmt "cond-expr") env)
    let then-expr str (call emit-block (call ir-field stmt "then-body") env indent)
    let else-expr str (call emit-block (call ir-field stmt "else-body") env indent)
    let r str (call string-append "(if " c "\n")
    set r (call string-append r indent)
    set r (call string-append r then-expr)
    set r (call string-append r "\n")
    set r (call string-append r indent)
    set r (call string-append r else-expr)
    set r (call string-append r ")")
    return r
  else
    return (call emit-stmt-loop stmt env indent)
  end
end

def emit-stmt-loop (stmt env indent) -> str
  if (call ir-tag? stmt "SWhile")
    let c str (call emit-expr (call ir-field stmt "cond-expr") env)
    let body-expr str (call emit-block (call ir-field stmt "body") env indent)
    let tail str (call string-append (call string-append "\n" indent) "    (loop)))")
    return (call build9 "(let loop ()\n" indent "  (when " c "\n" indent "    " body-expr tail)
  else
    return (call emit-stmt-for stmt env indent)
  end
end

def emit-stmt-for (stmt env indent) -> str
  if (call ir-tag? stmt "SFor")
    let stop str (call emit-expr (call ir-field stmt "stop") env)
    let body-expr str (call emit-block (call ir-field stmt "body") env indent)
    let r str (call string-append "(do ((" (call ir-field stmt "var"))
    set r (call string-append r " 0 (fx+ " (call ir-field stmt "var") " 1)))\n")
    set r (call string-append r indent)
    set r (call string-append r "    ((fx>=? " (call ir-field stmt "var") " " stop "))\n")
    set r (call string-append r indent)
    set r (call string-append r "  " body-expr)
    set r (call string-append r ")")
    return r
  else
    (call parse-fail "internal: unknown statement node")
    return "0"
  end
end

def emit-func (func) -> str
  let env any (call collect-func-env func)
  let body-expr str (call emit-block (call ir-field func "body") env "  ")
  let wrapped str (call build3 "(call/cc (lambda (__return__)" body-expr "))")
  let params-str str (call func-params-to-str (call ir-field func "params"))
  if (= params-str "")
    let r5 str (call string-append "(define (" (call ir-field func "name") ")\n  ")
    set r5 (call string-append r5 wrapped)
    set r5 (call string-append r5 ")\n")
    return r5
  else
    let r6 str (call string-append "(define (" (call ir-field func "name") " " params-str ")\n  ")
    set r6 (call string-append r6 wrapped)
    set r6 (call string-append r6 ")\n")
    return r6
  end
end

def emit-program (funcs) -> str
  let sb any (call sb-new)
  (call sb-write sb ";; generated by staticc.sp\n")
  (call sb-write sb "(import (chezscheme))\n")
  let i int 0
  let n int (call list-length funcs)
  while (< i n)
    (call sb-write sb (call emit-func (call list-ref funcs i)))
    set i (+ i 1)
  end
  (call sb-write sb "(main)\n")
  return (call sb-string sb)
end

def compile-file (path : str) -> str
  let fp any (call file_open path "r")
  let src str (call file_read_all fp)
  (call file_close fp)
  let tokens str (call tokenize src)
  let funcs any (call parse-program tokens)
  return (call emit-program funcs)
end

def main () -> int
  let args any (call argv)
  if (< (call list-length args) 3)
    (call print "usage: staticc <input.sp> <output.scm>")
    return 1
  end
  let inp str (call list-ref args 1)
  let out-path str (call list-ref args 2)
  let scm str (call compile-file inp)
  let fp any (call file_open out-path "w")
  (call file_write fp scm)
  (call file_close fp)
  return 0
end
