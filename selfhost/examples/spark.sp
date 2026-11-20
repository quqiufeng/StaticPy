# spark.sp — 迷你矢量图 DSL → SVG
# 演示用 .sp 写一个完整 DSL 前端（词法 + 语法 + 发射），产物是独立 ELF。
#
#   canvas 320 200
#   rect 10 10 80 40 fill=#e8543f
#   circle 160 100 45 fill=#3f7ae8
#   line 0 0 320 200 stroke=#333333
#   text 12 190 "hello spark"
#
#   ./spark in.spark out.svg

# ========== 基础 ==========
def str-ref (s : str i : int) -> str
  return (call substring s i (+ i 1))
end

def is-hex? (c : str) -> bool
  if (and (>= c "0") (<= c "9")) return True end
  if (and (>= c "a") (<= c "f")) return True end
  if (and (>= c "A") (<= c "F")) return True end
  return False
end

def is-space? (c : str) -> bool
  return (or (or (or (= c " ") (= c "\t")) (= c "\n")) (= c "\r"))
end

def fail (msg : str) -> int
  (call display (call string-append "spark: " (call string-append msg "\n")) (call current-error-port))
  (call exit-program 1)
  return 1
end

# ========== 词法 ==========
# token 三种：裸字（数字/指令名/key=value）、"字符串"（前缀 S 标记）、其余同裸字
def tokenize (src : str) -> list
  let toks list (call list)
  let i int 0
  let n int (call list_length src)
  while (< i n)
    if (call is-space? (call str-ref src i))
      set i (+ i 1)
    else
      if (= (call str-ref src i) "\"")
        set i (+ i 1)
        let start int i
        while (and (< i n) (not (= (call str-ref src i) "\"")))
          set i (+ i 1)
        end
        if (>= i n)
          (call fail "unterminated string literal")
        end
        set toks (call append toks (call list (call string-append "S" (call substring src start i))))
        set i (+ i 1)
      else
        if (and (= (call str-ref src i) "#") (not (and (< (+ i 1) n) (call is-hex? (call str-ref src (+ i 1))))))
          while (and (< i n) (not (= (call str-ref src i) "\n")))
            set i (+ i 1)
          end
        else
        let start int i
        while (and (< i n) (not (call is-space? (call str-ref src i))))
          set i (+ i 1)
        end
        if (> i start)
          set toks (call append toks (call list (call substring src start i)))
        end
        end
      end
    end
  end
  return toks
end

# ========== 语义辅助 ==========
def has-eq? (tok : str) -> bool
  let i int 0
  let n int (call list_length tok)
  while (< i n)
    if (= (call str-ref tok i) "=") return True end
    set i (+ i 1)
  end
  return False
end

def str-prefix? (p : str tok : str) -> bool
  if (< (call list_length tok) (call list_length p)) return False end
  return (= (call substring tok 0 (call list_length p)) p)
end

# "fill=#ff0000" → ` fill="#ff0000"`
def kv-attr (tok : str) -> str
  let i int 0
  let n int (call list_length tok)
  while (< i n)
    if (= (call str-ref tok i) "=")
      return (call string-append (call string-append (call string-append " " (call substring tok 0 i)) "=\"") (call string-append (call substring tok (+ i 1) n) "\""))
    end
    set i (+ i 1)
  end
  return ""
end

def attr-of (tok : str) -> str
  if (call has-eq? tok) return (call kv-attr tok) end
  return ""
end

def is-attr? (tok : str) -> bool
  return (call has-eq? tok)
end

# ========== 发射 ==========
def compile (toks : list) -> str
  let nt int (call list_length toks)
  if (< nt 3) (call fail "expected 'canvas <w> <h>'") end
  if (not (= (call list-ref toks 0) "canvas"))
    (call fail (call string-append "expected 'canvas', got '" (call string-append (call list-ref toks 0) "'")))
  end
  let w str (call list-ref toks 1)
  let h str (call list-ref toks 2)
  let sb any (call open-output-string)
  (call display (call string-append "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"" (call string-append w (call string-append "\" height=\"" (call string-append h "\">\n")))) sb)
  (call display (call string-append "<rect width=\"" (call string-append w (call string-append "\" height=\"" (call string-append h "\" fill=\"#ffffff\"/>\n")))) sb)
  let pc int 3
  while (< pc nt)
    let d str (call list-ref toks pc)
    if (= d "rect")
      if (>= (+ pc 5) nt) (call fail "rect needs x y w h") end
      (call display "<rect x=\"" sb)
      (call display (call list-ref toks (+ pc 1)) sb)
      (call display "\" y=\"" sb)
      (call display (call list-ref toks (+ pc 2)) sb)
      (call display "\" width=\"" sb)
      (call display (call list-ref toks (+ pc 3)) sb)
      (call display "\" height=\"" sb)
      (call display (call list-ref toks (+ pc 4)) sb)
      (call display "\"" sb)
      set pc (+ pc 5)
      if (and (< pc nt) (call is-attr? (call list-ref toks pc)))
        (call display (call attr-of (call list-ref toks pc)) sb)
        set pc (+ pc 1)
      end
      (call display "/>\n" sb)
    else
      if (= d "circle")
        if (>= (+ pc 4) nt) (call fail "circle needs cx cy r") end
        (call display "<circle cx=\"" sb)
        (call display (call list-ref toks (+ pc 1)) sb)
        (call display "\" cy=\"" sb)
        (call display (call list-ref toks (+ pc 2)) sb)
        (call display "\" r=\"" sb)
        (call display (call list-ref toks (+ pc 3)) sb)
        (call display "\"" sb)
        set pc (+ pc 4)
        if (and (< pc nt) (call is-attr? (call list-ref toks pc)))
          (call display (call attr-of (call list-ref toks pc)) sb)
          set pc (+ pc 1)
        end
        (call display "/>\n" sb)
      else
        if (= d "line")
          if (>= (+ pc 5) nt) (call fail "line needs x1 y1 x2 y2") end
          (call display "<line x1=\"" sb)
          (call display (call list-ref toks (+ pc 1)) sb)
          (call display "\" y1=\"" sb)
          (call display (call list-ref toks (+ pc 2)) sb)
          (call display "\" x2=\"" sb)
          (call display (call list-ref toks (+ pc 3)) sb)
          (call display "\" y2=\"" sb)
          (call display (call list-ref toks (+ pc 4)) sb)
          (call display "\" stroke-width=\"2\"" sb)
          set pc (+ pc 5)
          if (and (< pc nt) (call is-attr? (call list-ref toks pc)))
            (call display (call attr-of (call list-ref toks pc)) sb)
            set pc (+ pc 1)
          end
          (call display "/>\n" sb)
        else
          if (= d "text")
            if (>= (+ pc 3) nt) (call fail "text needs x y \"str\"") end
            let body str (call list-ref toks (+ pc 3))
            if (not (call str-prefix? "S" body))
              (call fail "text content must be a quoted string")
            end
            (call display "<text x=\"" sb)
            (call display (call list-ref toks (+ pc 1)) sb)
            (call display "\" y=\"" sb)
            (call display (call list-ref toks (+ pc 2)) sb)
            (call display "\" font-size=\"14\" font-family=\"monospace\"" sb)
            set pc (+ pc 4)
            if (and (< pc nt) (call is-attr? (call list-ref toks pc)))
              (call display (call attr-of (call list-ref toks pc)) sb)
              set pc (+ pc 1)
            end
            (call display ">" sb)
            (call display (call substring body 1 (call list_length body)) sb)
            (call display "</text>\n" sb)
          else
            (call fail (call string-append "unknown directive '" (call string-append d "'")))
          end
        end
      end
    end
  end
  (call display "</svg>\n" sb)
  return (call get-output-string sb)
end

# ========== 驱动 ==========
def main () -> int
  let av list (call argv)
  if (< (call list_length av) 3)
    (call fail "usage: spark <in.spark> <out.svg>")
  end
  let fp-in ptr (call file-open (call list-ref av 1) "r")
  if (= fp-in 0) (call fail (call string-append "cannot open " (call list-ref av 1))) end
  let src str (call file-read-all fp-in)
  (call file-close fp-in)
  let toks list (call tokenize src)
  let svg str (call compile toks)
  let fp ptr (call file-open (call list-ref av 2) "w")
  (call file-write fp svg)
  (call file-close fp)
  (call print (call string-append (call string_of_int (call list_length toks)) " tokens -> written"))
  return 0
end
