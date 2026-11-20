def join3 (a : str b : str c : str) -> str
  let r str (call string-append a b)
  return (call string-append r c)
end

def main () -> int
  let out str ""
  let i int 0
  while (< i 4)
    set out (+ out (call join3 "a" "b" "c"))
    set i (+ i 1)
  end
  (call print out)
  return 0
end
