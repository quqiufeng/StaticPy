def main () -> int
  let d any (call make_dict)
  (call dict_set d "k" "v")
  (call dict_set d "n" "42")
  (call print (call dict_get_or_empty d "k"))
  (call print (call dict_get_or_empty d "n"))
  (call print (call dict_get_or_empty d "missing"))
  return 0
end
