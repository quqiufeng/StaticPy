# staticc.sp — StaticPy subset compiler written in .sp syntax.
#
# ========== tokenizer ==========

def str-ref (s : str i : int) -> str
  return (call substring s i (+ i 1))
end

def is-digit (c : str) -> bool
  return (and (>= c "0") (<= c "9"))
end

def is-alpha (c : str) -> bool
  return (or (and (>= c "a") (<= c "z")) (and (>= c "A") (<= c "Z")))
end

def is-alnum (c : str) -> bool
  return (or (or (call is-alpha c) (call is-digit c)) (or (= c "_") (= c "-")))
end


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
  let result str ""
  let i int 0
  let n int (call list-length parts)
  while (< i n)
    if (= i 0)
      set result (call list-ref parts i)
    else
      set result (call string-append (call string-append result sep-str) (call list-ref parts i))
    end
    set i (+ i 1)
  end
  return result
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
  if (and (= lt "str") (= rt "str"))
    return (call make-binop-str "string-append" left right)
  else
    if (or (= lt "float") (= rt "float"))
      return (call make-binop-str "fl+" left right)
    else
      if (and (= lt "int") (= rt "int"))
        return (call make-binop-str "fx+" left right)
      else
        return (call make-binop-str "string-append" left right)
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
        return (call make-binop-str "string=?" left right)
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
        return (call make-binop-str "string<?" left right)
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
        return (call make-binop-str "string>?" left right)
      end
    end
  end
end

def emit-minus (left right lt rt) -> str
  if (or (= lt "float") (= rt "float"))
    return (call make-binop-str "fx-" left right)
  else
    if (and (= lt "int") (= rt "int"))
      return (call make-binop-str "" left right)
    else
      return (call make-binop-str "fl-" left right)
    end
  end
end

def emit-mult (left right lt rt) -> str
  if (or (= lt "float") (= rt "float"))
    return (call make-binop-str "fx*" left right)
  else
    if (and (= lt "int") (= rt "int"))
      return (call make-binop-str "*" left right)
    else
      return (call make-binop-str "fl*" left right)
    end
  end
end

def emit-div (left right lt rt) -> str
  if (or (= lt "float") (= rt "float"))
    return (call make-binop-str "fx/" left right)
  else
    if (and (= lt "int") (= rt "int"))
      return (call make-binop-str "/" left right)
    else
      return (call make-binop-str "fl/" left right)
    end
  end
end

def emit-le (left right lt rt) -> str
  if (or (= lt "float") (= rt "float"))
    return (call make-binop-str "fx<=?" left right)
  else
    if (and (= lt "int") (= rt "int"))
      return (call make-binop-str "<=?" left right)
    else
      return (call make-binop-str "fl<=" left right)
    end
  end
end

def emit-ge (left right lt rt) -> str
  if (or (= lt "float") (= rt "float"))
    return (call make-binop-str "fx>=?" left right)
  else
    if (and (= lt "int") (= rt "int"))
      return (call make-binop-str ">=?" left right)
    else
      return (call make-binop-str "fl>=" left right)
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
          let op str (call ir-field expr "op")
          let operand str (call emit-expr (call ir-field expr "operand") env)
          if (= op "not")
            return (call string-append (call string-append "(not " operand) ")")
          else
            return (call string-append (call string-append "(" op) (call string-append " " operand) ")")
          end
        else
          if (call ir-tag? expr "ECall")
            let result str (call string-append "(" (call ir-field expr "func"))
            let args any (call ir-field expr "args")
            let i int 0
  let n int (call list-length args)
            while (< i n)
              set result (call string-append (call string-append result " ") (call emit-expr (call list-ref args i) env))
              set i (+ i 1)
            end
            return (call string-append result ")")
          else return "#<expr>"
          end
        end
      end
    end
  end
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
                          else return (call make-binop-str (call string-append "__unknown__ " op) left right)
                        end
                      end
                    end
                  end
                end
              end
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
            if (call ir-tag? stmt "SWhile")
              let c str (call emit-expr (call ir-field stmt "cond-expr") env)
              let body-expr str (call emit-block (call ir-field stmt "body") env indent)
              let tail str (call string-append (call string-append "\n" indent) "    (loop)))")
              return (call build9 "(let loop ()\n" indent "  (when " c "\n" indent "    " body-expr tail)
            else
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
              else return "#<stmt>"
              end
            end
          end
        end
      end
    end
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
  let nl str (call string (call integer->char 10))
  let out str ";; generated by staticc.sp"
  set out (call string-append out nl)
  set out (call string-append out "(import (chezscheme))")
  set out (call string-append out nl)
  let i int 0
  let n int (call list-length funcs)
  while (< i n)
    set out (call string-append out (call emit-func (call list-ref funcs i)))
    set i (+ i 1)
  end
  set out (call string-append out "(main)")
  set out (call string-append out nl)
  return out
end
