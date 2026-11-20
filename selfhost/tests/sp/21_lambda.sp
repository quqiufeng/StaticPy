def main () -> int
  let inc any (lambda (x) (+ x 1))
  (call print (call inc 41))
  let add any (lambda (a b) (+ a b))
  (call print (call add 3 4))
  let msg any (lambda () "hi")
  (call print (call msg))
  return 0
end
