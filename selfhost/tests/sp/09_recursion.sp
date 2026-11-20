def fib (n : int) -> int
  if (< n 2)
    return n
  end
  return (+ (call fib (- n 1)) (call fib (- n 2)))
end

def main () -> int
  (call print (call fib 15))
  return 0
end
