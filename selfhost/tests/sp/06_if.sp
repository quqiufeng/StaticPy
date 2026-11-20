def f (n : int) -> str
  if (< n 0)
    return "neg"
  else
    if (= n 0)
      return "zero"
    else
      return "pos"
    end
  end
end

def main () -> int
  (call print (call f -3))
  (call print (call f 0))
  (call print (call f 9))
  return 0
end
