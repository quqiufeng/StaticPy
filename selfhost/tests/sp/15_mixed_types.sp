def total (n : int) -> float
  let s float 0.0
  let i int 0
  while (< i n)
    set s (+ s 0.5)
    set i (+ i 1)
  end
  return s
end

def main () -> int
  let t float (call total 6)
  (call print t)
  (call print (< t 10.0))
  return 0
end
