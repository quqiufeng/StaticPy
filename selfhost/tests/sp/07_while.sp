def main () -> int
  let i int 0
  let sum int 0
  while (< i 5)
    set sum (+ sum i)
    set i (+ i 1)
  end
  (call print sum)
  return 0
end
