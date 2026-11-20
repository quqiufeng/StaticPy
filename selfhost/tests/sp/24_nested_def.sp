def outer (n : int) -> int
  def sq (x : int) -> int
    return (* x x)
  end
  return (+ (call sq n) (call sq (+ n 1)))
end

def main () -> int
  (call print (call outer 3))
  return 0
end
