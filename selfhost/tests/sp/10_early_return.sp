def find (hay : str needle : str) -> int
  let i int 0
  let n int (call list_length hay)
  while (< i n)
    if (= (call substring hay i (+ i 1)) needle)
      return i
    end
    set i (+ i 1)
  end
  return -1
end

def main () -> int
  (call print (call find "abcdef" "d"))
  (call print (call find "abcdef" "z"))
  return 0
end
