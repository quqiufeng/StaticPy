def make-pair (a : int b : int) -> any
  return (call vector a b)
end

def main () -> int
  let p any (call make-pair 3 4)
  (call print (call vector-ref p 0))
  (call print (call vector-ref p 1))
  return 0
end
