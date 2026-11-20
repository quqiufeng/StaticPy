def apply-twice (f : any x : int) -> int
  return (call f (call f x))
end

def make-adder (n : int) -> any
  return (lambda (x) (+ x n))
end

def main () -> int
  let inc any (lambda (x) (+ x 1))
  (call print (call apply-twice inc 5))
  let add10 any (call make-adder 10)
  (call print (call add10 32))
  return 0
end
