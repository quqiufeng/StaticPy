def main () -> int
  let xs list (call py-list)
  set xs (call py-list-append xs 7)
  set xs (call py-list-append xs 8)
  (call print (call py-list-length xs))
  (call print (call py-list-ref xs 1))
  return 0
end
